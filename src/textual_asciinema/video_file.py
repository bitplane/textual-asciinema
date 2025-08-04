"""Simplified video file manager for asciinema playback."""

import json
import logging
from typing import List

from .parser import CastParser, CastFrame

logger = logging.getLogger(__name__)


class VideoFile:
    """Manages asciinema file reading and frame streaming."""

    def __init__(self, parser: CastParser):
        self.parser = parser

        # Simple file reading state
        self._file_handle = None
        self._current_file_offset = 0
        self._current_time = 0.0

        self._initialize_file()

    def _initialize_file(self) -> None:
        """Initialize file reading."""
        try:
            # Find first frame offset
            for offset, frame in self.parser.frames_with_offsets():
                self._current_file_offset = offset
                break
            else:
                self._current_file_offset = 0

            # Open file at starting position
            if self._file_handle:
                self._file_handle.close()
            self._file_handle = open(self.parser._working_file_path, "rb")
            self._file_handle.seek(self._current_file_offset)
            self._current_time = 0.0
            logger.debug(f"VideoFile initialized at offset {self._current_file_offset}")

        except Exception as e:
            logger.error(f"Failed to initialize video file: {e}")
            self._current_file_offset = 0

    def get_frames_until(self, target_time: float) -> List[CastFrame]:
        """Get all frames from current position up to target time."""
        frames = []
        if not self._file_handle:
            return frames

        try:
            while True:
                line = self._file_handle.readline()
                if not line:
                    break

                line_text = line.decode("utf-8").strip()
                if not line_text:
                    continue

                frame_data = json.loads(line_text)
                timestamp, stream_type, data = frame_data

                if timestamp > target_time:
                    # Seek back to start of this line for next call
                    self._file_handle.seek(self._file_handle.tell() - len(line))
                    break

                frames.append(CastFrame(timestamp, stream_type, data))
                self._current_time = timestamp

        except Exception as e:
            logger.error(f"Error reading frames: {e}")

        return frames

    def seek_to_time(self, target_time: float) -> None:
        """Seek to a specific timestamp (simple implementation - restart from beginning)."""
        if target_time < self._current_time:
            # Seeking backwards - restart from beginning
            self._initialize_file()

        # Skip frames until we reach target time
        self.get_frames_until(target_time)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._file_handle:
            self._file_handle.close()

    def __del__(self):
        """Cleanup on destruction."""
        self.cleanup()
