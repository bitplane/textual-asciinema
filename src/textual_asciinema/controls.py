"""Player controls widget for asciinema player."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar
from textual.reactive import reactive


class PlayerControls(Widget):
    """Control bar with play/pause, time display, and scrubber."""

    current_time = reactive(0.0)
    is_playing = reactive(False)
    speed = reactive(1.0)

    def __init__(self, duration: float, **kwargs):
        super().__init__(**kwargs)
        self.duration = duration
        self.on_play_pause = None
        self.on_seek = None
        self.on_speed_change = None

    def compose(self) -> ComposeResult:
        """Compose the control bar."""
        with Horizontal(id="controls-container"):
            yield Button("⏸️", id="play-pause-btn", variant="primary")
            yield Label(self._format_time_display(), id="time-display")
            yield ProgressBar(total=self.duration, show_eta=False, show_percentage=False, id="timeline-scrubber")
            yield Label(f"{self.speed}x", id="speed-display")

    def _format_time_display(self) -> str:
        """Format the current time and duration for display."""
        current_formatted = self._format_time(self.current_time)
        duration_formatted = self._format_time(self.duration)
        return f"{current_formatted} / {duration_formatted}"

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def watch_current_time(self, new_time: float) -> None:
        """React to time changes."""
        if self.is_mounted:
            try:
                self.query_one("#time-display", Label).update(self._format_time_display())
                progress_bar = self.query_one("#timeline-scrubber", ProgressBar)
                # Reset and set the progress to the current time
                progress_bar.progress = 0
                progress_bar.advance(new_time)
            except Exception:
                # Widget not ready yet
                pass

    def watch_is_playing(self, playing: bool) -> None:
        """React to play state changes."""
        if self.is_mounted:
            try:
                button = self.query_one("#play-pause-btn", Button)
                button.label = "⏸️" if playing else "▶️"
            except Exception:
                # Widget not ready yet
                pass

    def watch_speed(self, new_speed: float) -> None:
        """React to speed changes."""
        if self.is_mounted:
            try:
                self.query_one("#speed-display", Label).update(f"{new_speed}x")
            except Exception:
                # Widget not ready yet
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "play-pause-btn":
            self.is_playing = not self.is_playing
            if self.on_play_pause:
                self.on_play_pause()

    def on_click(self, event) -> None:
        """Handle clicks on the timeline scrubber."""
        if hasattr(event, "widget") and event.widget.id == "timeline-scrubber":
            # Calculate the timestamp based on click position
            progress_bar = event.widget
            if hasattr(event, "offset") and progress_bar.size.width > 0:
                click_ratio = event.offset.x / progress_bar.size.width
                target_time = click_ratio * self.duration

                if self.on_seek:
                    self.on_seek(target_time)

    def update_time(self, current_time: float) -> None:
        """Update the current time (called by playback engine)."""
        self.current_time = current_time

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "space":
            self.is_playing = not self.is_playing
            if self.on_play_pause:
                self.on_play_pause()
            event.prevent_default()
        elif event.key == "left":
            # Seek backward 10 seconds
            target_time = max(0, self.current_time - 10)
            if self.on_seek:
                self.on_seek(target_time)
            event.prevent_default()
        elif event.key == "right":
            # Seek forward 10 seconds
            target_time = min(self.duration, self.current_time + 10)
            if self.on_seek:
                self.on_seek(target_time)
            event.prevent_default()
        elif event.key in ["1", "2", "3", "4", "5"]:
            # Speed control
            speeds = {"1": 0.5, "2": 1.0, "3": 1.5, "4": 2.0, "5": 3.0}
            new_speed = speeds[event.key]
            self.speed = new_speed
            if self.on_speed_change:
                self.on_speed_change(new_speed)
            event.prevent_default()
