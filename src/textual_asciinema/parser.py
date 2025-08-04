"""Parser for asciinema cast files."""

import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Iterator, NamedTuple, Optional, Tuple
from platformdirs import user_cache_dir


class CastHeader(NamedTuple):
    """Metadata from the cast file header."""

    version: int
    width: int
    height: int
    timestamp: int
    title: str = ""
    command: str = ""
    shell: str = ""
    env: dict = None

    @classmethod
    def from_dict(cls, data: dict) -> "CastHeader":
        """Create header from parsed JSON."""
        return cls(
            version=data["version"],
            width=data["width"],
            height=data["height"],
            timestamp=data.get("timestamp", 0),
            title=data.get("title", ""),
            command=data.get("command", ""),
            shell=data.get("shell", ""),
            env=data.get("env", {}),
        )


class CastFrame(NamedTuple):
    """A single frame from the cast file."""

    timestamp: float
    stream_type: str
    data: str


class CastParser:
    """Parser for asciinema v2 cast files with file offset support."""

    def __init__(self, cast_path: str | Path):
        self.cast_path = Path(cast_path)
        self._header = None
        self._duration = None
        self._is_gzipped = str(cast_path).endswith(".gz")
        self._working_file_path: Optional[Path] = None
        self._temp_cache_file = False

        # If gzipped, decompress to cache directory
        if self._is_gzipped:
            self._working_file_path = self._decompress_to_cache()
            self._temp_cache_file = True
        else:
            self._working_file_path = self.cast_path

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()

    def cleanup(self):
        """Clean up temporary cache files."""
        if self._temp_cache_file and self._working_file_path and self._working_file_path.exists():
            try:
                os.unlink(self._working_file_path)
            except OSError:
                pass  # Ignore cleanup errors
            self._temp_cache_file = False

    def _decompress_to_cache(self) -> Path:
        """Decompress gzipped cast file to cache directory."""
        cache_dir = Path(user_cache_dir("textual-asciinema"))
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Create temp file in cache dir
        fd, temp_path = tempfile.mkstemp(suffix=".cast", dir=cache_dir)
        temp_path = Path(temp_path)

        try:
            with os.fdopen(fd, "wb") as temp_file:
                with gzip.open(self.cast_path, "rb") as gz_file:
                    temp_file.write(gz_file.read())
        except Exception:
            # Clean up on error
            if temp_path.exists():
                os.unlink(temp_path)
            raise

        return temp_path

    @property
    def header(self) -> CastHeader:
        """Get the cast file header."""
        if self._header is None:
            self._header = self._parse_header()
        return self._header

    @property
    def duration(self) -> float:
        """Get the total duration of the cast in seconds."""
        if self._duration is None:
            self._duration = self._calculate_duration()
        return self._duration

    def _parse_header(self) -> CastHeader:
        """Parse the header line of the cast file."""
        with open(self._working_file_path, "rb") as f:
            header_line = f.readline().decode("utf-8").strip()
            header_data = json.loads(header_line)
            return CastHeader.from_dict(header_data)

    def _calculate_duration(self) -> float:
        """Calculate the total duration by finding the last timestamp."""
        last_timestamp = 0.0
        with open(self._working_file_path, "rb") as f:
            f.readline()  # Skip header
            for line in f:
                line = line.decode("utf-8").strip()
                if line:
                    frame_data = json.loads(line)
                    last_timestamp = frame_data[0]
        return last_timestamp

    def frames(self) -> Iterator[CastFrame]:
        """Iterate over all frames in the cast file."""
        with open(self._working_file_path, "rb") as f:
            f.readline()  # Skip header
            for line in f:
                line = line.decode("utf-8").strip()
                if line:
                    frame_data = json.loads(line)
                    timestamp, stream_type, data = frame_data
                    yield CastFrame(timestamp, stream_type, data)

    def frames_with_offsets(self) -> Iterator[Tuple[int, CastFrame]]:
        """Iterate over frames with their byte offsets in the file."""
        with open(self._working_file_path, "rb") as f:
            f.readline()  # Skip header
            while True:
                offset = f.tell()
                line = f.readline()
                if not line:
                    break
                line = line.decode("utf-8").strip()
                if line:
                    frame_data = json.loads(line)
                    timestamp, stream_type, data = frame_data
                    yield offset, CastFrame(timestamp, stream_type, data)

    def parse_from_offset(self, offset: int) -> Iterator[CastFrame]:
        """Parse frames starting from a specific byte offset."""
        with open(self._working_file_path, "rb") as f:
            f.seek(offset)
            for line in f:
                line = line.decode("utf-8").strip()
                if line:
                    frame_data = json.loads(line)
                    timestamp, stream_type, data = frame_data
                    yield CastFrame(timestamp, stream_type, data)

    def frames_until(self, max_timestamp: float) -> Iterator[CastFrame]:
        """Iterate over frames up to a specific timestamp."""
        for frame in self.frames():
            if frame.timestamp > max_timestamp:
                break
            yield frame

    def frames_from(self, start_timestamp: float) -> Iterator[CastFrame]:
        """Iterate over frames starting from a specific timestamp."""
        for frame in self.frames():
            if frame.timestamp >= start_timestamp:
                yield frame
