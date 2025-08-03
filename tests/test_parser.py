"""Tests for the asciinema parser."""

import gzip
import json

import pytest

from textual_asciinema.parser import CastParser, CastFrame


@pytest.fixture
def sample_cast_data():
    """Sample cast data for testing."""
    header = {
        "version": 2,
        "width": 80,
        "height": 24,
        "timestamp": 1234567890,
        "title": "Test Recording",
        "command": "/bin/bash",
        "shell": "/bin/bash",
        "env": {"TERM": "xterm-256color"},
    }
    frames = [
        [0.0, "o", "Hello "],
        [0.5, "o", "World!"],
        [1.0, "o", "\r\n"],
        [1.5, "o", "$ "],
    ]
    return header, frames


@pytest.fixture
def cast_file(sample_cast_data, tmp_path):
    """Create a temporary cast file."""
    header, frames = sample_cast_data
    cast_path = tmp_path / "test.cast"

    with open(cast_path, "w") as f:
        f.write(json.dumps(header) + "\n")
        for frame in frames:
            f.write(json.dumps(frame) + "\n")

    return cast_path


@pytest.fixture
def gzipped_cast_file(sample_cast_data, tmp_path):
    """Create a temporary gzipped cast file."""
    header, frames = sample_cast_data
    cast_path = tmp_path / "test.cast.gz"

    with gzip.open(cast_path, "wt") as f:
        f.write(json.dumps(header) + "\n")
        for frame in frames:
            f.write(json.dumps(frame) + "\n")

    return cast_path


def test_parse_header(cast_file):
    """Test parsing the header from a regular cast file."""
    parser = CastParser(cast_file)
    header = parser.header

    assert header.version == 2
    assert header.width == 80
    assert header.height == 24
    assert header.timestamp == 1234567890
    assert header.title == "Test Recording"
    assert header.command == "/bin/bash"
    assert header.shell == "/bin/bash"
    assert header.env == {"TERM": "xterm-256color"}


def test_parse_gzipped_header(gzipped_cast_file):
    """Test parsing the header from a gzipped cast file."""
    parser = CastParser(gzipped_cast_file)
    header = parser.header

    assert header.version == 2
    assert header.width == 80
    assert header.height == 24
    assert header.timestamp == 1234567890
    assert header.title == "Test Recording"
    assert header.command == "/bin/bash"
    assert header.shell == "/bin/bash"
    assert header.env == {"TERM": "xterm-256color"}


def test_duration(cast_file):
    """Test calculating duration from a regular cast file."""
    parser = CastParser(cast_file)
    assert parser.duration == 1.5


def test_gzipped_duration(gzipped_cast_file):
    """Test calculating duration from a gzipped cast file."""
    parser = CastParser(gzipped_cast_file)
    assert parser.duration == 1.5


def test_frames(cast_file):
    """Test iterating over frames in a regular cast file."""
    parser = CastParser(cast_file)
    frames = list(parser.frames())

    assert len(frames) == 4
    assert frames[0] == CastFrame(0.0, "o", "Hello ")
    assert frames[1] == CastFrame(0.5, "o", "World!")
    assert frames[2] == CastFrame(1.0, "o", "\r\n")
    assert frames[3] == CastFrame(1.5, "o", "$ ")


def test_gzipped_frames(gzipped_cast_file):
    """Test iterating over frames in a gzipped cast file."""
    parser = CastParser(gzipped_cast_file)
    frames = list(parser.frames())

    assert len(frames) == 4
    assert frames[0] == CastFrame(0.0, "o", "Hello ")
    assert frames[1] == CastFrame(0.5, "o", "World!")
    assert frames[2] == CastFrame(1.0, "o", "\r\n")
    assert frames[3] == CastFrame(1.5, "o", "$ ")


def test_frames_until(cast_file):
    """Test getting frames up to a specific timestamp."""
    parser = CastParser(cast_file)
    frames = list(parser.frames_until(0.7))

    assert len(frames) == 2
    assert frames[0].timestamp == 0.0
    assert frames[1].timestamp == 0.5


def test_frames_from(cast_file):
    """Test getting frames from a specific timestamp."""
    parser = CastParser(cast_file)
    frames = list(parser.frames_from(1.0))

    assert len(frames) == 2
    assert frames[0].timestamp == 1.0
    assert frames[1].timestamp == 1.5
