"""Playback engine for asciinema player."""

import asyncio
import time
from typing import Callable, Optional, Dict, Any
from textual_tty import TextualTerminal

from .parser import CastParser


class Keyframe:
    """Represents a cached terminal state at a specific timestamp."""

    def __init__(self, timestamp: float, frame_index: int, cost: int, creation_time: float):
        self.timestamp = timestamp
        self.frame_index = frame_index  # Index in frames list to replay from
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

    def _should_create_keyframe(self) -> bool:
        """Check if we should create a keyframe at current time."""
        return self.current_time - self.last_keyframe_time >= self.keyframe_interval

    def _create_keyframe(self) -> None:
        """Create a keyframe at current playback position."""
        keyframe_time = self.current_time
        keyframe = Keyframe(
            timestamp=keyframe_time,
            frame_index=self._current_frame_index,
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
            # Start from keyframe
            start_frame_index = keyframe.frame_index
        else:
            # No keyframe found, start from beginning
            start_frame_index = 0

        # Find the target frame index
        target_frame_index = start_frame_index
        for i in range(start_frame_index, len(self._frames)):
            if self._frames[i].timestamp > timestamp:
                break
            target_frame_index = i

        # Replay frames from start point to target
        for i in range(start_frame_index, target_frame_index + 1):
            frame = self._frames[i]
            if frame.stream_type == "o":
                # Use _feed_terminal_data to track cost and create keyframes
                self._feed_terminal_data(frame.data)

        # Update state
        self._current_frame_index = target_frame_index
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
                        # Feed ANSI data to the terminal parser with cost tracking
                        self._feed_terminal_data(frame.data)

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
        self.last_keyframe_time = 0.0
        self.current_cost = 0
        # Keep existing keyframes - they're still valid for future seeks
        self.terminal.clear_screen()
        if self.on_time_update:
            self.on_time_update(self.current_time)
