"""Player controls widget for asciinema player."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label
from textual.reactive import reactive
from textual.events import Click, MouseScrollUp, MouseScrollDown


class TimeBar(Widget):
    current_time = reactive(0.0)
    can_focus = False  # Prevent text selection

    def __init__(self, max_time: float, step: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.max_time = max_time
        self.step = step
        self.on_seek = None  # Callback: new time
        self.on_play_pause = None  # Callback: play/pause

    def render(self):
        width = self.size.width
        if width <= 0:
            return ""

        ratio = min(max(self.current_time / self.max_time, 0.0), 1.0) if self.max_time > 0 else 0.0
        full_blocks = int(ratio * width)
        partial = (ratio * width) - full_blocks
        levels = "▏▎▍▌▋▊▉"  # 1/8 to 7/8

        if full_blocks < width:
            # Calculate which partial block to use (0-6)
            partial_idx = min(int(partial * 7), 6) if partial > 0 else -1
            sub = levels[partial_idx] if partial_idx >= 0 else ""
            bar = "█" * full_blocks + sub
            bar += " " * (width - len(bar))
        else:
            bar = "█" * width
        return bar

    def on_click(self, event: Click):
        rel_x = event.x / self.size.width
        new_time = rel_x * self.max_time
        if self.on_seek:
            self.on_seek(new_time)

    def on_mouse_scroll_up(self, event: MouseScrollUp):
        self._seek_delta(+self.step)

    def on_mouse_scroll_down(self, event: MouseScrollDown):
        self._seek_delta(-self.step)

    def _seek_delta(self, delta: float):
        new_time = max(0.0, min(self.current_time + delta, self.max_time))
        if self.on_seek:
            self.on_seek(new_time)


class PlayerControls(Widget):
    """Control bar with play/pause, time display, and scrubber."""

    current_time = reactive(0.0)
    is_playing = reactive(False)
    speed = reactive(1.0)
    can_focus = True

    def __init__(self, duration: float, **kwargs):
        super().__init__(**kwargs)
        self.duration = duration
        self.on_play_pause = None
        self.on_seek = None
        self.on_speed_change = None

    def compose(self) -> ComposeResult:
        """Compose the control bar."""
        with Horizontal(id="controls-container"):
            yield Button("▶", id="play-pause-btn", variant="primary")
            yield Label(self._format_time_display(), id="time-display")
            yield TimeBar(max_time=self.duration, step=1.0, id="timeline-scrubber")
            yield Label(f"{self.speed:.1f}x", id="speed-display")

    def _format_time_display(self) -> str:
        """Format the current time and duration for display."""
        current_formatted = self._format_time(self.current_time)
        duration_formatted = self._format_time(self.duration)
        return f"{current_formatted} / {duration_formatted}"

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def watch_current_time(self, new_time: float) -> None:
        """React to time changes."""
        if self.is_mounted:
            try:
                self.query_one("#time-display", Label).update(self._format_time_display())
                time_bar = self.query_one("#timeline-scrubber", TimeBar)
                time_bar.current_time = new_time
            except Exception:
                # Widget not ready yet
                pass

    def watch_is_playing(self, playing: bool) -> None:
        """React to play state changes."""
        if self.is_mounted:
            try:
                button = self.query_one("#play-pause-btn", Button)
                button.label = "⏸" if playing else "▶"
            except Exception:
                # Widget not ready yet
                pass

    def watch_speed(self, new_speed: float) -> None:
        """React to speed changes."""
        if self.is_mounted:
            try:
                self.query_one("#speed-display", Label).update(f"{new_speed:.1f}x")
            except Exception:
                # Widget not ready yet
                pass

    def on_mount(self) -> None:
        """Connect TimeBar callback when mounted."""
        try:
            time_bar = self.query_one("#timeline-scrubber", TimeBar)
            time_bar.on_seek = self.on_seek
            time_bar.on_play_pause = self._handle_play_pause
        except Exception:
            pass
        # Focus the controls widget to capture keyboard input
        self.focus()

    def _handle_play_pause(self) -> None:
        """Handle play/pause from TimeBar."""
        # If at the end, reset before playing
        if self.current_time >= self.duration - 0.1:  # Near end
            self.current_time = 0.0
            if self.on_seek:
                self.on_seek(0.0)

        self.is_playing = not self.is_playing
        if self.on_play_pause:
            self.on_play_pause()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "play-pause-btn":
            self._handle_play_pause()

    def update_time(self, current_time: float) -> None:
        """Update the current time (called by playback engine)."""
        self.current_time = current_time

    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "space":
            # Play/pause
            self._handle_play_pause()
            event.prevent_default()
        elif event.key == "left":
            # Seek backward 1 second
            target_time = max(0, self.current_time - 1)
            if self.on_seek:
                self.on_seek(target_time)
            event.prevent_default()
        elif event.key == "right":
            # Seek forward 1 second
            target_time = min(self.duration, self.current_time + 1)
            if self.on_seek:
                self.on_seek(target_time)
            event.prevent_default()
        elif event.key in ["minus", "underscore"]:  # minus key (with or without shift)
            # Decrease speed by 0.1
            new_speed = max(0.1, self.speed - 0.1)
            self.speed = new_speed
            if self.on_speed_change:
                self.on_speed_change(new_speed)
            event.prevent_default()
        elif event.key in ["plus", "equals"]:  # plus key (with or without shift)
            # Increase speed by 0.1
            new_speed = min(5.0, self.speed + 0.1)
            self.speed = new_speed
            if self.on_speed_change:
                self.on_speed_change(new_speed)
            event.prevent_default()
