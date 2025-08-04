"""Tests for the main AsciinemaPlayer widget."""

import gzip
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from textual_asciinema.player import AsciinemaPlayer, PlaybackTerminal
from textual_asciinema.parser import CastParser


@pytest.fixture
def sample_cast_file(tmp_path):
    """Create a sample cast file for testing."""
    header = {
        "version": 2,
        "width": 80,
        "height": 24,
        "timestamp": 1234567890,
        "title": "Test Recording",
    }
    frames = [
        [0.0, "o", "Hello "],
        [1.0, "o", "World!"],
        [2.0, "o", "\r\n"],
    ]

    cast_path = tmp_path / "test.cast"
    with open(cast_path, "w") as f:
        f.write(json.dumps(header) + "\n")
        for frame in frames:
            f.write(json.dumps(frame) + "\n")

    return cast_path


@pytest.fixture
def gzipped_cast_file(tmp_path):
    """Create a gzipped cast file for testing."""
    header = {
        "version": 2,
        "width": 120,
        "height": 30,
        "timestamp": 1234567890,
        "title": "Gzipped Test Recording",
    }
    frames = [
        [0.0, "o", "Compressed "],
        [1.5, "o", "data!"],
    ]

    cast_path = tmp_path / "test.cast.gz"
    with gzip.open(cast_path, "wt") as f:
        f.write(json.dumps(header) + "\n")
        for frame in frames:
            f.write(json.dumps(frame) + "\n")

    return cast_path


class TestPlaybackTerminal:
    """Test the PlaybackTerminal widget."""

    @pytest.mark.asyncio
    async def test_start_process_override(self):
        """Test that start_process doesn't actually start a process."""
        terminal = PlaybackTerminal(width=80, height=24)

        # Should not raise exception and not start any process
        await terminal.start_process()

        # Should complete without error
        assert True

    @pytest.mark.asyncio
    async def test_on_mount_no_process(self):
        """Test terminal mounts without starting process."""
        terminal = PlaybackTerminal(width=80, height=24)

        # Mock the super().on_mount() to avoid starting actual terminal
        with patch("textual_asciinema.player.TextualTerminal.on_mount") as mock_super:
            mock_super.side_effect = Exception("Process would start")

            # Should handle exception gracefully
            await terminal.on_mount()

            # Should not propagate exception
            assert True


class TestAsciinemaPlayer:
    """Test the main AsciinemaPlayer widget."""

    def test_init_with_string_path(self, sample_cast_file):
        """Test initialization with string path."""
        player = AsciinemaPlayer(str(sample_cast_file))

        assert isinstance(player.cast_path, Path)
        assert player.cast_path == sample_cast_file
        assert isinstance(player.parser, CastParser)
        assert player.terminal is None
        assert player.engine is None
        assert player.controls is None

    def test_init_with_path_object(self, sample_cast_file):
        """Test initialization with Path object."""
        player = AsciinemaPlayer(sample_cast_file)

        assert player.cast_path == sample_cast_file
        assert isinstance(player.parser, CastParser)

    def test_parser_properties(self, sample_cast_file):
        """Test that parser is initialized correctly."""
        player = AsciinemaPlayer(sample_cast_file)

        # Should have parsed header correctly
        header = player.parser.header
        assert header.width == 80
        assert header.height == 24
        assert header.title == "Test Recording"

        # Should have calculated duration
        assert player.parser.duration == 2.0

    def test_gzipped_file_parsing(self, gzipped_cast_file):
        """Test parsing of gzipped files."""
        player = AsciinemaPlayer(gzipped_cast_file)

        # Should parse gzipped file correctly
        header = player.parser.header
        assert header.width == 120
        assert header.height == 30
        assert header.title == "Gzipped Test Recording"
        assert player.parser.duration == 1.5

    def test_handle_play_pause_sync_wrapper(self, sample_cast_file):
        """Test play/pause sync wrapper method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock run_worker method
        player.run_worker = Mock()

        # Create mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.toggle_play_pause = AsyncMock()

        # Call the sync wrapper
        player._handle_play_pause()

        # Should call run_worker with coroutine
        player.run_worker.assert_called_once()
        call_args = player.run_worker.call_args[0][0]
        assert hasattr(call_args, "__await__")  # Is a coroutine

    def test_handle_seek_sync_wrapper(self, sample_cast_file):
        """Test seek sync wrapper method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock run_worker method
        player.run_worker = Mock()

        # Create mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.seek_to = AsyncMock()

        # Call the sync wrapper
        player._handle_seek(42.0)

        # Should call run_worker with coroutine
        player.run_worker.assert_called_once()
        call_args = player.run_worker.call_args[0][0]
        assert hasattr(call_args, "__await__")  # Is a coroutine

    @pytest.mark.asyncio
    async def test_play_method(self, sample_cast_file):
        """Test public play method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.play = AsyncMock()

        await player.play()

        player.engine.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_method(self, sample_cast_file):
        """Test public pause method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.pause = AsyncMock()

        await player.pause()

        player.engine.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_seek_method(self, sample_cast_file):
        """Test public seek method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.seek_to = AsyncMock()

        await player.seek(30.0)

        player.engine.seek_to.assert_called_once_with(30.0)

    def test_set_speed_method(self, sample_cast_file):
        """Test public set_speed method."""
        player = AsciinemaPlayer(sample_cast_file)

        # Mock engine to avoid compose() call
        player.engine = Mock()
        player.engine.set_speed = Mock()

        player.set_speed(2.0)

        player.engine.set_speed.assert_called_once_with(2.0)

    @pytest.mark.asyncio
    async def test_methods_with_no_engine(self, sample_cast_file):
        """Test public methods handle missing engine gracefully."""
        player = AsciinemaPlayer(sample_cast_file)
        # Don't set engine, so it remains None

        # Should not raise exceptions
        await player.play()
        await player.pause()
        await player.seek(30.0)
        player.set_speed(2.0)

        # All should complete without error
        assert True

    def test_context_manager_integration(self, sample_cast_file):
        """Test that parser context manager is used correctly."""
        player = AsciinemaPlayer(sample_cast_file)

        # The parser should be created and accessible
        assert isinstance(player.parser, CastParser)

        # Parser should have cleanup method available
        assert hasattr(player.parser, "cleanup")

        # Should be able to access parser properties
        assert player.parser.duration >= 0
        assert player.parser.header.width > 0

    def test_large_dimensions(self, tmp_path):
        """Test with large terminal dimensions."""
        header = {
            "version": 2,
            "width": 200,
            "height": 50,
            "timestamp": 1234567890,
        }
        frames = [[0.0, "o", "test"]]

        cast_path = tmp_path / "large.cast"
        with open(cast_path, "w") as f:
            f.write(json.dumps(header) + "\n")
            for frame in frames:
                f.write(json.dumps(frame) + "\n")

        player = AsciinemaPlayer(cast_path)

        # Should handle large dimensions without error
        assert player.parser.header.width == 200
        assert player.parser.header.height == 50

    def test_minimal_cast_file(self, tmp_path):
        """Test with minimal cast file."""
        header = {
            "version": 2,
            "width": 10,
            "height": 5,
        }
        # No frames

        cast_path = tmp_path / "minimal.cast"
        with open(cast_path, "w") as f:
            f.write(json.dumps(header) + "\n")

        player = AsciinemaPlayer(cast_path)

        # Should handle minimal file without error
        assert player.parser.header.width == 10
        assert player.parser.header.height == 5
        assert player.parser.duration == 0.0

    def test_css_classes_present(self, sample_cast_file):
        """Test that CSS is properly defined."""
        css = AsciinemaPlayer.DEFAULT_CSS

        # Should contain key selectors
        assert "#asciinema-terminal" in css
        assert "#asciinema-controls" in css
        assert "#controls-container" in css
        assert "#play-pause-btn" in css
        assert "#timeline-scrubber" in css
        assert "#time-display" in css
        assert "#speed-display" in css

        # Should contain important properties
        assert "border: solid white" in css
        assert "dock: bottom" in css
        assert "height: 3" in css


class TestAsciinemaPlayerIntegration:
    """Integration tests for AsciinemaPlayer."""

    def test_parser_context_cleanup(self, sample_cast_file):
        """Test that parser context cleanup works properly."""
        # Create player
        player = AsciinemaPlayer(sample_cast_file)

        # Access parser to ensure it's working
        original_parser = player.parser
        duration = player.parser.duration
        assert duration >= 0

        # Parser should have cleanup capabilities
        assert hasattr(original_parser, "cleanup")

        # Should be able to call cleanup without error
        original_parser.cleanup()

        # After cleanup, should still be accessible but may have cleaned up temp files
        assert original_parser is not None

    def test_streaming_functionality(self, sample_cast_file):
        """Test that streaming functionality is available."""
        player = AsciinemaPlayer(sample_cast_file)

        # Parser should have streaming methods
        assert hasattr(player.parser, "frames_with_offsets")
        assert hasattr(player.parser, "parse_from_offset")

        # Should be able to get frames with offsets
        frames_with_offsets = list(player.parser.frames_with_offsets())
        assert len(frames_with_offsets) > 0

        # Each item should be (offset, frame) tuple
        offset, frame = frames_with_offsets[0]
        assert isinstance(offset, int)
        assert offset > 0  # Should be after header
        assert hasattr(frame, "timestamp")
        assert hasattr(frame, "data")

    def test_gzipped_streaming(self, gzipped_cast_file):
        """Test streaming with gzipped files."""
        player = AsciinemaPlayer(gzipped_cast_file)

        # Should handle gzipped files correctly
        frames_with_offsets = list(player.parser.frames_with_offsets())
        assert len(frames_with_offsets) > 0

        # Should be able to parse from offset
        first_offset = frames_with_offsets[0][0]
        frames_from_offset = list(player.parser.parse_from_offset(first_offset))
        assert len(frames_from_offset) > 0
