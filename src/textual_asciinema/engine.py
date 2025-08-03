"""Playback engine for asciinema player."""

import asyncio
import time
from typing import Callable, Optional, Dict, Any
from textual_tty import TextualTerminal

from .parser import CastParser


class Keyframe:
    """Represents a cached terminal state at a specific timestamp."""

    def __init__(self, timestamp: float, terminal_state: Dict[str, Any]):
        self.timestamp = timestamp
        self.terminal_state = terminal_state


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

        # Keyframe cache (will be implemented later)
        self.keyframes: list[Keyframe] = []
        self.keyframe_interval = 5.0  # Cache every 5 seconds

        # Callbacks
        self.on_time_update: Optional[Callable[[float], None]] = None

        # Playback task
        self._playback_task: Optional[asyncio.Task] = None

        # Frame cache for current playback
        self._frames = list(self.parser.frames())
        self._current_frame_index = 0

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

    async def seek_to(self, timestamp: float) -> None:
        """Seek to a specific timestamp."""
        # For now, simple linear seeking - we'll optimize with keyframes later
        timestamp = max(0.0, min(timestamp, self.parser.duration))

        was_playing = self.is_playing
        await self.pause()

        # Reset terminal (commented out for now - may be clearing content)
        # self.terminal.clear_screen()

        # Find the frame index for this timestamp
        self._current_frame_index = 0
        for i, frame in enumerate(self._frames):
            if frame.timestamp > timestamp:
                break
            self._current_frame_index = i

        # Replay all frames up to this point
        for i in range(self._current_frame_index + 1):
            frame = self._frames[i]
            if frame.stream_type == "o":
                self.terminal.parser.feed(frame.data)

        # Force terminal view to update after seeking
        if self.terminal.terminal_view:
            self.terminal.terminal_view.update_content()

        self.current_time = timestamp
        if self.on_time_update:
            self.on_time_update(self.current_time)

        if was_playing:
            await self.play()

    async def _playback_loop(self) -> None:
        """Main playback loop."""
        try:
            while self.is_playing and self._current_frame_index < len(self._frames):
                current_real_time = time.time()

                # Calculate how much cast time has passed
                if self.last_update_time > 0:
                    real_time_delta = current_real_time - self.last_update_time
                    cast_time_delta = real_time_delta * self.speed
                    self.current_time += cast_time_delta

                self.last_update_time = current_real_time

                # Process frames that should have played by now
                while (
                    self._current_frame_index < len(self._frames)
                    and self._frames[self._current_frame_index].timestamp <= self.current_time
                ):
                    frame = self._frames[self._current_frame_index]
                    if frame.stream_type == "o":
                        # Feed ANSI data to the terminal parser
                        self.terminal.parser.feed(frame.data)
                        # Force terminal view to update
                        if self.terminal.terminal_view:
                            self.terminal.terminal_view.update_content()

                    self._current_frame_index += 1

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
        self._current_frame_index = 0
        self.terminal.clear_screen()
        if self.on_time_update:
            self.on_time_update(self.current_time)
