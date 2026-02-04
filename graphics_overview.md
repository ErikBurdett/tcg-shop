# Rendering & Asset Pipeline (TCG Shop Simulator)

This document focuses on how rendering and assets work in this project. It is intended as a technical reference for anyone adding sprites, card art, or new sets.

## Rendering Overview
Rendering is immediate-mode: each frame clears the screen and draws layered surfaces in a fixed order. The shop scene is the primary rendering surface; UI elements (panels/buttons) are drawn on top.

### Draw Order (Shop Scene)
The shop scene draws the floor, objects, customers, and then UI elements. This ordering keeps gameplay visuals beneath the UI.
```814:836:game/scenes/shop_scene.py
    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self._draw_grid(surface)
        self._draw_objects(surface)
        self._draw_customers(surface)
        self.order_panel.draw(surface, self.theme)
        if self.current_tab == "manage":
            self.stock_panel.draw(surface, self.theme)
            self.inventory_panel.draw(surface, self.theme)
            if self.manage_card_book_open:
                self.book_panel.draw(surface, self.theme)
        if self.current_tab == "deck":
            self.book_panel.draw(surface, self.theme)
            self.deck_panel.draw(surface, self.theme)
        for button in self.buttons:
            button.draw(surface, self.theme)
        for tb in self.tab_buttons:
            tb.draw(surface, self.theme)
        self._draw_status(surface)
        if self.current_tab == "packs":
            self._draw_packs(surface)
        if self.current_tab == "manage":
            self._draw_manage(surface)
```

### Pack Reveal Rendering
Pack cards are rendered with a gradient background, a centered sprite, and a rarity border with a subtle glow.
```68:114:game/scenes/pack_open_scene.py
    def _draw_cards(self, surface: pygame.Surface) -> None:
        start_x = 100
        y = 160
        asset_mgr = get_asset_manager()
        
        for idx, card_id in enumerate(self.revealed_cards):
            rect = pygame.Rect(start_x + idx * 200, y, 160, 220)
            if idx < self.reveal_index:
                card = CARD_INDEX[card_id]
                
                # Draw card background with dark fantasy gradient
                bg = asset_mgr.create_card_background(card.rarity, (rect.width, rect.height))
                surface.blit(bg, rect.topleft)
                
                # Draw card sprite centered in upper portion
                sprite = asset_mgr.get_card_sprite(card_id, (96, 96))
                if sprite:
                    sprite_x = rect.x + (rect.width - 96) // 2
                    sprite_y = rect.y + 30
                    surface.blit(sprite, (sprite_x, sprite_y))
                
                # Draw rarity border
                rarity_color = self._rarity_color(card.rarity)
                draw_glow_border(surface, rect, rarity_color, border_width=3, glow_radius=5, glow_alpha=90)
                
                # Draw card name at top
                id_text = self.theme.font_small.render(card.card_id.upper(), True, self.theme.colors.muted)
                surface.blit(id_text, (rect.x + 8, rect.y + 6))
```

### Rarity Glow Utility
The glow border helper lives in `game/ui/effects.py` and is used across multiple card renderers.
```6:37:game/ui/effects.py
def draw_glow_border(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    border_width: int = 2,
    glow_radius: int = 4,
    glow_alpha: int = 80,
    border_radius: int = 0,
) -> None:
    if glow_radius > 0 and glow_alpha > 0:
        gw = rect.width + glow_radius * 2
        gh = rect.height + glow_radius * 2
        glow = pygame.Surface((gw, gh), pygame.SRCALPHA)
        for i in range(glow_radius, 0, -1):
            a = int(glow_alpha * (i / glow_radius) ** 2)
            ring_rect = pygame.Rect(glow_radius - i, glow_radius - i, rect.width + i * 2, rect.height + i * 2)
            pygame.draw.rect(glow, (color[0], color[1], color[2], a), ring_rect, width=1)
        surface.blit(glow, (rect.x - glow_radius, rect.y - glow_radius))
    pygame.draw.rect(surface, color, rect, width=border_width, border_radius=border_radius)
```

## Sprite Methodology
Sprites are loaded from tilesheets or from individual tile files and cached in asset managers. The project uses a mix of:
- Tilesheets (for dungeon/monster art)
- Individual tiles (for tiny creatures)
- Scaled sprites for the shop environment

### Tilesheet Extraction (Generic)
The `SpriteSheet` helper extracts a tile at `(col, row)` and optionally scales it.
```14:39:game/assets/__init__.py
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
        sheet = self._load()
        tw, th = self.tile_size
        rect = pygame.Rect(col * tw, row * th, tw, th)
        sprite = pygame.Surface((tw, th), pygame.SRCALPHA)
        sprite.blit(sheet, (0, 0), rect)
        return sprite

    def get_sprite_scaled(self, col: int, row: int, target_size: Tuple[int, int]) -> pygame.Surface:
        sprite = self.get_sprite(col, row)
        return pygame.transform.scale(sprite, target_size)
```

### Card Art Mapping
Card art uses a mix of individual tile PNGs and a larger tilesheet. Each card id maps to a tile source.
```42:166:game/assets/__init__.py
class CardAssetManager:
    """Manages card sprite assets for all card types."""

    SPROUTLING_TILES = [37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48]
    RIVER_GUARD_TILES = [1, 2, 3, 4, 5, 6, 7, 8]
    DUNGEON_CRAWL_MAPPING = {
        "skyblade_1": (3, 2),
        "skyblade_2": (10, 1),
        "skyblade_3": (6, 1),
        "skyblade_4": (11, 1),
        "skyblade_5": (12, 1),
        "voidcaller_1": (15, 2),
        "voidcaller_2": (17, 2),
        "voidcaller_3": (4, 2),
        "ancient_wyrm_1": (7, 2),
        "ancient_wyrm_2": (8, 2),
    }

    def get_card_sprite(self, card_id: str, target_size: Tuple[int, int] = (64, 64)) -> Optional[pygame.Surface]:
        if not self._initialized:
            self.init()
        cache_key = f"{card_id}_{target_size[0]}x{target_size[1]}"
        if cache_key in self._sprite_cache:
            return self._sprite_cache[cache_key]
        sprite = self._load_card_sprite(card_id, target_size)
        if sprite:
            self._sprite_cache[cache_key] = sprite
        return sprite
```

### Shop Floor Tiling
Shop floor is pre-rendered as a tiled surface to reduce per-frame work.
```127:153:game/assets/shop/__init__.py
    def create_shop_floor_surface(self, grid_size: Tuple[int, int], tile_size: int) -> pygame.Surface:
        if not self._initialized:
            self.init()
        width = grid_size[0] * tile_size
        height = grid_size[1] * tile_size
        surface = pygame.Surface((width, height))
        surface.fill((25, 27, 32))
        if self._floor_tiles:
            for y in range(grid_size[1]):
                for x in range(grid_size[0]):
                    variant = (x + y * 3) % len(self._floor_tiles)
                    tile = self.get_floor_tile(variant, (tile_size, tile_size))
                    if tile:
                        surface.blit(tile, (x * tile_size, y * tile_size))
        wall_rect = pygame.Rect(0, 0, width, tile_size)
        wall_color = (35, 30, 40)
        pygame.draw.rect(surface, wall_color, wall_rect)
        return surface
```

## Asset Sizes & Structure
### Global Pixel Sizes
- Window: `1600x900` (resizable)
- Base resolution: `1600x900`
- Shop grid tiles: `48x48`

### Card Art Sizes
- Card sprites: `64x64` (shop), `96x96` (pack reveal)
- Card background: `160x220` in pack reveal

### Shop Art Sizes
- Floor tiles: scaled to `48x48`
- Furniture sprites: source `16x16`, scaled to `48x48`
- Customer sprites: source `32x32`, scaled to `40x40`

### Asset Layout
- `game/assets/tiny-creatures/Tiles/tile_####.png` (individual tiles)
- `game/assets/dungeon-crawl-utumno.png` (32x32 tilesheet)
- `game/assets/shop/tiles/floor_#.png`
- `game/assets/shop/tiles/customer_#.png`
- `game/assets/shop/furniture.png`

## Best Practices (New Assets)
- Use power-of-two sprite sizes where possible (16, 32, 64).
- Keep pixel-perfect edges: no anti-aliasing or subpixel alignment.
- Export with transparent backgrounds (PNG).
- Avoid scaling each frame; pre-scale and cache.
- Keep tile sizes consistent per sheet.
- Name tiles predictably (`tile_####.png`), and document mappings.

## Best Practices (New Card Sets)
1. Add new `CardDef` entries in `game/cards/card_defs.py`.
2. Add art mappings in `game/assets/__init__.py`:
   - add tilesheet coordinates or tile ids
   - update mapping keys (e.g., `newset_1`, `newset_2`)
3. Add assets to `game/assets/` and ensure dimensions match.
4. Validate pack generation distribution in `game/cards/pack.py`.
5. Update README card-set list and stats.

## What Still Needs Work (for a fully immersive pixel game)
- Animation system for sprites (idle/walk/interaction).
- FX pipeline for pack openings, purchases, and combat.
- Camera/viewport support for larger shops.
- Asset atlas builder and texture packing.
- Audio engine for ambient loops, UI feedback, and SFX.
- Input rebinding + accessibility controls.

## Learning Resources
- Pygame Docs: https://www.pygame.org/docs/
- Pixel Art Palettes/Guides: https://lospec.com/
- Game Loop Patterns: https://gameprogrammingpatterns.com/game-loop.html
