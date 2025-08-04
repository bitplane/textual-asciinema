"""Tests for player controls."""

from unittest.mock import Mock
import pytest
from textual.app import App
from textual.events import MouseScrollDown, MouseScrollUp

from textual_asciinema.controls import TimeBar, PlayerControls


@pytest.fixture
async def test_app():
    """Create a test app for widget testing."""

    class TestApp(App):
        def compose(self):
            yield TimeBar(max_time=100.0)

    app = TestApp()
    async with app.run_test() as pilot:
        yield app, pilot


class TestTimeBar:
    """Test the TimeBar widget."""

    def test_init(self):
        """Test TimeBar initialization."""
        timebar = TimeBar(max_time=120.0, step=5.0)

        assert timebar.max_time == 120.0
        assert timebar.step == 5.0
        assert timebar.current_time == 0.0
        assert timebar.on_seek is None
        assert timebar.on_play_pause is None
        assert not timebar.can_focus

    def test_on_click_seek(self):
        """Test click-to-seek functionality."""
        timebar = TimeBar(max_time=100.0)
        timebar.on_seek = Mock()

        # Test the seek delta function directly (core logic)
        timebar._seek_delta(10.0)
        timebar.on_seek.assert_called_once_with(10.0)

    def test_on_click_no_callback(self):
        """Test click when no callback is set."""
        timebar = TimeBar(max_time=100.0)
        # on_seek is None

        # Should not raise exception when calling seek delta
        timebar._seek_delta(10.0)

    def test_mouse_scroll_up(self):
        """Test mouse scroll up (forward seek)."""
        timebar = TimeBar(max_time=100.0, step=10.0)
        timebar.current_time = 50.0
        timebar.on_seek = Mock()

        scroll_event = Mock(spec=MouseScrollUp)
        timebar.on_mouse_scroll_up(scroll_event)

        # Should seek forward by step amount
        timebar.on_seek.assert_called_once_with(60.0)

    def test_mouse_scroll_down(self):
        """Test mouse scroll down (backward seek)."""
        timebar = TimeBar(max_time=100.0, step=10.0)
        timebar.current_time = 50.0
        timebar.on_seek = Mock()

        scroll_event = Mock(spec=MouseScrollDown)
        timebar.on_mouse_scroll_down(scroll_event)

        # Should seek backward by step amount
        timebar.on_seek.assert_called_once_with(40.0)

    def test_seek_delta_bounds(self):
        """Test seek delta respects bounds."""
        timebar = TimeBar(max_time=100.0)
        timebar.on_seek = Mock()

        # Test lower bound
        timebar.current_time = 5.0
        timebar._seek_delta(-10.0)  # Would go to -5, should clamp to 0
        timebar.on_seek.assert_called_with(0.0)

        # Test upper bound
        timebar.current_time = 95.0
        timebar._seek_delta(10.0)  # Would go to 105, should clamp to 100
        timebar.on_seek.assert_called_with(100.0)


class TestPlayerControls:
    """Test the PlayerControls widget."""

    def test_init(self):
        """Test PlayerControls initialization."""
        controls = PlayerControls(duration=120.0)

        assert controls.duration == 120.0
        assert controls.current_time == 0.0
        assert not controls.is_playing
        assert controls.speed == 1.0
        assert controls.can_focus
        assert controls.on_play_pause is None
        assert controls.on_seek is None
        assert controls.on_speed_change is None

    def test_format_time_minutes(self):
        """Test time formatting for minutes/seconds."""
        controls = PlayerControls(duration=120.0)

        assert controls._format_time(0) == "00:00"
        assert controls._format_time(30) == "00:30"
        assert controls._format_time(90) == "01:30"
        assert controls._format_time(125) == "02:05"

    def test_format_time_hours(self):
        """Test time formatting with hours."""
        controls = PlayerControls(duration=7200.0)

        assert controls._format_time(3600) == "1:00:00"
        assert controls._format_time(3661) == "1:01:01"
        assert controls._format_time(7325) == "2:02:05"

    def test_format_time_display(self):
        """Test complete time display formatting."""
        controls = PlayerControls(duration=125.0)
        controls.current_time = 30.0

        result = controls._format_time_display()
        assert result == "00:30 / 02:05"

    def test_watch_current_time(self):
        """Test current time watcher doesn't crash."""
        controls = PlayerControls(duration=120.0)

        # Should not raise exception when not mounted
        controls.watch_current_time(45.0)

    def test_watch_is_playing(self):
        """Test play state watcher doesn't crash."""
        controls = PlayerControls(duration=120.0)

        # Should not raise exception when not mounted
        controls.watch_is_playing(True)
        controls.watch_is_playing(False)

    def test_watch_speed(self):
        """Test speed watcher doesn't crash."""
        controls = PlayerControls(duration=120.0)

        # Should not raise exception when not mounted
        controls.watch_speed(2.5)

    def test_handle_play_pause_normal(self):
        """Test play/pause handling in normal case."""
        controls = PlayerControls(duration=120.0)
        controls.current_time = 30.0
        controls.is_playing = False
        controls.on_play_pause = Mock()

        controls._handle_play_pause()

        # Should toggle play state and call callback
        assert controls.is_playing
        controls.on_play_pause.assert_called_once()

    def test_handle_play_pause_at_end(self):
        """Test play/pause when at end of recording."""
        controls = PlayerControls(duration=120.0)
        controls.current_time = 119.95  # Near end
        controls.is_playing = False
        controls.on_seek = Mock()
        controls.on_play_pause = Mock()

        controls._handle_play_pause()

        # Should reset to beginning, then start playing
        controls.on_seek.assert_called_once_with(0.0)
        assert controls.current_time == 0.0
        assert controls.is_playing
        controls.on_play_pause.assert_called_once()

    def test_update_time(self):
        """Test update_time method."""
        controls = PlayerControls(duration=120.0)

        controls.update_time(45.0)

        assert controls.current_time == 45.0

    def test_keyboard_space(self):
        """Test space key for play/pause."""
        controls = PlayerControls(duration=120.0)
        controls.on_play_pause = Mock()

        event = Mock()
        event.key = "space"

        controls.on_key(event)

        event.prevent_default.assert_called_once()
        # _handle_play_pause should be called, which calls callback
        assert controls.is_playing  # Toggled from False

    def test_keyboard_left_arrow(self):
        """Test left arrow key for backward seek."""
        controls = PlayerControls(duration=120.0)
        controls.current_time = 30.0
        controls.on_seek = Mock()

        event = Mock()
        event.key = "left"

        controls.on_key(event)

        event.prevent_default.assert_called_once()
        controls.on_seek.assert_called_once_with(29.0)  # -1 second

    def test_keyboard_right_arrow(self):
        """Test right arrow key for forward seek."""
        controls = PlayerControls(duration=120.0)
        controls.current_time = 30.0
        controls.on_seek = Mock()

        event = Mock()
        event.key = "right"

        controls.on_key(event)

        event.prevent_default.assert_called_once()
        controls.on_seek.assert_called_once_with(31.0)  # +1 second

    def test_keyboard_arrows_bounds(self):
        """Test arrow keys respect time bounds."""
        controls = PlayerControls(duration=120.0)
        controls.on_seek = Mock()

        # Test left arrow at beginning
        controls.current_time = 0.0
        event = Mock()
        event.key = "left"
        controls.on_key(event)
        controls.on_seek.assert_called_with(0.0)  # Should not go below 0

        # Test right arrow at end
        controls.current_time = 120.0
        event.key = "right"
        controls.on_key(event)
        controls.on_seek.assert_called_with(120.0)  # Should not go above duration

    def test_keyboard_speed_decrease(self):
        """Test minus key for speed decrease."""
        controls = PlayerControls(duration=120.0)
        controls.speed = 1.0
        controls.on_speed_change = Mock()

        event = Mock()
        event.key = "minus"

        controls.on_key(event)

        event.prevent_default.assert_called_once()
        assert controls.speed == 0.9
        controls.on_speed_change.assert_called_once_with(0.9)

    def test_keyboard_speed_increase(self):
        """Test plus key for speed increase."""
        controls = PlayerControls(duration=120.0)
        controls.speed = 1.0
        controls.on_speed_change = Mock()

        event = Mock()
        event.key = "plus"

        controls.on_key(event)

        event.prevent_default.assert_called_once()
        assert controls.speed == 1.1
        controls.on_speed_change.assert_called_once_with(1.1)

    def test_keyboard_speed_bounds(self):
        """Test speed change bounds."""
        controls = PlayerControls(duration=120.0)
        controls.on_speed_change = Mock()

        # Test minimum speed bound
        controls.speed = 0.1
        event = Mock()
        event.key = "minus"
        controls.on_key(event)
        assert controls.speed == 0.1  # Should not go below 0.1

        # Test maximum speed bound
        controls.speed = 5.0
        event.key = "plus"
        controls.on_key(event)
        assert controls.speed == 5.0  # Should not go above 5.0

    def test_keyboard_underscore_key(self):
        """Test underscore key (shift+minus) for speed decrease."""
        controls = PlayerControls(duration=120.0)
        controls.speed = 1.0
        controls.on_speed_change = Mock()

        event = Mock()
        event.key = "underscore"

        controls.on_key(event)

        assert controls.speed == 0.9

    def test_keyboard_equals_key(self):
        """Test equals key for speed increase."""
        controls = PlayerControls(duration=120.0)
        controls.speed = 1.0
        controls.on_speed_change = Mock()

        event = Mock()
        event.key = "equals"

        controls.on_key(event)

        assert controls.speed == 1.1

    def test_keyboard_unknown_key(self):
        """Test unknown key does nothing."""
        controls = PlayerControls(duration=120.0)
        controls.on_play_pause = Mock()
        controls.on_seek = Mock()
        controls.on_speed_change = Mock()

        event = Mock()
        event.key = "unknown"

        controls.on_key(event)

        # Should not call any callbacks
        controls.on_play_pause.assert_not_called()
        controls.on_seek.assert_not_called()
        controls.on_speed_change.assert_not_called()
