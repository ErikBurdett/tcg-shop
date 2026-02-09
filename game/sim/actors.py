from __future__ import annotations

from dataclasses import dataclass, field

from game.sim.inventory import Inventory
from game.sim.inventory import RARITIES
from game.cards.collection import CardCollection
from game.cards.deck import Deck
from game.sim.shop import ShelfStock


Tile = tuple[int, int]

MAX_CARRY_BOOSTERS = 3
MAX_CARRY_DECKS = 3
MAX_CARRY_SINGLES = 10


@dataclass
class RestockPlan:
    shelf_key: str
    product: str  # "booster" | "deck" | "single_<rarity>"
    amount: int = 1
    card_id: str | None = None  # for listed-card shelves


@dataclass
class Staff:
    """Roaming staff actor (tile-space coordinates)."""

    # Position in tile-space (e.g., (10.5, 7.5) means center of tile (10,7))
    pos: tuple[float, float]
    speed_tiles_per_s: float = 4.0
    state: str = "idle"  # "idle" | "moving" | "stocking"
    task: str = "none"  # "none" | "pickup" | "deliver"
    target_shelf_key: str | None = None
    target_tile: Tile | None = None  # destination tile (walkable tile adjacent to shelf)
    path: list[Tile] = field(default_factory=list)  # cached path to target_tile
    scan_cooldown: float = 0.4
    stock_timer: float = 0.0
    plan: RestockPlan | None = None
    # React quickly to shelf changes (e.g. customer buys an item).
    priority_shelf_key: str | None = None
    # Carry inventory (picked up from the checkout counter).
    carry_boosters: int = 0
    carry_decks: int = 0
    carry_singles: dict[str, int] = field(default_factory=dict)
    # progression (for rendering XP/level)
    xp: int = 0
    level: int = 1

    def carry_singles_total(self) -> int:
        return sum(self.carry_singles.values())


def notify_shelf_change(staff: Staff, shelf_key: str) -> None:
    """Notify staff that a shelf changed (e.g. product taken off)."""
    staff.priority_shelf_key = shelf_key
    staff.scan_cooldown = 0.0


def _parse_key(key: str) -> Tile:
    x, y = key.split(",")
    return (int(x), int(y))


def _manhattan(a: Tile, b: Tile) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _tile_center(tile: Tile) -> tuple[float, float]:
    return (tile[0] + 0.5, tile[1] + 0.5)


def _is_walkable(tile: Tile, *, grid: Tile, blocked: set[Tile]) -> bool:
    x, y = tile
    if x < 0 or y < 0 or x >= grid[0] or y >= grid[1]:
        return False
    return tile not in blocked


def _adjacent_walk_tiles(shelf_tile: Tile, *, grid: Tile, blocked: set[Tile]) -> list[Tile]:
    x, y = shelf_tile
    candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    result: list[Tile] = []
    for t in candidates:
        if _is_walkable(t, grid=grid, blocked=blocked):
            result.append(t)
    return result


def _bfs_path(start: Tile, goal: Tile, *, grid: Tile, blocked: set[Tile]) -> list[Tile] | None:
    """Return a list of tiles to step through (excluding start), or None if unreachable."""
    if start == goal:
        return []
    if not _is_walkable(goal, grid=grid, blocked=blocked):
        return None
    # Lightweight BFS: grid is small (SHOP_GRID 20x12).
    from collections import deque

    q = deque([start])
    prev: dict[Tile, Tile] = {}
    seen = {start}
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        cx, cy = cur
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            nxt = (nx, ny)
            if nxt in seen:
                continue
            if not _is_walkable(nxt, grid=grid, blocked=blocked):
                continue
            seen.add(nxt)
            prev[nxt] = cur
            q.append(nxt)
    else:
        return None

    # Reconstruct path backward.
    path_rev: list[Tile] = []
    cur = goal
    while cur != start:
        path_rev.append(cur)
        cur = prev[cur]
    path_rev.reverse()
    return path_rev


def choose_restock_plan(
    staff_tile: Tile,
    *,
    shelf_stocks: dict[str, ShelfStock],
    inventory: Inventory,
    collection: CardCollection,
    deck: Deck,
    threshold_ratio: float = 0.999,
) -> RestockPlan | None:
    """Pick the best restock plan without allocating large lists."""
    best_key: str | None = None
    best_plan: RestockPlan | None = None
    best_dist: int = 1_000_000

    for key, stock in shelf_stocks.items():
        if stock.max_qty <= 0:
            continue
        # Restock if below threshold (strictly). With threshold_ratio ~= 1.0 this becomes "qty < max".
        threshold = min(stock.max_qty - 1, int(stock.max_qty * threshold_ratio))
        if stock.qty > threshold:
            continue

        shelf_tile = _parse_key(key)

        # Determine what this shelf should be restocked with.
        card_id: str | None = None
        if getattr(stock, "cards", None):
            # Listed singles shelf: restock using the same card IDs already listed (if possible).
            if stock.cards:
                card_id = stock.cards[0]
                owned = collection.get(card_id)
                in_deck = deck.cards.get(card_id, 0)
                if owned <= in_deck:
                    continue
            else:
                # No listed cards to infer from.
                continue
        else:
            # Bulk products (boosters/decks/singles by rarity). If truly empty, prefer boosters/decks/singles if available.
            desired = stock.product
            if desired == "empty":
                if inventory.booster_packs > 0:
                    desired = "booster"
                elif inventory.decks > 0:
                    desired = "deck"
                else:
                    # pick any rarity with available singles
                    pick = None
                    for r in RARITIES:
                        if inventory.singles.get(r, 0) > 0:
                            pick = r
                            break
                    if pick:
                        desired = f"single_{pick}"
                    else:
                        continue

            if desired == "booster":
                if inventory.booster_packs <= 0:
                    continue
            elif desired == "deck":
                if inventory.decks <= 0:
                    continue
            elif desired.startswith("single_"):
                rarity = desired.replace("single_", "")
                if inventory.singles.get(rarity, 0) <= 0:
                    continue
            else:
                continue

        dist = _manhattan(staff_tile, shelf_tile)
        if dist < best_dist:
            best_dist = dist
            best_key = key
            amount = max(1, stock.max_qty - stock.qty)
            best_plan = RestockPlan(shelf_key=key, product=stock.product, amount=amount, card_id=card_id)

    _ = best_key
    return best_plan


def apply_restock(
    plan: RestockPlan,
    *,
    shelf_stocks: dict[str, ShelfStock],
    inventory: Inventory,
    collection: CardCollection,
    deck: Deck,
    amount: int = 2,
) -> int:
    """Apply the restock changes. Returns number of items stocked."""
    stock = shelf_stocks.get(plan.shelf_key)
    if not stock:
        return 0
    if stock.qty >= stock.max_qty:
        return 0
    capacity = stock.max_qty - stock.qty

    # Listed card shelf
    if plan.card_id:
        cid = plan.card_id
        owned = collection.get(cid)
        in_deck = deck.cards.get(cid, 0)
        if owned <= in_deck:
            return 0
        if not getattr(stock, "cards", None):
            return 0
        if not collection.remove(cid, 1):
            return 0
        stock.cards.append(cid)
        stock.qty = len(stock.cards)
        stock.product = plan.product
        return 1

    # Bulk inventory
    to_add = min(amount, capacity)
    if plan.product == "booster":
        to_add = min(to_add, inventory.booster_packs)
        if to_add <= 0:
            return 0
        inventory.booster_packs -= to_add
    elif plan.product == "deck":
        to_add = min(to_add, inventory.decks)
        if to_add <= 0:
            return 0
        inventory.decks -= to_add
    elif plan.product.startswith("single_"):
        rarity = plan.product.replace("single_", "")
        available = inventory.singles.get(rarity, 0)
        to_add = min(to_add, available)
        if to_add <= 0:
            return 0
        inventory.singles[rarity] = available - to_add
    else:
        return 0

    stock.product = plan.product
    if hasattr(stock, "cards"):
        stock.cards.clear()
    stock.qty += to_add
    return int(to_add)


def _pickup_at_counter(staff: Staff, *, inventory: Inventory, preferred_single_rarity: str | None) -> None:
    """Fill carry up to max limits, removing items from inventory."""
    # Boosters
    need_b = MAX_CARRY_BOOSTERS - int(staff.carry_boosters)
    if need_b > 0 and inventory.booster_packs > 0:
        take = min(need_b, int(inventory.booster_packs))
        staff.carry_boosters += take
        inventory.booster_packs -= take

    # Decks
    need_d = MAX_CARRY_DECKS - int(staff.carry_decks)
    if need_d > 0 and inventory.decks > 0:
        take = min(need_d, int(inventory.decks))
        staff.carry_decks += take
        inventory.decks -= take

    # Singles (any rarity) – bias toward the requested rarity first if present.
    if not staff.carry_singles:
        staff.carry_singles = {r: 0 for r in RARITIES}
    remaining = MAX_CARRY_SINGLES - staff.carry_singles_total()
    if remaining <= 0:
        return

    order: list[str] = []
    if preferred_single_rarity and preferred_single_rarity in RARITIES:
        order.append(preferred_single_rarity)
    for r in RARITIES:
        if r not in order:
            order.append(r)
    for r in order:
        if remaining <= 0:
            break
        avail = int(inventory.singles.get(r, 0))
        if avail <= 0:
            continue
        take = min(remaining, avail)
        staff.carry_singles[r] = int(staff.carry_singles.get(r, 0)) + take
        inventory.singles[r] = avail - take
        remaining -= take


def _deliver_from_carry(staff: Staff, plan: RestockPlan, *, shelf_stocks: dict[str, ShelfStock]) -> int:
    """Restock a shelf using carried items (no inventory reads)."""
    stock = shelf_stocks.get(plan.shelf_key)
    if not stock:
        return 0
    if stock.max_qty <= 0:
        return 0
    if stock.qty >= stock.max_qty:
        return 0
    capacity = int(stock.max_qty - stock.qty)
    if capacity <= 0:
        return 0

    product = stock.product
    # If shelf is truly empty, allow plan to set a product.
    if product == "empty":
        product = plan.product if plan.product != "empty" else product

    # If plan targets an empty shelf, plan.product may still be "empty" (fallback to what staff carries).
    if product == "empty":
        if staff.carry_boosters > 0:
            product = "booster"
        elif staff.carry_decks > 0:
            product = "deck"
        else:
            for r in RARITIES:
                if int(staff.carry_singles.get(r, 0)) > 0:
                    product = f"single_{r}"
                    break

    if product == "booster":
        to_add = min(capacity, int(staff.carry_boosters))
        if to_add <= 0:
            return 0
        staff.carry_boosters -= to_add
        stock.product = "booster"
        stock.qty += to_add
        return int(to_add)
    if product == "deck":
        to_add = min(capacity, int(staff.carry_decks))
        if to_add <= 0:
            return 0
        staff.carry_decks -= to_add
        stock.product = "deck"
        stock.qty += to_add
        return int(to_add)
    if product.startswith("single_"):
        rarity = product.replace("single_", "")
        to_add = min(capacity, int(staff.carry_singles.get(rarity, 0)))
        if to_add <= 0:
            return 0
        staff.carry_singles[rarity] = int(staff.carry_singles.get(rarity, 0)) - to_add
        stock.product = product
        stock.qty += to_add
        if hasattr(stock, "cards"):
            stock.cards.clear()
        return int(to_add)
    return 0


@dataclass(frozen=True)
class StaffRestockResult:
    did_restock: bool
    items_moved: int = 0
    product: str | None = None


def update_staff(
    staff: Staff,
    dt: float,
    *,
    grid: Tile,
    blocked_tiles: set[Tile],
    counter_tile: Tile | None,
    shelf_stocks: dict[str, ShelfStock],
    inventory: Inventory,
    collection: CardCollection,
    deck: Deck,
    restock_threshold_ratio: float = 0.999,
    stock_time: float = 0.8,
) -> StaffRestockResult:
    """Advance staff state machine."""
    # Throttled scanning (avoid O(N shelves) each frame).
    staff.scan_cooldown = max(0.0, staff.scan_cooldown - dt)

    # Update derived level (simple progression).
    staff.level = max(1, 1 + staff.xp // 100)

    # Movement/stocking state machine.
    if staff.state == "stocking":
        staff.stock_timer = max(0.0, staff.stock_timer - dt)
        if staff.stock_timer <= 0.0 and staff.plan:
            # For listed-card shelves, fall back to legacy restock (collection-based).
            if staff.plan.card_id:
                moved = apply_restock(
                    staff.plan, shelf_stocks=shelf_stocks, inventory=inventory, collection=collection, deck=deck
                )
            else:
                moved = _deliver_from_carry(staff, staff.plan, shelf_stocks=shelf_stocks)
            product = staff.plan.product
            staff.plan = None
            staff.target_shelf_key = None
            staff.target_tile = None
            staff.path.clear()
            staff.state = "idle"
            staff.task = "none"
            if moved > 0:
                return StaffRestockResult(True, int(moved), str(product))
        return StaffRestockResult(False)

    if staff.state == "moving":
        # Follow cached path tile-by-tile (tile-space movement).
        if not staff.target_tile:
            staff.state = "idle"
            return StaffRestockResult(False)
        px, py = staff.pos
        if staff.path:
            next_tile = staff.path[0]
        else:
            next_tile = staff.target_tile
        tx, ty = _tile_center(next_tile)
        dx = tx - px
        dy = ty - py
        dist2 = dx * dx + dy * dy
        if dist2 < 0.0004:
            # Reached this step.
            if staff.path:
                staff.path.pop(0)
            # If reached final tile, start stocking.
            if not staff.path and next_tile == staff.target_tile:
                if staff.task == "pickup":
                    # Pick up stock at the counter, then retarget the shelf.
                    preferred: str | None = None
                    if staff.plan and staff.plan.product.startswith("single_"):
                        preferred = staff.plan.product.replace("single_", "")
                    _pickup_at_counter(staff, inventory=inventory, preferred_single_rarity=preferred)
                    staff.task = "deliver"
                    # Compute path to shelf after pickup.
                    if not staff.plan:
                        staff.state = "idle"
                        staff.task = "none"
                        return StaffRestockResult(False)
                    shelf_tile = _parse_key(staff.plan.shelf_key)
                    walk_tiles = _adjacent_walk_tiles(shelf_tile, grid=grid, blocked=blocked_tiles)
                    if not walk_tiles:
                        staff.state = "idle"
                        staff.task = "none"
                        staff.plan = None
                        return StaffRestockResult(False)
                    walk_tiles.sort(key=lambda t: _manhattan((int(staff.pos[0]), int(staff.pos[1])), t))
                    dest = walk_tiles[0]
                    staff_tile = (int(staff.pos[0]), int(staff.pos[1]))
                    path = _bfs_path(staff_tile, dest, grid=grid, blocked=blocked_tiles) or []
                    staff.target_tile = dest
                    staff.path = path
                    staff.state = "moving"
                    return StaffRestockResult(False)

                staff.state = "stocking"
                staff.stock_timer = stock_time
            staff.pos = (tx, ty)
            return StaffRestockResult(False)

        import math

        dist = math.sqrt(dist2)
        step = staff.speed_tiles_per_s * dt
        if step >= dist:
            staff.pos = (tx, ty)
        else:
            staff.pos = (px + dx / dist * step, py + dy / dist * step)
        return StaffRestockResult(False)

    # Idle: scan for work occasionally.
    if staff.state != "idle":
        staff.state = "idle"

    if staff.scan_cooldown > 0:
        return StaffRestockResult(False)
    staff.scan_cooldown = 0.8

    staff_tile = (int(staff.pos[0]), int(staff.pos[1]))
    # Priority shelf first (reacts to sales).
    plan: RestockPlan | None = None
    if staff.priority_shelf_key and staff.priority_shelf_key in shelf_stocks:
        stock = shelf_stocks.get(staff.priority_shelf_key)
        if stock and stock.qty < stock.max_qty:
            plan = RestockPlan(shelf_key=staff.priority_shelf_key, product=stock.product, amount=stock.max_qty - stock.qty)
        staff.priority_shelf_key = None
    if not plan:
        plan = choose_restock_plan(
            staff_tile,
            shelf_stocks=shelf_stocks,
            inventory=inventory,
            collection=collection,
            deck=deck,
            threshold_ratio=restock_threshold_ratio,
        )
    if not plan:
        return StaffRestockResult(False)

    # If plan points at a shelf that is truly empty, choose what to put on it based on carry/inventory.
    stock = shelf_stocks.get(plan.shelf_key)
    if stock and stock.product == "empty":
        if staff.carry_boosters > 0 or inventory.booster_packs > 0:
            plan.product = "booster"
        elif staff.carry_decks > 0 or inventory.decks > 0:
            plan.product = "deck"
        else:
            pick = None
            for r in RARITIES:
                if int(staff.carry_singles.get(r, 0)) > 0 or int(inventory.singles.get(r, 0)) > 0:
                    pick = r
                    break
            if pick:
                plan.product = f"single_{pick}"

    # Decide whether we need to visit the counter first (pickup).
    needs_pickup = False
    if plan.product == "booster":
        needs_pickup = staff.carry_boosters <= 0
    elif plan.product == "deck":
        needs_pickup = staff.carry_decks <= 0
    elif plan.product.startswith("single_"):
        rarity = plan.product.replace("single_", "")
        needs_pickup = int(staff.carry_singles.get(rarity, 0)) <= 0
    # If we have no carry at all, go pick up to avoid thrashing between shelves.
    if staff.carry_boosters + staff.carry_decks + staff.carry_singles_total() <= 0:
        needs_pickup = True

    staff.plan = plan
    staff.target_shelf_key = plan.shelf_key
    if needs_pickup and counter_tile is not None:
        # Walk to a tile adjacent to the counter.
        walk_tiles = _adjacent_walk_tiles(counter_tile, grid=grid, blocked=blocked_tiles)
        if not walk_tiles:
            return StaffRestockResult(False)
        walk_tiles.sort(key=lambda t: _manhattan(staff_tile, t))
        dest = walk_tiles[0]
        path = _bfs_path(staff_tile, dest, grid=grid, blocked=blocked_tiles) or []
        staff.target_tile = dest
        staff.path = path
        staff.task = "pickup"
        staff.state = "moving"
        return StaffRestockResult(False)

    # Otherwise, go directly to the shelf to deliver.
    shelf_tile = _parse_key(plan.shelf_key)
    walk_tiles = _adjacent_walk_tiles(shelf_tile, grid=grid, blocked=blocked_tiles)
    if not walk_tiles:
        return StaffRestockResult(False)
    walk_tiles.sort(key=lambda t: _manhattan(staff_tile, t))
    dest = walk_tiles[0]
    path = _bfs_path(staff_tile, dest, grid=grid, blocked=blocked_tiles) or []
    staff.target_tile = dest
    staff.path = path
    staff.task = "deliver"
    staff.state = "moving"
    return StaffRestockResult(False)

