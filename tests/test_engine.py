"""Tests for the PlaybackEngine."""

import asyncio
import gzip
import json
import time
from unittest.mock import Mock

import pytest

from textual_asciinema.engine import PlaybackEngine, Keyframe
from textual_asciinema.parser import CastParser


@pytest.fixture
def mock_terminal():
    """Mock TextualTerminal for testing."""
    terminal = Mock()
    terminal.parser = Mock()
    terminal.terminal_view = Mock()
    terminal.clear_screen = Mock()
    return terminal


@pytest.fixture
def sample_cast_with_offsets(tmp_path):
    """Create a cast file with predictable frame offsets."""
    header = {
        "version": 2,
        "width": 80,
        "height": 24,
        "timestamp": 1234567890,
    }
    frames = [
        [0.0, "o", "Frame 0"],
        [1.0, "o", "Frame 1"],
        [2.0, "o", "Frame 2"],
        [3.0, "o", "Frame 3"],
        [4.0, "o", "Frame 4"],
    ]

    cast_path = tmp_path / "test_offsets.cast"
    with open(cast_path, "w") as f:
        f.write(json.dumps(header) + "\n")
        for frame in frames:
            f.write(json.dumps(frame) + "\n")

    return cast_path


@pytest.fixture
def engine_with_parser(sample_cast_with_offsets, mock_terminal):
    """Create PlaybackEngine with real parser and mock terminal."""
    with CastParser(sample_cast_with_offsets) as parser:
        engine = PlaybackEngine(parser, mock_terminal)
        yield engine


class TestKeyframe:
    """Test the Keyframe class."""

    def test_keyframe_creation(self):
        """Test creating a keyframe with all fields."""
        keyframe = Keyframe(timestamp=1.5, frame_index=10, file_offset=1234, cost=500, creation_time=time.time())

        assert keyframe.timestamp == 1.5
        assert keyframe.frame_index == 10
        assert keyframe.file_offset == 1234
        assert keyframe.cost == 500
        assert isinstance(keyframe.creation_time, float)


class TestPlaybackEngine:
    """Test the PlaybackEngine class."""

    def test_init(self, engine_with_parser):
        """Test engine initialization."""
        engine = engine_with_parser

        assert engine.current_time == 0.0
        assert not engine.is_playing
        assert engine.speed == 1.0
        assert engine._current_file_offset > 0  # Should be at first frame offset
        assert engine._file_handle is not None  # Should have open file handle
        assert isinstance(engine.keyframes, dict)

    def test_set_speed(self, engine_with_parser):
        """Test speed control."""
        engine = engine_with_parser

        engine.set_speed(2.0)
        assert engine.speed == 2.0

        engine.set_speed(0.5)
        assert engine.speed == 0.5

    def test_should_create_keyframe(self, engine_with_parser):
        """Test keyframe creation logic."""
        engine = engine_with_parser

        # No keyframe needed at start
        assert not engine._should_create_keyframe()

        # After interval, should create keyframe
        engine.current_time = 1.5
        assert engine._should_create_keyframe()

        # After creating keyframe, shouldn't create another immediately
        engine.last_keyframe_time = 1.5
        assert not engine._should_create_keyframe()

    def test_create_keyframe(self, engine_with_parser):
        """Test keyframe creation."""
        engine = engine_with_parser
        engine.current_time = 2.0
        engine._current_file_offset = 1234
        engine.current_cost = 500

        # Initially no keyframes
        assert len(engine.keyframes) == 0

        # Create keyframe
        engine._create_keyframe()

        # Should have one keyframe
        assert len(engine.keyframes) == 1
        keyframe = engine.keyframes[2.0]
        assert keyframe.timestamp == 2.0
        assert keyframe.file_offset == 1234
        assert keyframe.cost == 500
        assert engine.last_keyframe_time == 2.0
        assert engine.current_cost == 0  # Should reset

    def test_find_nearest_keyframe(self, engine_with_parser):
        """Test finding nearest keyframe."""
        engine = engine_with_parser

        # Create some keyframes
        engine.keyframes[1.0] = Keyframe(1.0, 0, 100, 50, time.time())
        engine.keyframes[3.0] = Keyframe(3.0, 0, 300, 150, time.time())
        engine.keyframes[5.0] = Keyframe(5.0, 0, 500, 250, time.time())

        # Test finding keyframes
        assert engine._find_nearest_keyframe(0.5) is None  # Before any keyframe
        assert engine._find_nearest_keyframe(1.5).timestamp == 1.0
        assert engine._find_nearest_keyframe(3.0).timestamp == 3.0
        assert engine._find_nearest_keyframe(4.0).timestamp == 3.0
        assert engine._find_nearest_keyframe(10.0).timestamp == 5.0

    def test_get_keyframe_stats(self, engine_with_parser):
        """Test keyframe statistics."""
        engine = engine_with_parser

        # Empty stats
        stats = engine.get_keyframe_stats()
        assert stats["count"] == 0
        assert stats["coverage"] == 0.0
        assert stats["total_cost"] == 0

        # Add some keyframes
        engine.keyframes[1.0] = Keyframe(1.0, 0, 100, 50, time.time())
        engine.keyframes[2.0] = Keyframe(2.0, 0, 200, 75, time.time())

        stats = engine.get_keyframe_stats()
        assert stats["count"] == 2
        assert stats["total_cost"] == 125
        assert stats["avg_cost"] == 62.5
        assert stats["timestamps"] == [1.0, 2.0]

    def test_feed_terminal_data(self, engine_with_parser):
        """Test feeding data to terminal with cost tracking."""
        engine = engine_with_parser

        # Feed some data
        test_data = "Hello World"
        engine._feed_terminal_data(test_data)

        # Should call terminal parser
        engine.terminal.parser.feed.assert_called_once_with(test_data)

        # Should track cost
        assert engine.current_cost == len(test_data)

        # Should update terminal view
        engine.terminal.terminal_view.update_content.assert_called_once()

    def test_consume_next_frame(self, engine_with_parser):
        """Test consuming frames from read-ahead buffer."""
        engine = engine_with_parser

        # Should have first frame ready
        assert engine._next_frame is not None
        assert engine._next_frame.timestamp == 0.0

        # Consume first frame
        frame = engine._consume_next_frame()
        assert frame is not None
        assert frame.timestamp == 0.0
        assert frame.data == "Frame 0"

        # Should have advanced to second frame
        assert engine._next_frame is not None
        assert engine._next_frame.timestamp == 1.0

        # Consume second frame
        frame = engine._consume_next_frame()
        assert frame is not None
        assert frame.timestamp == 1.0
        assert frame.data == "Frame 1"

    @pytest.mark.asyncio
    async def test_play_pause(self, engine_with_parser):
        """Test play/pause functionality."""
        engine = engine_with_parser

        # Initially not playing
        assert not engine.is_playing

        # Start playing
        await engine.play()
        assert engine.is_playing

        # Pause
        await engine.pause()
        assert not engine.is_playing

    @pytest.mark.asyncio
    async def test_toggle_play_pause(self, engine_with_parser):
        """Test toggle play/pause."""
        engine = engine_with_parser

        # Start paused
        assert not engine.is_playing

        # Toggle to play
        await engine.toggle_play_pause()
        assert engine.is_playing

        # Toggle back to pause
        await engine.toggle_play_pause()
        assert not engine.is_playing

    @pytest.mark.asyncio
    async def test_seek_to_with_keyframe(self, engine_with_parser):
        """Test seeking with keyframe optimization."""
        engine = engine_with_parser

        # Create a keyframe at 2.0s
        engine.keyframes[2.0] = Keyframe(2.0, 0, 200, 100, time.time())

        # Mock time update callback
        engine.on_time_update = Mock()

        # Seek to 3.0s (should use keyframe at 2.0s)
        await engine.seek_to(3.0)

        # Should have updated time
        assert engine.current_time == 3.0

        # Should have called terminal reset methods
        engine.terminal.clear_screen.assert_called()
        engine.terminal.parser.feed.assert_called()

        # Should have called time update callback
        engine.on_time_update.assert_called_with(3.0)

    @pytest.mark.asyncio
    async def test_seek_to_bounds(self, engine_with_parser):
        """Test seek bounds checking."""
        engine = engine_with_parser
        duration = engine.parser.duration

        # Seek before start - should clamp to 0
        await engine.seek_to(-1.0)
        assert engine.current_time == 0.0

        # Seek after end - should clamp to duration
        await engine.seek_to(duration + 10.0)
        assert engine.current_time == duration

    def test_reset(self, engine_with_parser):
        """Test engine reset."""
        engine = engine_with_parser

        # Set some state
        engine.current_time = 5.0
        engine.current_cost = 100
        engine.on_time_update = Mock()

        # Reset
        engine.reset()

        # Should reset all state
        assert engine.current_time == 0.0
        assert engine._current_file_offset > 0  # Should be at first frame offset after reset
        assert engine.current_cost == 0

        # Should clear terminal and call time update
        engine.terminal.clear_screen.assert_called()
        engine.on_time_update.assert_called_with(0.0)


class TestPlaybackEngineIntegration:
    """Integration tests with real parser."""

    @pytest.mark.asyncio
    async def test_playback_loop_basic(self, engine_with_parser):
        """Test basic playback loop functionality."""
        engine = engine_with_parser
        engine.on_time_update = Mock()

        # Start playback for a short time
        await engine.play()

        # Let it run briefly
        await asyncio.sleep(0.05)

        # Stop playback
        await engine.pause()

        # Should have advanced time and called updates
        assert engine.current_time >= 0
        assert engine.on_time_update.called

    def test_streaming_with_gzipped_file(self, tmp_path, mock_terminal):
        """Test streaming works with gzipped files."""
        # Create gzipped cast file
        header = {"version": 2, "width": 80, "height": 24}
        frames = [[0.0, "o", "test"], [1.0, "o", "data"]]

        cast_path = tmp_path / "test.cast.gz"
        with gzip.open(cast_path, "wt") as f:
            f.write(json.dumps(header) + "\n")
            for frame in frames:
                f.write(json.dumps(frame) + "\n")

        # Create engine with gzipped file
        with CastParser(cast_path) as parser:
            engine = PlaybackEngine(parser, mock_terminal)

            # Should be able to consume frames
            frame = engine._consume_next_frame()
            assert frame is not None
            assert frame.data == "test"
