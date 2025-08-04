"""Main asciinema player widget."""

from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual_tty import TextualTerminal

from .parser import CastParser
from .engine import PlaybackEngine
from .controls import PlayerControls


class PlaybackTerminal(TextualTerminal):
    """TextualTerminal configured for playback-only mode."""

    def __init__(self, width: int, height: int, **kwargs):
        super().__init__(**kwargs)
        # Initialize with proper dimensions
        self.resize(width, height)

    async def start_process(self) -> None:
        """Override to prevent starting a shell process."""
        # Don't start any process - we'll feed data manually for playback
        pass


class AsciinemaPlayer(Widget):
    """Main asciinema player widget with terminal display and controls."""

    DEFAULT_CSS = """
    #terminal-scroll {
        border: solid white;
        overflow: hidden;
        width: auto;
        height: auto;
        text-wrap: nowrap;
        scrollbar-size: 0 0;
    }

    #asciinema-terminal {
        overflow: hidden;
        scrollbar-size: 0 0;
        width: auto;
        height: auto;
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

    def __init__(self, cast_path: str | Path, **kwargs):
        super().__init__(**kwargs)
        self.cast_path = Path(cast_path)
        self.parser = CastParser(self.cast_path)
        self.terminal = None
        self.engine = None
        self.controls = None

    def compose(self) -> ComposeResult:
        """Compose the player with terminal and controls."""
        header = self.parser.header

        # Create TextualTerminal for proper ANSI rendering
        self.terminal = PlaybackTerminal(width=header.width, height=header.height, id="asciinema-terminal")

        # Create playback engine with terminal for direct manipulation
        self.engine = PlaybackEngine(self.parser, self.terminal)

        # Create controls
        self.controls = PlayerControls(duration=self.parser.duration, id="asciinema-controls")

        # Wire up controls to engine (need async wrappers)
        self.controls.on_play_pause = self._handle_play_pause
        self.controls.on_seek = self._handle_seek
        self.controls.on_speed_change = self.engine.set_speed

        # Wire up engine to controls for time updates
        self.engine.on_time_update = self._update_display_and_time

        with Vertical():
            with VerticalScroll(id="terminal-scroll"):
                yield self.terminal
            yield self.controls

    def on_mount(self) -> None:
        """Initialize the player when mounted."""
        # Don't start the terminal process - we're in playback mode
        pass

    def _update_display_and_time(self, current_time: float) -> None:
        """Update display terminal from video file and notify controls."""
        # Engine has already triggered the terminal display update

        # Update time controls
        self.controls.update_time(current_time)

    def _handle_play_pause(self) -> None:
        """Handle play/pause button clicks (sync wrapper for async method)."""
        self.run_worker(self.engine.toggle_play_pause())

    def _handle_seek(self, timestamp: float) -> None:
        """Handle seek requests (sync wrapper for async method)."""
        self.run_worker(self.engine.seek_to(timestamp))

    async def play(self) -> None:
        """Start playback."""
        if self.engine:
            await self.engine.play()

    async def pause(self) -> None:
        """Pause playback."""
        if self.engine:
            await self.engine.pause()

    async def seek(self, timestamp: float) -> None:
        """Seek to a specific timestamp."""
        if self.engine:
            await self.engine.seek_to(timestamp)

    def set_speed(self, speed: float) -> None:
        """Set playback speed."""
        if self.engine:
            self.engine.set_speed(speed)
