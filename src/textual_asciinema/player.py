"""Main asciinema player widget."""

from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual_tty import TextualTerminal

from .parser import CastParser
from .engine import PlaybackEngine
from .controls import PlayerControls


class PlaybackTerminal(TextualTerminal):
    """TextualTerminal configured for playback-only mode."""

    async def on_mount(self) -> None:
        """Override to prevent starting a shell process."""
        # Initialize the terminal view without starting a process
        pass


class AsciinemaPlayer(Widget):
    """Main asciinema player widget with terminal display and controls."""

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

        # Create terminal with cast dimensions (no process for playback)
        self.terminal = PlaybackTerminal(width=header.width, height=header.height, id="asciinema-terminal")

        # Create playback engine
        self.engine = PlaybackEngine(self.parser, self.terminal)

        # Create controls
        self.controls = PlayerControls(duration=self.parser.duration, id="asciinema-controls")

        # Wire up controls to engine
        self.controls.on_play_pause = self.engine.toggle_play_pause
        self.controls.on_seek = self.engine.seek_to
        self.controls.on_speed_change = self.engine.set_speed

        # Wire up engine to controls for time updates
        self.engine.on_time_update = self.controls.update_time

        with Vertical():
            yield self.terminal
            yield self.controls

    def on_mount(self) -> None:
        """Initialize the player when mounted."""
        # Don't start the terminal process - we're in playback mode
        pass

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
