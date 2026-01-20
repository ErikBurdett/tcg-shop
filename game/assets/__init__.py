"""Asset management for card sprites."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional

import pygame


# Asset directory path
ASSET_DIR = Path(__file__).parent


class SpriteSheet:
    """Loads and extracts sprites from a tileset image."""

    def __init__(self, path: Path, tile_size: Tuple[int, int]) -> None:
        self.path = path
        self.tile_size = tile_size
        self._surface: Optional[pygame.Surface] = None

    def _load(self) -> pygame.Surface:
        if self._surface is None:
            self._surface = pygame.image.load(str(self.path)).convert_alpha()
        return self._surface

    def get_sprite(self, col: int, row: int) -> pygame.Surface:
        """Extract a single sprite from the tileset at (col, row) position."""
        sheet = self._load()
        tw, th = self.tile_size
        rect = pygame.Rect(col * tw, row * th, tw, th)
        sprite = pygame.Surface((tw, th), pygame.SRCALPHA)
        sprite.blit(sheet, (0, 0), rect)
        return sprite

    def get_sprite_scaled(self, col: int, row: int, target_size: Tuple[int, int]) -> pygame.Surface:
        """Extract and scale a sprite to target size."""
        sprite = self.get_sprite(col, row)
        return pygame.transform.scale(sprite, target_size)


class CardAssetManager:
    """Manages card sprite assets for all card types."""

    # Tiny Creatures individual tile mappings (tile numbers 1-180)
    # Row 0 (tiles 1-12): Knights/warriors
    # Row 3 (tiles 37-48): Slimes/elementals
    # Row 4 (tiles 49-60): Golems/large monsters
    
    # Sproutling (common) - use slime/elemental tiles (37-48)
    SPROUTLING_TILES = [37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48]
    
    # River Guard (uncommon) - use knight/warrior tiles (1-8)
    RIVER_GUARD_TILES = [1, 2, 3, 4, 5, 6, 7, 8]
    
    # Dungeon Crawl Utumno positions (32x32 grid)
    # The tileset is 2048x1536 pixels = 64 cols x 48 rows
    # Manually verified creature positions
    DUNGEON_CRAWL_MAPPING = {
        # Skyblade (rare) - warrior/beast creatures
        "skyblade_1": (3, 2),    # Werewolf beast
        "skyblade_2": (10, 1),   # Knight with shield
        "skyblade_3": (6, 1),    # Warrior with axe
        "skyblade_4": (11, 1),   # Blue beast
        "skyblade_5": (12, 1),   # Orc warrior
        
        # Voidcaller (epic) - dark/demonic creatures
        "voidcaller_1": (15, 2),  # Dark demon beast
        "voidcaller_2": (17, 2),  # Red demon
        "voidcaller_3": (4, 2),   # Dark mage
        
        # Ancient Wyrm (legendary) - dragons
        "ancient_wyrm_1": (7, 2),   # Green dragon
        "ancient_wyrm_2": (8, 2),   # Green dragon variant
    }

    def __init__(self) -> None:
        self._dungeon_crawl: Optional[SpriteSheet] = None
        self._tile_cache: Dict[int, pygame.Surface] = {}
        self._sprite_cache: Dict[str, pygame.Surface] = {}
        self._initialized = False

    def init(self) -> None:
        """Initialize spritesheets. Call after pygame.init()."""
        if self._initialized:
            return
            
        dungeon_path = ASSET_DIR / "dungeon-crawl-utumno.png"
        if dungeon_path.exists():
            self._dungeon_crawl = SpriteSheet(dungeon_path, (32, 32))
            
        self._initialized = True

    def _load_tile(self, tile_num: int) -> Optional[pygame.Surface]:
        """Load an individual tile from the Tiny Creatures pack."""
        if tile_num in self._tile_cache:
            return self._tile_cache[tile_num]
            
        tile_path = ASSET_DIR / "tiny-creatures" / "Tiles" / f"tile_{tile_num:04d}.png"
        if tile_path.exists():
            surface = pygame.image.load(str(tile_path)).convert_alpha()
            self._tile_cache[tile_num] = surface
            return surface
        return None

    def get_card_sprite(self, card_id: str, target_size: Tuple[int, int] = (64, 64)) -> Optional[pygame.Surface]:
        """Get the sprite for a card, scaled to target_size."""
        if not self._initialized:
            self.init()
            
        cache_key = f"{card_id}_{target_size[0]}x{target_size[1]}"
        if cache_key in self._sprite_cache:
            return self._sprite_cache[cache_key]
        
        sprite = self._load_card_sprite(card_id, target_size)
        if sprite:
            self._sprite_cache[cache_key] = sprite
        return sprite

    def _load_card_sprite(self, card_id: str, target_size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """Load and scale a sprite for the given card_id."""
        # card_id format: c1-c12 (common), u1-u8 (uncommon), r1-r5 (rare), e1-e3 (epic), l1-l2 (legendary)
        
        if card_id.startswith("c"):
            # Common - Sproutling (use individual tiles)
            idx = int(card_id[1:]) - 1  # Convert to 0-indexed
            if 0 <= idx < len(self.SPROUTLING_TILES):
                tile_num = self.SPROUTLING_TILES[idx]
                tile = self._load_tile(tile_num)
                if tile:
                    return pygame.transform.scale(tile, target_size)
                
        elif card_id.startswith("u"):
            # Uncommon - River Guard (use individual tiles)
            idx = int(card_id[1:]) - 1  # Convert to 0-indexed
            if 0 <= idx < len(self.RIVER_GUARD_TILES):
                tile_num = self.RIVER_GUARD_TILES[idx]
                tile = self._load_tile(tile_num)
                if tile:
                    return pygame.transform.scale(tile, target_size)
                
        elif card_id.startswith("r"):
            # Rare - Skyblade (use Dungeon Crawl)
            idx = int(card_id[1:])
            key = f"skyblade_{idx}"
            if key in self.DUNGEON_CRAWL_MAPPING and self._dungeon_crawl:
                col, row = self.DUNGEON_CRAWL_MAPPING[key]
                return self._dungeon_crawl.get_sprite_scaled(col, row, target_size)
                
        elif card_id.startswith("e"):
            # Epic - Voidcaller (use Dungeon Crawl)
            idx = int(card_id[1:])
            key = f"voidcaller_{idx}"
            if key in self.DUNGEON_CRAWL_MAPPING and self._dungeon_crawl:
                col, row = self.DUNGEON_CRAWL_MAPPING[key]
                return self._dungeon_crawl.get_sprite_scaled(col, row, target_size)
                
        elif card_id.startswith("l"):
            # Legendary - Ancient Wyrm (use Dungeon Crawl)
            idx = int(card_id[1:])
            key = f"ancient_wyrm_{idx}"
            if key in self.DUNGEON_CRAWL_MAPPING and self._dungeon_crawl:
                col, row = self.DUNGEON_CRAWL_MAPPING[key]
                return self._dungeon_crawl.get_sprite_scaled(col, row, target_size)
        
        return None

    def create_card_background(self, rarity: str, size: Tuple[int, int]) -> pygame.Surface:
        """Create a dark fantasy background for the card based on rarity."""
        surface = pygame.Surface(size, pygame.SRCALPHA)
        
        # Dark fantasy color schemes per rarity (top color, bottom color)
        colors = {
            "common": ((30, 32, 38), (50, 55, 62)),
            "uncommon": ((25, 42, 38), (40, 62, 55)),
            "rare": ((28, 32, 52), (45, 50, 75)),
            "epic": ((42, 25, 48), (65, 40, 70)),
            "legendary": ((48, 38, 22), (72, 58, 32)),
        }
        
        dark, light = colors.get(rarity, colors["common"])
        
        # Create vertical gradient background
        for y in range(size[1]):
            progress = y / max(size[1] - 1, 1)
            r = int(dark[0] + (light[0] - dark[0]) * progress)
            g = int(dark[1] + (light[1] - dark[1]) * progress)
            b = int(dark[2] + (light[2] - dark[2]) * progress)
            pygame.draw.line(surface, (r, g, b), (0, y), (size[0], y))
        
        # Add subtle vignette effect for dark fantasy feel
        vignette = pygame.Surface(size, pygame.SRCALPHA)
        center_x, center_y = size[0] // 2, size[1] // 2
        max_dist = ((size[0] / 2) ** 2 + (size[1] / 2) ** 2) ** 0.5
        
        for y in range(0, size[1], 2):
            for x in range(0, size[0], 2):
                dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                alpha = int(min(30, (dist / max_dist) * 50))
                if alpha > 0:
                    pygame.draw.rect(vignette, (0, 0, 0, alpha), (x, y, 2, 2))
        
        surface.blit(vignette, (0, 0))
        
        return surface


# Global asset manager instance
_asset_manager: Optional[CardAssetManager] = None


def get_asset_manager() -> CardAssetManager:
    """Get the global asset manager instance."""
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = CardAssetManager()
    return _asset_manager
