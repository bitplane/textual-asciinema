"""Parser for asciinema cast files."""

import gzip
import json
from pathlib import Path
from typing import Iterator, NamedTuple


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
    """Parser for asciinema v2 cast files."""

    def __init__(self, cast_path: str | Path):
        self.cast_path = Path(cast_path)
        self._header = None
        self._duration = None
        self._is_gzipped = str(cast_path).endswith(".gz")

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
        open_func = gzip.open if self._is_gzipped else open
        mode = "rt" if self._is_gzipped else "r"

        with open_func(self.cast_path, mode) as f:
            header_line = f.readline().strip()
            header_data = json.loads(header_line)
            return CastHeader.from_dict(header_data)

    def _calculate_duration(self) -> float:
        """Calculate the total duration by finding the last timestamp."""
        last_timestamp = 0.0
        open_func = gzip.open if self._is_gzipped else open
        mode = "rt" if self._is_gzipped else "r"

        with open_func(self.cast_path, mode) as f:
            f.readline()  # Skip header
            for line in f:
                line = line.strip()
                if line:
                    frame_data = json.loads(line)
                    last_timestamp = frame_data[0]
        return last_timestamp

    def frames(self) -> Iterator[CastFrame]:
        """Iterate over all frames in the cast file."""
        open_func = gzip.open if self._is_gzipped else open
        mode = "rt" if self._is_gzipped else "r"

        with open_func(self.cast_path, mode) as f:
            f.readline()  # Skip header
            for line in f:
                line = line.strip()
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
