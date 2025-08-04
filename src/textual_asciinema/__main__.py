"""Main entry point for textual-asciinema player."""

import sys
from pathlib import Path
from textual.app import App

from .player import AsciinemaPlayer


class AsciinemaApp(App):
    """Main application for the asciinema player."""

    DEFAULT_CSS = """
    #asciinema-terminal {
        border: solid white;
        overflow: hidden;
    }

    #asciinema-terminal TerminalScrollView {
        overflow: hidden;
        scrollbar-size: 0 0;
    }

    #asciinema-controls {
        height: 3;
        dock: bottom;
    }

    #controls-container {
        height: 3;
        width: 100%;
    }

    #play-pause-btn {
        width: 3;
        min-width: 3;
        border: none;
        padding: 0;
        background: transparent;
    }

    #play-pause-btn:focus {
        border: none;
        background: transparent;
        text-style: none;
    }

    #play-pause-btn:hover {
        background: transparent;
    }

    #time-display {
        width: 15;
        text-align: center;
    }

    #timeline-scrubber {
        width: 1fr;
        height: 1;
        background: $surface;
        color: $primary;
        text-style: none;
    }

    #timeline-scrubber:hover {
        background: $surface-lighten-1;
    }

    #speed-display {
        width: auto;
        text-align: center;
        padding: 0 0 0 1;
        overflow: hidden;
    }
    """

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
