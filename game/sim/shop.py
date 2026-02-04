from __future__ import annotations

from dataclasses import dataclass, field

from game.config import SHOP_GRID


@dataclass
class ShopObject:
    kind: str
    tile: tuple[int, int]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "tile": list(self.tile)}

    @classmethod
    def from_dict(cls, data: dict) -> "ShopObject":
        return cls(data["kind"], tuple(data["tile"]))


@dataclass
class ShelfStock:
    product: str
    qty: int
    max_qty: int = 10
    cards: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"product": self.product, "qty": self.qty, "max_qty": self.max_qty, "cards": list(self.cards)}

    @classmethod
    def from_dict(cls, data: dict) -> "ShelfStock":
        return cls(
            data["product"],
            data["qty"],
            data.get("max_qty", 10),
            list(data.get("cards", [])),
        )


class ShopLayout:
    """Represents placed objects in the shop grid."""

    def __init__(self) -> None:
        self.grid = SHOP_GRID
        self.objects: list[ShopObject] = []
        self.shelf_stocks: dict[str, ShelfStock] = {}
        self._place_default()

    def _place_default(self) -> None:
        self.objects = [
            ShopObject("counter", (10, 7)),
            ShopObject("poster", (2, 1)),
        ]

    def place(self, kind: str, tile: tuple[int, int]) -> None:
        if not self._in_bounds(tile):
            return
        if self.object_at(tile) is not None:
            return
        self.objects.append(ShopObject(kind, tile))
        if kind == "shelf":
            self.shelf_stocks.setdefault(self._key(tile), ShelfStock("empty", 0))

    def remove_at(self, tile: tuple[int, int]) -> None:
        self.objects = [obj for obj in self.objects if obj.tile != tile]
        self.shelf_stocks.pop(self._key(tile), None)

    def object_at(self, tile: tuple[int, int]) -> ShopObject | None:
        for obj in self.objects:
            if obj.tile == tile:
                return obj
        return None

    def _in_bounds(self, tile: tuple[int, int]) -> bool:
        x, y = tile
        return 0 <= x < self.grid[0] and 0 <= y < self.grid[1]

    def _key(self, tile: tuple[int, int]) -> str:
        return f"{tile[0]},{tile[1]}"

    def shelf_tiles(self) -> list[tuple[int, int]]:
        return [obj.tile for obj in self.objects if obj.kind == "shelf"]

    def to_dict(self) -> dict:
        return {
            "objects": [obj.to_dict() for obj in self.objects],
            "shelf_stocks": {key: stock.to_dict() for key, stock in self.shelf_stocks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShopLayout":
        layout = cls()
        layout.objects = [ShopObject.from_dict(d) for d in data.get("objects", [])]
        layout.shelf_stocks = {
            key: ShelfStock.from_dict(stock) for key, stock in data.get("shelf_stocks", {}).items()
        }
        for tile in layout.shelf_tiles():
            layout.shelf_stocks.setdefault(layout._key(tile), ShelfStock("empty", 0))
        return layout
