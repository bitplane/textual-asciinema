"""Main entry point for textual-asciinema player."""

import sys
from pathlib import Path
from textual.app import App

from .player import AsciinemaPlayer


class AsciinemaApp(App):
    """Main application for the asciinema player."""

    CSS_PATH = Path(__file__).parent / "player.tcss"

    def __init__(self, cast_path: str):
        super().__init__()
        self.cast_path = cast_path

    def compose(self):
        """Compose the app with the player widget."""
        yield AsciinemaPlayer(self.cast_path)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: textual-asciinema <cast_file>")
        sys.exit(1)

    cast_path = sys.argv[1]
    if not Path(cast_path).exists():
        print(f"Error: Cast file '{cast_path}' not found")
        sys.exit(1)

    app = AsciinemaApp(cast_path)
    app.run()


if __name__ == "__main__":
    main()
