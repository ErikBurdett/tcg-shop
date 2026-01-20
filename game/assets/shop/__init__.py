"""Shop asset management for interior tiles and customer sprites."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional
import random

import pygame


SHOP_ASSET_DIR = Path(__file__).parent


class ShopAssetManager:
    """Manages shop interior and customer sprite assets."""

    def __init__(self) -> None:
        self._floor_tiles: list[pygame.Surface] = []
        self._customer_sprites: list[pygame.Surface] = []
        self._furniture_sheet: Optional[pygame.Surface] = None
        self._cache: Dict[str, pygame.Surface] = {}
        self._initialized = False

    def init(self) -> None:
        """Initialize assets. Call after pygame.init()."""
        if self._initialized:
            return

        # Load floor tiles
        tiles_dir = SHOP_ASSET_DIR / "tiles"
        for i in range(4):
            path = tiles_dir / f"floor_{i}.png"
            if path.exists():
                surface = pygame.image.load(str(path)).convert_alpha()
                self._floor_tiles.append(surface)

        # Load customer sprites
        for i in range(8):
            path = tiles_dir / f"customer_{i}.png"
            if path.exists():
                surface = pygame.image.load(str(path)).convert_alpha()
                self._customer_sprites.append(surface)

        # Load furniture sheet
        furniture_path = SHOP_ASSET_DIR / "furniture.png"
        if furniture_path.exists():
            self._furniture_sheet = pygame.image.load(str(furniture_path)).convert_alpha()

        self._initialized = True

    def get_floor_tile(self, variant: int = 0, size: Tuple[int, int] = (48, 48)) -> Optional[pygame.Surface]:
        """Get a floor tile scaled to the given size."""
        if not self._initialized:
            self.init()

        if not self._floor_tiles:
            return None

        cache_key = f"floor_{variant}_{size[0]}x{size[1]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        tile_idx = variant % len(self._floor_tiles)
        scaled = pygame.transform.scale(self._floor_tiles[tile_idx], size)
        self._cache[cache_key] = scaled
        return scaled

    def get_customer_sprite(self, customer_id: int, size: Tuple[int, int] = (32, 32)) -> Optional[pygame.Surface]:
        """Get a customer sprite scaled to the given size, properly centered."""
        if not self._initialized:
            self.init()

        if not self._customer_sprites:
            return None

        cache_key = f"customer_{customer_id}_{size[0]}x{size[1]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        sprite_idx = customer_id % len(self._customer_sprites)
        original = self._customer_sprites[sprite_idx]
        
        # Scale to target size
        scaled = pygame.transform.scale(original, size)
        self._cache[cache_key] = scaled
        return scaled

    def get_furniture_sprite(self, furniture_type: str, size: Tuple[int, int] = (48, 48)) -> Optional[pygame.Surface]:
        """Get a furniture sprite for shelf, counter, or poster."""
        if not self._initialized:
            self.init()

        if self._furniture_sheet is None:
            return None

        cache_key = f"furniture_{furniture_type}_{size[0]}x{size[1]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Furniture positions in the 16x16 grid (8 cols x 4 rows)
        furniture_positions = {
            "shelf": (1, 2),      # Blue bookshelf
            "shelf_alt": (1, 1), # Brown bookshelf
            "counter": (7, 0),   # Brown table
            "poster": (0, 2),    # Picture frame
            "chair": (2, 1),     # Chair
            "plant": (4, 1),     # Green plant
            "chest": (0, 1),     # Chest/trunk
        }

        if furniture_type not in furniture_positions:
            return None

        col, row = furniture_positions[furniture_type]
        x = col * 16
        y = row * 16

        # Extract the 16x16 sprite
        sprite = pygame.Surface((16, 16), pygame.SRCALPHA)
        sprite.blit(self._furniture_sheet, (0, 0), pygame.Rect(x, y, 16, 16))

        # Scale to target size
        scaled = pygame.transform.scale(sprite, size)
        self._cache[cache_key] = scaled
        return scaled

    def create_shop_floor_surface(self, grid_size: Tuple[int, int], tile_size: int) -> pygame.Surface:
        """Create a full shop floor surface with tiled dark stone pattern."""
        if not self._initialized:
            self.init()

        width = grid_size[0] * tile_size
        height = grid_size[1] * tile_size
        surface = pygame.Surface((width, height))

        # Fill with a dark base color
        surface.fill((25, 27, 32))

        if self._floor_tiles:
            for y in range(grid_size[1]):
                for x in range(grid_size[0]):
                    # Use a deterministic pattern based on position
                    variant = (x + y * 3) % len(self._floor_tiles)
                    tile = self.get_floor_tile(variant, (tile_size, tile_size))
                    if tile:
                        surface.blit(tile, (x * tile_size, y * tile_size))

        # Add subtle border/wall effect at the top
        wall_rect = pygame.Rect(0, 0, width, tile_size)
        wall_color = (35, 30, 40)
        pygame.draw.rect(surface, wall_color, wall_rect)

        return surface

    def get_random_customer_id(self, rng: random.Random) -> int:
        """Get a random customer sprite ID."""
        if self._customer_sprites:
            return rng.randint(0, len(self._customer_sprites) - 1)
        return 0


# Global shop asset manager instance
_shop_asset_manager: Optional[ShopAssetManager] = None


def get_shop_asset_manager() -> ShopAssetManager:
    """Get the global shop asset manager instance."""
    global _shop_asset_manager
    if _shop_asset_manager is None:
        _shop_asset_manager = ShopAssetManager()
    return _shop_asset_manager
