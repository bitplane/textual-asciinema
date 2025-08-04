"""Main entry point for textual-asciinema player."""

import argparse
import logging
import sys
from pathlib import Path
from textual.app import App

from .player import AsciinemaPlayer


def setup_file_logging(log_file_path: str):
    """Set up file-based logging."""
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger to write to file
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode="w"),  # Overwrite existing log
        ],
    )

    # Set our specific logger to DEBUG
    logger = logging.getLogger("textual_asciinema.engine")
    logger.setLevel(logging.DEBUG)

    print(f"Debug logging enabled: {log_path}")


class AsciinemaApp(App):
    """Main application for the asciinema player."""

    def __init__(self, cast_path: str):
        super().__init__()
        self.cast_path = cast_path

    def compose(self):
        """Compose the app with the player widget."""
        yield AsciinemaPlayer(self.cast_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Play asciinema cast files in the terminal")
    parser.add_argument("cast_file", help="Path to the cast file to play")
    parser.add_argument("--log-file", help="Enable debug logging to specified file (e.g., ./logs/debug.log)")

    args = parser.parse_args()

    # Set up logging if requested
    if args.log_file:
        setup_file_logging(args.log_file)

    cast_path = Path(args.cast_file)
    if not cast_path.exists():
        print(f"Error: Cast file '{cast_path}' not found")
        sys.exit(1)

    app = AsciinemaApp(str(cast_path))
    app.run()


if __name__ == "__main__":
    main()
