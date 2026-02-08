from __future__ import annotations

from dataclasses import dataclass, field

from game.sim.progression import PlayerProgression


@dataclass(frozen=True)
class Modifiers:
    """Aggregated modifiers produced by skills.

    Percent values are expressed as fractions (e.g. 0.10 == +10%).
    """

    sell_price_pct: float = 0.0
    sales_xp_pct: float = 0.0
    battle_xp_pct: float = 0.0
    fixture_discount_pct: float = 0.0

    def __add__(self, other: "Modifiers") -> "Modifiers":
        return Modifiers(
            sell_price_pct=self.sell_price_pct + other.sell_price_pct,
            sales_xp_pct=self.sales_xp_pct + other.sales_xp_pct,
            battle_xp_pct=self.battle_xp_pct + other.battle_xp_pct,
            fixture_discount_pct=self.fixture_discount_pct + other.fixture_discount_pct,
        )

    def scale(self, k: float) -> "Modifiers":
        return Modifiers(
            sell_price_pct=self.sell_price_pct * k,
            sales_xp_pct=self.sales_xp_pct * k,
            battle_xp_pct=self.battle_xp_pct * k,
            fixture_discount_pct=self.fixture_discount_pct * k,
        )


@dataclass(frozen=True)
class SkillPrereq:
    skill_id: str
    rank: int = 1


@dataclass(frozen=True)
class SkillNodeDef:
    skill_id: str
    name: str
    desc: str
    pos: tuple[int, int]
    max_rank: int = 1
    level_req: int = 1
    prereqs: tuple[SkillPrereq, ...] = ()
    mods_per_rank: Modifiers = Modifiers()


@dataclass(frozen=True)
class SkillTreeDef:
    nodes: dict[str, SkillNodeDef]

    def validate(self) -> None:
        if len(self.nodes) < 20:
            raise ValueError("SkillTreeDef must include at least 20 skills.")
        for sid, node in self.nodes.items():
            if sid != node.skill_id:
                raise ValueError(f"Skill id mismatch: key={sid} node.skill_id={node.skill_id}")
            if node.max_rank < 1:
                raise ValueError(f"{sid}: max_rank must be >= 1")
            if node.level_req < 1:
                raise ValueError(f"{sid}: level_req must be >= 1")
            for pr in node.prereqs:
                if pr.skill_id not in self.nodes:
                    raise ValueError(f"{sid}: prereq missing: {pr.skill_id}")
                if pr.rank < 1:
                    raise ValueError(f"{sid}: prereq rank must be >= 1")
        # Light cycle check (DFS) to avoid accidental loops in prerequisites.
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(cur: str) -> None:
            if cur in visited:
                return
            if cur in visiting:
                raise ValueError(f"Skill prereq cycle detected at {cur}")
            visiting.add(cur)
            for pr in self.nodes[cur].prereqs:
                dfs(pr.skill_id)
            visiting.remove(cur)
            visited.add(cur)

        for sid in self.nodes:
            dfs(sid)


@dataclass
class SkillTreeState:
    """Player-owned skill ranks + cached aggregated modifiers."""

    ranks: dict[str, int] = field(default_factory=dict)
    _dirty: bool = True
    _cached_mods: Modifiers = field(default_factory=Modifiers)

    def rank(self, skill_id: str) -> int:
        return int(self.ranks.get(skill_id, 0))

    def can_rank_up(self, tree: SkillTreeDef, skill_id: str, prog: PlayerProgression) -> tuple[bool, str]:
        node = tree.nodes.get(skill_id)
        if not node:
            return (False, "Unknown skill.")
        cur = self.rank(skill_id)
        if cur >= node.max_rank:
            return (False, "Already max rank.")
        if prog.skill_points <= 0:
            return (False, "No skill points.")
        if prog.level < node.level_req:
            return (False, f"Requires level {node.level_req}.")
        for pr in node.prereqs:
            if self.rank(pr.skill_id) < pr.rank:
                return (False, f"Requires {tree.nodes[pr.skill_id].name} rank {pr.rank}.")
        return (True, "OK")

    def rank_up(self, tree: SkillTreeDef, skill_id: str, prog: PlayerProgression) -> bool:
        ok, _reason = self.can_rank_up(tree, skill_id, prog)
        if not ok:
            return False
        self.ranks[skill_id] = self.rank(skill_id) + 1
        prog.skill_points -= 1
        self._dirty = True
        return True

    def modifiers(self, tree: SkillTreeDef) -> Modifiers:
        if not self._dirty:
            return self._cached_mods
        mods = Modifiers()
        for sid, rank in self.ranks.items():
            if rank <= 0:
                continue
            node = tree.nodes.get(sid)
            if not node:
                continue
            r = min(int(rank), node.max_rank)
            mods = mods + node.mods_per_rank.scale(float(r))
        self._cached_mods = mods
        self._dirty = False
        return mods

    def to_dict(self) -> dict[str, object]:
        return {"ranks": dict(self.ranks)}

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "SkillTreeState":
        if not data:
            return cls()
        ranks_obj = data.get("ranks", {})  # type: ignore[assignment]
        ranks: dict[str, int] = {}
        if isinstance(ranks_obj, dict):
            for k, v in ranks_obj.items():
                try:
                    ranks[str(k)] = max(0, int(v))  # type: ignore[arg-type]
                except Exception:
                    continue
        return cls(ranks=ranks)


def default_skill_tree() -> SkillTreeDef:
    """Return the game's default skill tree (>= 20 nodes)."""

    def n(
        sid: str,
        name: str,
        desc: str,
        pos: tuple[int, int],
        *,
        max_rank: int = 1,
        level_req: int = 1,
        prereqs: tuple[SkillPrereq, ...] = (),
        mods_per_rank: Modifiers = Modifiers(),
    ) -> SkillNodeDef:
        return SkillNodeDef(
            skill_id=sid,
            name=name,
            desc=desc,
            pos=pos,
            max_rank=max_rank,
            level_req=level_req,
            prereqs=prereqs,
            mods_per_rank=mods_per_rank,
        )

    nodes = {
        # Commerce spine
        "haggle": n(
            "haggle",
            "Haggle",
            "Increase your sell prices slightly.",
            (0, 0),
            max_rank=10,
            mods_per_rank=Modifiers(sell_price_pct=0.01),
        ),
        "premium_display": n(
            "premium_display",
            "Premium Display",
            "Better presentation means customers pay a little more.",
            (220, -40),
            max_rank=10,
            level_req=5,
            prereqs=(SkillPrereq("haggle", 3),),
            mods_per_rank=Modifiers(sell_price_pct=0.005),
        ),
        "local_reputation": n(
            "local_reputation",
            "Local Reputation",
            "Earn more XP from sales.",
            (220, 40),
            max_rank=5,
            level_req=3,
            prereqs=(SkillPrereq("haggle", 2),),
            mods_per_rank=Modifiers(sales_xp_pct=0.05),
        ),
        "bulk_buying": n(
            "bulk_buying",
            "Bulk Buying",
            "Discount fixture purchases.",
            (440, 0),
            max_rank=5,
            level_req=8,
            prereqs=(SkillPrereq("premium_display", 3),),
            mods_per_rank=Modifiers(fixture_discount_pct=0.03),
        ),
        "market_savvy": n(
            "market_savvy",
            "Market Savvy",
            "Earn more XP from battle wins.",
            (440, 90),
            max_rank=5,
            level_req=6,
            prereqs=(SkillPrereq("local_reputation", 2),),
            mods_per_rank=Modifiers(battle_xp_pct=0.05),
        ),
        # Battle branch
        "sparring": n(
            "sparring",
            "Sparring",
            "Learn by fighting; +battle XP.",
            (0, 220),
            max_rank=5,
            mods_per_rank=Modifiers(battle_xp_pct=0.05),
        ),
        "tactics": n(
            "tactics",
            "Tactics",
            "More battle XP from smarter play.",
            (220, 220),
            max_rank=5,
            level_req=4,
            prereqs=(SkillPrereq("sparring", 2),),
            mods_per_rank=Modifiers(battle_xp_pct=0.05),
        ),
        "champion": n(
            "champion",
            "Champion",
            "A proven winner; more battle XP.",
            (440, 220),
            max_rank=5,
            level_req=10,
            prereqs=(SkillPrereq("tactics", 3),),
            mods_per_rank=Modifiers(battle_xp_pct=0.06),
        ),
        # Operations branch (mostly placeholders for future effects)
        "shopkeeping": n(
            "shopkeeping",
            "Shopkeeping",
            "Core shop operations training.",
            (-180, 80),
            max_rank=5,
            mods_per_rank=Modifiers(sales_xp_pct=0.03),
        ),
        "inventory_habits": n(
            "inventory_habits",
            "Inventory Habits",
            "Learn to run tighter operations.",
            (-360, 80),
            max_rank=5,
            level_req=4,
            prereqs=(SkillPrereq("shopkeeping", 2),),
        ),
        "store_layout": n(
            "store_layout",
            "Store Layout",
            "Place fixtures intentionally.",
            (-360, -20),
            max_rank=5,
            level_req=6,
            prereqs=(SkillPrereq("shopkeeping", 2),),
            mods_per_rank=Modifiers(fixture_discount_pct=0.01),
        ),
        "community_events": n(
            "community_events",
            "Community Events",
            "More sales XP from engagement.",
            (-360, 180),
            max_rank=5,
            level_req=7,
            prereqs=(SkillPrereq("shopkeeping", 3),),
            mods_per_rank=Modifiers(sales_xp_pct=0.04),
        ),
        # Extra nodes to reach >=20 with a structured graph
        "collector": n(
            "collector",
            "Collector",
            "A love of cards keeps you motivated (+sales XP).",
            (-180, -80),
            max_rank=5,
            level_req=2,
            prereqs=(SkillPrereq("haggle", 1),),
            mods_per_rank=Modifiers(sales_xp_pct=0.03),
        ),
        "advertising": n(
            "advertising",
            "Advertising",
            "Premium display has more impact on pricing.",
            (220, -140),
            max_rank=5,
            level_req=9,
            prereqs=(SkillPrereq("premium_display", 4),),
            mods_per_rank=Modifiers(sell_price_pct=0.004),
        ),
        "vip_regulars": n(
            "vip_regulars",
            "VIP Regulars",
            "Regulars pay a little more.",
            (440, -120),
            max_rank=5,
            level_req=12,
            prereqs=(SkillPrereq("advertising", 2),),
            mods_per_rank=Modifiers(sell_price_pct=0.004),
        ),
        "shrewd_deals": n(
            "shrewd_deals",
            "Shrewd Deals",
            "Discount fixtures further.",
            (660, -60),
            max_rank=5,
            level_req=14,
            prereqs=(SkillPrereq("bulk_buying", 2),),
            mods_per_rank=Modifiers(fixture_discount_pct=0.02),
        ),
        "sales_grind": n(
            "sales_grind",
            "Sales Grind",
            "More XP from sales (practice).",
            (660, 60),
            max_rank=10,
            level_req=11,
            prereqs=(SkillPrereq("local_reputation", 3),),
            mods_per_rank=Modifiers(sales_xp_pct=0.02),
        ),
        "battle_grind": n(
            "battle_grind",
            "Battle Grind",
            "More XP from wins (practice).",
            (660, 180),
            max_rank=10,
            level_req=11,
            prereqs=(SkillPrereq("tactics", 2),),
            mods_per_rank=Modifiers(battle_xp_pct=0.02),
        ),
        "master_merchant": n(
            "master_merchant",
            "Master Merchant",
            "Late-game pricing edge.",
            (880, 0),
            max_rank=10,
            level_req=25,
            prereqs=(SkillPrereq("vip_regulars", 3), SkillPrereq("sales_grind", 5)),
            mods_per_rank=Modifiers(sell_price_pct=0.003),
        ),
        "legend": n(
            "legend",
            "Legend",
            "Late-game battle XP edge.",
            (880, 220),
            max_rank=10,
            level_req=25,
            prereqs=(SkillPrereq("champion", 3), SkillPrereq("battle_grind", 5)),
            mods_per_rank=Modifiers(battle_xp_pct=0.02),
        ),
        "frugal_builder": n(
            "frugal_builder",
            "Frugal Builder",
            "Fixtures are cheaper.",
            (660, -180),
            max_rank=10,
            level_req=15,
            prereqs=(SkillPrereq("store_layout", 2),),
            mods_per_rank=Modifiers(fixture_discount_pct=0.01),
        ),
        "efficiency": n(
            "efficiency",
            "Efficiency",
            "General skill; more sales XP.",
            (-540, 130),
            max_rank=10,
            level_req=10,
            prereqs=(SkillPrereq("inventory_habits", 2),),
            mods_per_rank=Modifiers(sales_xp_pct=0.01),
        ),
        "grit": n(
            "grit",
            "Grit",
            "General skill; more battle XP.",
            (-180, 320),
            max_rank=10,
            level_req=10,
            prereqs=(SkillPrereq("sparring", 3),),
            mods_per_rank=Modifiers(battle_xp_pct=0.01),
        ),
    }
    tree = SkillTreeDef(nodes=nodes)
    tree.validate()
    return tree


_DEFAULT_TREE: SkillTreeDef | None = None


def get_default_skill_tree() -> SkillTreeDef:
    """Return a cached default skill tree definition."""
    global _DEFAULT_TREE
    if _DEFAULT_TREE is None:
        _DEFAULT_TREE = default_skill_tree()
    return _DEFAULT_TREE

