from __future__ import annotations

from dataclasses import dataclass, field

from game.sim.inventory import Inventory
from game.cards.collection import CardCollection
from game.cards.deck import Deck
from game.sim.shop import ShelfStock


Tile = tuple[int, int]


@dataclass
class RestockPlan:
    shelf_key: str
    product: str  # "booster" | "deck" | "single_<rarity>"
    card_id: str | None = None  # for listed-card shelves


@dataclass
class Staff:
    """Roaming staff actor (tile-space coordinates)."""

    # Position in tile-space (e.g., (10.5, 7.5) means center of tile (10,7))
    pos: tuple[float, float]
    speed_tiles_per_s: float = 4.0
    state: str = "idle"  # "idle" | "moving" | "stocking"
    target_shelf_key: str | None = None
    target_tile: Tile | None = None  # destination tile (walkable tile adjacent to shelf)
    path: list[Tile] = field(default_factory=list)  # cached path to target_tile
    scan_cooldown: float = 0.4
    stock_timer: float = 0.0
    plan: RestockPlan | None = None
    # progression (for rendering XP/level)
    xp: int = 0
    level: int = 1


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
    threshold_ratio: float = 0.4,
) -> RestockPlan | None:
    """Pick the best restock plan without allocating large lists."""
    best_key: str | None = None
    best_plan: RestockPlan | None = None
    best_dist: int = 1_000_000

    for key, stock in shelf_stocks.items():
        if stock.product == "empty" or stock.max_qty <= 0:
            continue
        threshold = int(stock.max_qty * threshold_ratio)
        # Restock if below threshold (strictly).
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
            # Bulk products (boosters/decks/singles by rarity)
            if stock.product == "booster":
                if inventory.booster_packs <= 0:
                    continue
            elif stock.product == "deck":
                if inventory.decks <= 0:
                    continue
            elif stock.product.startswith("single_"):
                rarity = stock.product.replace("single_", "")
                if inventory.singles.get(rarity, 0) <= 0:
                    continue
            else:
                continue

        dist = _manhattan(staff_tile, shelf_tile)
        if dist < best_dist:
            best_dist = dist
            best_key = key
            best_plan = RestockPlan(shelf_key=key, product=stock.product, card_id=card_id)

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
) -> bool:
    """Apply the restock changes. Returns True if something was stocked."""
    stock = shelf_stocks.get(plan.shelf_key)
    if not stock:
        return False
    if stock.qty >= stock.max_qty:
        return False
    capacity = stock.max_qty - stock.qty

    # Listed card shelf
    if plan.card_id:
        cid = plan.card_id
        owned = collection.get(cid)
        in_deck = deck.cards.get(cid, 0)
        if owned <= in_deck:
            return False
        if not getattr(stock, "cards", None):
            return False
        if not collection.remove(cid, 1):
            return False
        stock.cards.append(cid)
        stock.qty = len(stock.cards)
        stock.product = plan.product
        return True

    # Bulk inventory
    to_add = min(amount, capacity)
    if plan.product == "booster":
        to_add = min(to_add, inventory.booster_packs)
        if to_add <= 0:
            return False
        inventory.booster_packs -= to_add
    elif plan.product == "deck":
        to_add = min(to_add, inventory.decks)
        if to_add <= 0:
            return False
        inventory.decks -= to_add
    elif plan.product.startswith("single_"):
        rarity = plan.product.replace("single_", "")
        available = inventory.singles.get(rarity, 0)
        to_add = min(to_add, available)
        if to_add <= 0:
            return False
        inventory.singles[rarity] = available - to_add
    else:
        return False

    stock.product = plan.product
    if hasattr(stock, "cards"):
        stock.cards.clear()
    stock.qty += to_add
    return to_add > 0


def update_staff(
    staff: Staff,
    dt: float,
    *,
    grid: Tile,
    blocked_tiles: set[Tile],
    shelf_stocks: dict[str, ShelfStock],
    inventory: Inventory,
    collection: CardCollection,
    deck: Deck,
    restock_threshold_ratio: float = 0.4,
    stock_time: float = 0.8,
) -> bool:
    """Advance staff state machine."""
    did_restock = False
    # Throttled scanning (avoid O(N shelves) each frame).
    staff.scan_cooldown = max(0.0, staff.scan_cooldown - dt)

    # Update derived level (simple progression).
    staff.level = max(1, 1 + staff.xp // 100)

    # Movement/stocking state machine.
    if staff.state == "stocking":
        staff.stock_timer = max(0.0, staff.stock_timer - dt)
        if staff.stock_timer <= 0.0 and staff.plan:
            if apply_restock(
                staff.plan, shelf_stocks=shelf_stocks, inventory=inventory, collection=collection, deck=deck
            ):
                staff.xp += 10
                did_restock = True
            staff.plan = None
            staff.target_shelf_key = None
            staff.target_tile = None
            staff.path.clear()
            staff.state = "idle"
        return did_restock

    if staff.state == "moving":
        # Follow cached path tile-by-tile (tile-space movement).
        if not staff.target_tile:
            staff.state = "idle"
            return
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
                staff.state = "stocking"
                staff.stock_timer = stock_time
            staff.pos = (tx, ty)
            return did_restock

        import math

        dist = math.sqrt(dist2)
        step = staff.speed_tiles_per_s * dt
        if step >= dist:
            staff.pos = (tx, ty)
        else:
            staff.pos = (px + dx / dist * step, py + dy / dist * step)
        return did_restock

    # Idle: scan for work occasionally.
    if staff.state != "idle":
        staff.state = "idle"

    if staff.scan_cooldown > 0:
        return did_restock
    staff.scan_cooldown = 0.8

    staff_tile = (int(staff.pos[0]), int(staff.pos[1]))
    plan = choose_restock_plan(
        staff_tile,
        shelf_stocks=shelf_stocks,
        inventory=inventory,
        collection=collection,
        deck=deck,
        threshold_ratio=restock_threshold_ratio,
    )
    if not plan:
        return did_restock

    shelf_tile = _parse_key(plan.shelf_key)
    walk_tiles = _adjacent_walk_tiles(shelf_tile, grid=grid, blocked=blocked_tiles)
    if not walk_tiles:
        return did_restock
    # Pick the closest adjacent tile.
    walk_tiles.sort(key=lambda t: _manhattan(staff_tile, t))
    dest = walk_tiles[0]

    # Path cache: compute once for this target.
    path = _bfs_path(staff_tile, dest, grid=grid, blocked=blocked_tiles)
    if path is None:
        # If blocked/unreachable, fall back to direct move (no path).
        path = []

    staff.plan = plan
    staff.target_shelf_key = plan.shelf_key
    staff.target_tile = dest
    staff.path = path
    staff.state = "moving"
    return did_restock

