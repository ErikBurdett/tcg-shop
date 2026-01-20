import os
import pygame

from game.core.app import GameApp
from game.config import WINDOW_SIZE, WINDOW_TITLE


def main() -> None:
    # Suppress ALSA audio errors on Linux systems without proper audio setup
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    app = GameApp(screen)
    app.run()
    pygame.quit()


if __name__ == "__main__":
    main()
