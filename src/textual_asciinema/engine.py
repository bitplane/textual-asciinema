"""Playback engine for asciinema player."""

import asyncio
import json
import logging
import time
from typing import Callable, Optional, Dict, Any
from textual_tty import TextualTerminal

from .parser import CastParser, CastFrame

# Set up debug logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Keyframe:
    """Represents a cached terminal state at a specific timestamp."""

    def __init__(self, timestamp: float, frame_index: int, file_offset: int, cost: int, creation_time: float):
        self.timestamp = timestamp
        self.frame_index = frame_index  # Index in frames list (for compatibility)
        self.file_offset = file_offset  # Byte offset in cast file for streaming
        self.cost = cost  # Number of characters processed to create this keyframe
        self.creation_time = creation_time  # When this keyframe was created
        # Future: terminal_state for dump()/reset() when available


class PlaybackEngine:
    """Engine for playing back asciinema cast files."""

    def __init__(self, parser: CastParser, terminal: TextualTerminal):
        self.parser = parser
        self.terminal = terminal

        # Playback state
        self.current_time = 0.0  # Current display time
        self.is_playing = False
        self.speed = 1.0
        self.last_update_time = 0.0

        # Keyframe cache
        self.keyframes: Dict[float, Keyframe] = {}  # keyed by timestamp
        self.keyframe_interval = 1.0  # Cache every 1 second
        self.last_keyframe_time = 0.0
        self.current_cost = 0  # Characters processed since last keyframe

        # Callbacks
        self.on_time_update: Optional[Callable[[float], None]] = None

        # Playback task
        self._playback_task: Optional[asyncio.Task] = None

        # Sequential file reading state
        self._file_handle = None  # Keep file open for sequential reading
        self._current_file_offset = 0  # Current position in file
        self._next_frame = None  # Next frame read from file (read-ahead)

        # Initialize to first frame position
        self._initialize_file_position()

    async def play(self) -> None:
        """Start or resume playback."""
        if self.is_playing:
            return

        self.is_playing = True
        self.last_update_time = time.time()

        if self._playback_task is None or self._playback_task.done():
            self._playback_task = asyncio.create_task(self._playback_loop())

    async def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
            try:
                await self._playback_task
            except asyncio.CancelledError:
                pass

    async def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            await self.pause()
        else:
            await self.play()

    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier."""
        self.speed = speed

    def _initialize_file_position(self) -> None:
        """Initialize file handle and position to first frame."""
        try:
            # Find first frame offset
            for offset, frame in self.parser.frames_with_offsets():
                self._current_file_offset = offset
                break
            else:
                self._current_file_offset = 0

            # Open file at the starting position
            if self._file_handle:
                self._file_handle.close()
            self._file_handle = open(self.parser._working_file_path, "rb")
            self._file_handle.seek(self._current_file_offset)

            # Read first frame for read-ahead
            self._next_frame = self._read_next_frame_data()
            logger.debug(f"Initialized with first frame: {self._next_frame.timestamp if self._next_frame else 'None'}")
        except Exception:
            self._current_file_offset = 0
            self._next_frame = None

    def _should_create_keyframe(self) -> bool:
        """Check if we should create a keyframe at current time."""
        return self.current_time - self.last_keyframe_time >= self.keyframe_interval

    def _create_keyframe(self) -> None:
        """Create a keyframe at current playback position."""
        keyframe_time = self.current_time
        keyframe = Keyframe(
            timestamp=keyframe_time,
            frame_index=0,  # Not used in streaming mode
            file_offset=self._current_file_offset,
            cost=self.current_cost,
            creation_time=time.time(),
        )
        self.keyframes[keyframe_time] = keyframe
        self.last_keyframe_time = keyframe_time
        self.current_cost = 0  # Reset cost counter

    def _feed_terminal_data(self, data: str) -> None:
        """Feed data to terminal and track cost."""
        self.terminal.parser.feed(data)
        self.current_cost += len(data)

        # Force terminal view to update
        if self.terminal.terminal_view:
            self.terminal.terminal_view.update_content()

        # Check if we should create a keyframe
        if self._should_create_keyframe():
            self._create_keyframe()

    def _read_next_frame_data(self) -> Optional[CastFrame]:
        """Read the next frame from file sequentially. Returns frame or None."""
        if not self._file_handle:
            return None

        try:
            line = self._file_handle.readline()
            if not line:
                return None  # End of file

            line_text = line.decode("utf-8").strip()
            if not line_text:
                return self._read_next_frame_data()  # Skip empty lines

            frame_data = json.loads(line_text)
            timestamp, stream_type, data = frame_data
            frame = CastFrame(timestamp, stream_type, data)
            return frame

        except Exception:
            return None  # Parse error or end of file

    def _consume_next_frame(self) -> Optional[CastFrame]:
        """Get the next frame and advance to the following one."""
        if not self._next_frame:
            return None

        current_frame = self._next_frame
        self._next_frame = self._read_next_frame_data()  # Read-ahead for next iteration
        return current_frame

    def _find_nearest_keyframe(self, target_time: float) -> Optional[Keyframe]:
        """Find the keyframe closest to but before target_time."""
        best_keyframe = None
        best_time = -1

        for timestamp, keyframe in self.keyframes.items():
            if timestamp <= target_time and timestamp > best_time:
                best_keyframe = keyframe
                best_time = timestamp

        return best_keyframe

    def get_keyframe_stats(self) -> Dict[str, Any]:
        """Get statistics about keyframe cache for debugging."""
        if not self.keyframes:
            return {"count": 0, "coverage": 0.0, "total_cost": 0}

        total_cost = sum(kf.cost for kf in self.keyframes.values())
        coverage = (
            len(self.keyframes) * self.keyframe_interval / self.parser.duration if self.parser.duration > 0 else 0
        )

        return {
            "count": len(self.keyframes),
            "coverage": min(coverage, 1.0),  # Cap at 100%
            "total_cost": total_cost,
            "avg_cost": total_cost / len(self.keyframes),
            "timestamps": sorted(self.keyframes.keys()),
        }

    async def seek_to(self, timestamp: float) -> None:
        """Seek to a specific timestamp using keyframe optimization."""
        timestamp = max(0.0, min(timestamp, self.parser.duration))

        was_playing = self.is_playing
        await self.pause()

        # Clear terminal and reset state before replaying
        self.terminal.clear_screen()
        # Send additional reset sequences to ensure clean state
        # Move cursor to home position and reset attributes
        self.terminal.parser.feed("\033[H\033[0m")

        # Try to find a keyframe to start from
        keyframe = self._find_nearest_keyframe(timestamp)

        if keyframe:
            # Start from keyframe file offset
            start_offset = keyframe.file_offset
        else:
            # No keyframe found, start from beginning of file (after header)
            # We need to find the first frame offset
            start_offset = None
            for offset, frame in self.parser.frames_with_offsets():
                start_offset = offset
                break
            if start_offset is None:
                start_offset = 0

        # Seek file to start offset and replay frames to target timestamp
        if self._file_handle:
            self._file_handle.seek(start_offset)
            self._current_file_offset = start_offset

        # Read and feed frames until we reach target timestamp
        logger.debug(f"Seek: replaying frames from file to reach timestamp {timestamp:.3f}")
        frames_replayed = 0

        # Read first frame for new position
        self._next_frame = self._read_next_frame_data()

        # Process frames until we reach target
        while self._next_frame and self._next_frame.timestamp <= timestamp:
            frame = self._consume_next_frame()
            frames_replayed += 1

            if frame.stream_type == "o":
                self._feed_terminal_data(frame.data)

        logger.debug(
            f"Seek: replayed {frames_replayed} frames to reach {timestamp:.3f}, next_frame={self._next_frame.timestamp if self._next_frame else 'None'}"
        )

        # Update state
        self.current_time = timestamp

        if self.on_time_update:
            self.on_time_update(self.current_time)

        if was_playing:
            await self.play()

    async def _playback_loop(self) -> None:
        """Main playback loop with streaming."""
        try:
            while self.is_playing:
                current_real_time = time.time()

                # Calculate how much cast time has passed
                if self.last_update_time > 0:
                    real_time_delta = current_real_time - self.last_update_time
                    cast_time_delta = real_time_delta * self.speed
                    self.current_time += cast_time_delta

                self.last_update_time = current_real_time

                # Process frames that are ready to play (simple read-ahead pattern)
                accumulated_data = ""
                frames_processed_this_loop = 0

                logger.debug(
                    f"Loop start: current_time={self.current_time:.3f}, next_frame={self._next_frame.timestamp if self._next_frame else 'None'}"
                )

                # Process all frames that should have played by now
                while self._next_frame and self._next_frame.timestamp <= self.current_time:
                    frame = self._consume_next_frame()  # Get current frame and advance read-ahead
                    frames_processed_this_loop += 1

                    logger.debug(
                        f"PROCESS: timestamp={frame.timestamp:.3f}, type={frame.stream_type}, data_len={len(frame.data)}"
                    )

                    # Is it time to create a keyframe?
                    if self._should_create_keyframe() and not self.keyframes.get(frame.timestamp):
                        self._create_keyframe()
                        logger.debug(f"Created keyframe at {frame.timestamp:.3f}")

                    # Feed this frame to terminal
                    if frame.stream_type == "o":
                        accumulated_data += frame.data

                # Check for end of file
                if not self._next_frame:
                    logger.debug("End of file reached, stopping playback")
                    self.is_playing = False

                logger.debug(
                    f"Loop end: processed={frames_processed_this_loop}, accumulated_data_len={len(accumulated_data)}, next_frame={self._next_frame.timestamp if self._next_frame else 'None'}"
                )

                # Feed all accumulated data at once
                if accumulated_data:
                    self._feed_terminal_data(accumulated_data)

                # Update time display
                if self.on_time_update:
                    self.on_time_update(self.current_time)

                # Check if we've reached the end
                if self.current_time >= self.parser.duration:
                    self.is_playing = False
                    break

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Log error and stop playback
            print(f"Playback error: {e}")
            self.is_playing = False

    def reset(self) -> None:
        """Reset playback to the beginning."""
        self.current_time = 0.0
        self.last_keyframe_time = 0.0
        self.current_cost = 0
        # Keep existing keyframes - they're still valid for future seeks
        self.terminal.clear_screen()

        # Reset file position to beginning
        self._initialize_file_position()

        if self.on_time_update:
            self.on_time_update(self.current_time)

    def __del__(self):
        """Cleanup file handle."""
        if self._file_handle:
            self._file_handle.close()
