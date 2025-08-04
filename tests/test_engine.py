"""Tests for the PlaybackEngine - simplified to test real functionality."""

from unittest.mock import Mock

from textual_asciinema.engine import PlaybackEngine


class TestPlaybackEngine:
    """Test the PlaybackEngine class with minimal mocking."""

    def test_basic_functionality_exists(self):
        """Test that basic engine functionality exists without mocking everything."""
        # Just verify the class can be imported and has expected methods
        assert hasattr(PlaybackEngine, "play")
        assert hasattr(PlaybackEngine, "pause")
        assert hasattr(PlaybackEngine, "seek_to")
        assert hasattr(PlaybackEngine, "set_speed")
        assert hasattr(PlaybackEngine, "reset")

    def test_speed_control(self):
        """Test speed control works."""
        # Create minimal mock terminal
        mock_terminal = Mock()
        mock_terminal.clear_screen = Mock()

        # Create minimal mock parser
        mock_parser = Mock()
        mock_parser.duration = 10.0

        engine = PlaybackEngine(mock_parser, mock_terminal)

        # Test speed changes
        engine.set_speed(2.0)
        assert engine.speed == 2.0

        engine.set_speed(0.5)
        assert engine.speed == 0.5

    def test_basic_state(self):
        """Test basic engine state."""
        mock_terminal = Mock()
        mock_terminal.clear_screen = Mock()
        mock_parser = Mock()
        mock_parser.duration = 10.0

        engine = PlaybackEngine(mock_parser, mock_terminal)

        # Test initial state
        assert engine.current_time == 0.0
        assert not engine.is_playing
        assert engine.speed == 1.0
        assert engine.video_file is not None
