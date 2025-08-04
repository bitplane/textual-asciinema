"""Playback engine for asciinema player."""

import asyncio
import time
from typing import Callable, Optional, Dict, Any
from textual_tty import TextualTerminal

from .parser import CastParser, CastFrame


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
        self.current_time = 0.0
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

        # Streaming playback state
        self._frame_buffer = []  # Small buffer of upcoming frames
        self._buffer_size = 100  # Keep 100 frames buffered
        self._current_file_offset = 0  # Will be set after method definition

        # Initialize file offset after methods are defined
        self._initialize_offset()

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

    def _initialize_offset(self) -> None:
        """Initialize the current file offset to the first frame."""
        try:
            for offset, frame in self.parser.frames_with_offsets():
                self._current_file_offset = offset
                return
        except Exception:
            pass
        self._current_file_offset = 0  # Fallback to start of file

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

    def _fill_frame_buffer(self) -> None:
        """Fill the frame buffer with upcoming frames."""
        if len(self._frame_buffer) >= self._buffer_size:
            return  # Buffer is full

        # Get frames starting from current offset
        try:
            frame_iter = self.parser.parse_from_offset(self._current_file_offset)
            frames_to_add = self._buffer_size - len(self._frame_buffer)

            for i, frame in enumerate(frame_iter):
                if i >= frames_to_add:
                    break
                self._frame_buffer.append(frame)
        except Exception:
            # End of file or parsing error
            pass

    def _get_next_frame(self) -> Optional[CastFrame]:
        """Get the next frame, managing the buffer."""
        if not self._frame_buffer:
            self._fill_frame_buffer()

        if self._frame_buffer:
            return self._frame_buffer.pop(0)
        return None

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

        # Replay frames from start offset to target timestamp
        self._current_file_offset = start_offset
        for frame in self.parser.parse_from_offset(start_offset):
            if frame.timestamp > timestamp:
                break
            if frame.stream_type == "o":
                # Use _feed_terminal_data to track cost and create keyframes
                self._feed_terminal_data(frame.data)

        # Update state
        self.current_time = timestamp
        self._frame_buffer.clear()  # Clear buffer after seek
        self._fill_frame_buffer()  # Refill for playback

        if self.on_time_update:
            self.on_time_update(self.current_time)

        if was_playing:
            await self.play()

    async def _playback_loop(self) -> None:
        """Main playback loop with streaming."""
        try:
            # Initialize buffer if empty
            if not self._frame_buffer:
                self._fill_frame_buffer()

            while self.is_playing:
                current_real_time = time.time()

                # Calculate how much cast time has passed
                if self.last_update_time > 0:
                    real_time_delta = current_real_time - self.last_update_time
                    cast_time_delta = real_time_delta * self.speed
                    self.current_time += cast_time_delta

                self.last_update_time = current_real_time

                # Process frames that should have played by now
                while True:
                    # Peek at next frame
                    if not self._frame_buffer:
                        self._fill_frame_buffer()

                    if not self._frame_buffer:
                        # No more frames, end of file
                        self.is_playing = False
                        break

                    next_frame = self._frame_buffer[0]
                    if next_frame.timestamp > self.current_time:
                        break  # This frame is in the future

                    # Process this frame
                    frame = self._get_next_frame()
                    if frame and frame.stream_type == "o":
                        # Feed ANSI data to the terminal parser with cost tracking
                        self._feed_terminal_data(frame.data)

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
        self._current_file_offset = 0
        self._frame_buffer.clear()
        self.last_keyframe_time = 0.0
        self.current_cost = 0
        # Keep existing keyframes - they're still valid for future seeks
        self.terminal.clear_screen()
        if self.on_time_update:
            self.on_time_update(self.current_time)
