#!/home/gaz/src/textual/textual-asciinema/.venv/bin/python
"""Demo application for the asciinema player."""

import sys
from pathlib import Path
from textual.app import App

from src.textual_asciinema import AsciinemaPlayer


class AsciinemaDemo(App):
    """Demo app for the asciinema player."""

    CSS_PATH = "player.tcss"

    def __init__(self, cast_path: str):
        super().__init__()
        self.cast_path = cast_path

    def compose(self):
        yield AsciinemaPlayer(self.cast_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python demo.py <cast_file>")
        sys.exit(1)

    cast_file = sys.argv[1]
    if not Path(cast_file).exists():
        print(f"Cast file not found: {cast_file}")
        sys.exit(1)

    app = AsciinemaDemo(cast_file)
    app.run()
