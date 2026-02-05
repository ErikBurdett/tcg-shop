import os
import pygame

from game.core.app import GameApp
from game.config import WINDOW_SIZE, WINDOW_TITLE


def main() -> None:
    # Suppress ALSA audio errors on Linux systems without proper audio setup
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    # Start at "max" window size (desktop resolution) by default.
    # This keeps the window resizable while filling the available screen.
    info = pygame.display.Info()
    max_size = (info.current_w or WINDOW_SIZE[0], info.current_h or WINDOW_SIZE[1])
    screen = pygame.display.set_mode(max_size, pygame.RESIZABLE)
    app = GameApp(screen)
    app.run()
    pygame.quit()


if __name__ == "__main__":
    main()
