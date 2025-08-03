# Textual Asciinema Player

An asciinema player widget for Textual applications. This widget provides video-like
controls for playing back asciinema terminal recordings with seeking, speed control,
and a familiar player interface.

## Project Status

**Current Phase:** Basic Implementation Complete, Debugging TextualTerminal Integration

### ✅ Completed Components

1. **CastParser** (`src/textual_asciinema/parser.py`)
   - Parses asciinema v2 format (.cast files)
   - Supports gzipped files (.cast.gz)
   - Extracts header metadata (dimensions, duration, etc.)
   - Provides frame iteration with timestamp filtering

2. **AsciinemaPlayer** (`src/textual_asciinema/player.py`)
   - Main container widget that orchestrates all components
   - Integrates terminal display with player controls
   - Manages playback state and coordinates between components
   - Includes `PlaybackTerminal` subclass to prevent shell startup

3. **PlayerControls** (`src/textual_asciinema/controls.py`)
   - Video-style control bar with play/pause button
   - Time display showing "current/total" format
   - Horizontal progress bar for scrubbing
   - Speed display and keyboard shortcuts
   - Reactive properties for real-time updates

4. **PlaybackEngine** (`src/textual_asciinema/engine.py`)
   - Manages linear playback with accurate timing
   - Handles play/pause/seek operations
   - Speed control (0.5x to 3x)
   - Frame indexing and timestamp tracking

5. **Demo Application** (`demo.py`)
   - Simple test app that loads and plays cast files
   - CSS styling for proper widget layout
   - Command-line interface: `./demo.py <cast_file>`

### 🔧 Current Issue

**Problem:** TextualTerminal still launches a shell despite overriding `on_mount()`

The demo currently starts a bash shell (indicated by purple prompt) instead of
showing the Textual UI. This suggests that textual-tty is starting a PTY process
somewhere in its initialization chain that we haven't identified yet.

**Attempted Solutions:**
- ✅ Created `PlaybackTerminal` subclass that overrides `on_mount()`
- ✅ Tried passing `shell=None` parameter (not supported)
- ❌ Still launches shell - need deeper investigation

### 🔍 Next Steps (Priority Order)

1. **Deep Investigation** - Research textual-tty and bittty initialization
   - Identify all code paths that create PTY processes
   - Find constructor parameters or methods to prevent subprocess creation
   - Consider bypassing TextualTerminal and using bittty.Terminal directly

2. **Fix Terminal Integration** - Get basic playback working
   - Ensure terminal displays ANSI content without launching processes
   - Test with simple cast files

3. **Implement Keyframe Caching** - For efficient seeking
   - Cache terminal state every 5-10 seconds
   - Enable instant backward seeking to cached points

4. **Add Scrubbing Support** - Timeline interaction
   - Click-to-seek on progress bar
   - Smooth scrubbing with visual feedback

5. **Polish Features** - Enhanced user experience
   - Keyboard shortcuts (space, arrows, number keys)
   - Speed controls (0.5x, 1x, 1.5x, 2x, 3x)
   - Better error handling and edge cases

## Architecture

```
AsciinemaPlayer (main widget)
├── PlaybackTerminal (terminal display)
│   └── bittty.Terminal (ANSI parsing & rendering)
└── PlayerControls (control bar)
    ├── Play/Pause Button
    ├── Time Display (00:00 / 05:30)
    ├── Progress Bar (scrubbing)
    └── Speed Display (1.0x)

PlaybackEngine (coordination)
├── CastParser (file reading)
├── Frame Management (indexing, caching)
└── Timing Control (speed, seeking)
```

## Key Features (Planned)

- **Video-like Interface:** Play, pause, seek, speed control
- **Format Support:** .cast and .cast.gz files
- **Efficient Seeking:** Keyframe caching for instant backward seeks
- **Keyboard Shortcuts:** Space, arrows, number keys
- **Terminal Accuracy:** Full ANSI escape sequence support via bittty
- **Textual Integration:** Reactive properties, proper widget lifecycle

## Files Created

```
src/textual_asciinema/
├── __init__.py           # Package exports
├── parser.py             # Cast file parsing (.cast/.cast.gz)
├── player.py             # Main widget + PlaybackTerminal
├── controls.py           # Player controls UI
└── engine.py             # Playback logic and timing

demo.py                   # Test application
player.tcss              # CSS styling
test.cast                # Simple test file
```

## Development Notes

- Built on textual-tty (v0.2.2) and bittty (v0.0.5)
- Follows Zen of Python principles
- Uses pytest-style functional tests
- Supports Python 3.10+

## Testing

```bash
# Basic parser test
python -c "from src.textual_asciinema.parser import CastParser; p = CastParser('test.cast'); print(p.header, p.duration)"

# Demo app (currently launches shell - needs fix)
./demo.py test.cast
```

## Known Issues

1. **Shell Startup:** TextualTerminal launches bash instead of displaying UI
2. **No Keyframes:** Seeking is currently linear (inefficient for large files)
3. **Limited Testing:** Need more comprehensive test coverage

---

*This project demonstrates the power of Textual widgets and showcases textual-tty
for building sophisticated terminal-based applications.*