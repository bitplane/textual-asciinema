"""Video player for asciinema playback - handles timing and UI updates only."""

import asyncio
import logging
import time
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from textual_tty import TextualTerminal

from .parser import CastParser
from .video_file import VideoFile

# Set up debug logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PlaybackEngine:
    """Video player that handles timing, UI updates, and user controls."""

    def __init__(self, parser: CastParser, terminal: "TextualTerminal"):
        self.parser = parser
        self.terminal = terminal

        # Video file manager handles file reading only
        self.video_file = VideoFile(parser)

        # Simple playback state - just UI timing
        self.current_time = 0.0
        self.is_playing = False
        self.speed = 1.0
        self.last_update_time = 0.0

        # UI callback
        self.on_time_update: Optional[Callable[[float], None]] = None

        # Playback task
        self._playback_task: Optional[asyncio.Task] = None

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
        timestamp = max(0.0, min(timestamp, self.parser.duration))

        was_playing = self.is_playing
        await self.pause()

        # Clear terminal and seek video file
        self.terminal.clear_screen()
        self.video_file.seek_to_time(timestamp)

        # Update UI time
        self.current_time = timestamp

        if self.on_time_update:
            self.on_time_update(self.current_time)

        if was_playing:
            await self.play()

    async def _playback_loop(self) -> None:
        """Simple video player loop - streams frames to terminal."""
        try:
            frame_time = 0.016  # Target 60fps
            last_render_time = 0.0

            while self.is_playing:
                current_real_time = time.time()

                # Calculate how much cast time has passed
                if self.last_update_time > 0:
                    real_time_delta = current_real_time - self.last_update_time
                    cast_time_delta = real_time_delta * self.speed
                    self.current_time += cast_time_delta

                self.last_update_time = current_real_time

                # Skip frames if we're falling behind (only render at target framerate)
                time_since_last_render = current_real_time - last_render_time
                if time_since_last_render >= frame_time:
                    # Get frames up to current time and feed to terminal
                    frames = self.video_file.get_frames_until(self.current_time)
                    has_output = False
                    for frame in frames:
                        if frame.stream_type == "o":
                            # Feed output data to terminal
                            self.terminal.parser.feed(frame.data)
                            has_output = True
                        elif frame.stream_type == "r":
                            # Handle resize events
                            try:
                                cols, rows = map(int, frame.data.split("x"))
                                logger.debug(f"Resize event at {frame.timestamp:.3f}: {cols}x{rows}")
                                self.terminal.resize(cols, rows)
                                has_output = True
                            except (ValueError, AttributeError) as e:
                                logger.warning(f"Failed to parse resize data '{frame.data}': {e}")

                    # Trigger display update if we had any output
                    if has_output:
                        await self.terminal._update_display()

                    last_render_time = current_real_time

                    # Update time display
                    if self.on_time_update:
                        self.on_time_update(self.current_time)

                # Check if we've reached the end
                if self.current_time >= self.parser.duration:
                    self.is_playing = False
                    break

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.008)  # 125Hz polling for smoother timing

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Playback error: {e}")
            self.is_playing = False

    def reset(self) -> None:
        """Reset playback to the beginning."""
        self.current_time = 0.0
        self.last_update_time = 0.0

        # Clear terminal and reset video file
        self.terminal.clear_screen()
        self.video_file.seek_to_time(0.0)

        if self.on_time_update:
            self.on_time_update(self.current_time)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.video_file:
            self.video_file.cleanup()

    def __del__(self):
        """Cleanup on destruction."""
        self.cleanup()
