# Textual Asciinema Player

A widget for playing asciinema .cast files

## Try

```bash
uvx textual-asciinema my-file.cast
```

## See

* [📺 youtube](https://youtu.be/2fMZmxsm5ZM)

## Read

* [🏠 home](https://ttygroup.github.io/textual-asciinema)
* [🐱 src](https://github.com/ttygroup/textual-asciinema)
* [🐍 pypi](https://pypi.org/project/textual-asciinema)

## Also

* [🎬 asciinema](https://bitplan.net/dev/python/tvmux) - terminal recorder
* [🗔 ](https://bitplane.net/dev/python/bittty) - a pure python tty
* [🎥 tvmux](https://bitplane.net/dev/python/tvmux) - record your tmux projects

## Development Status

✅ **COMPLETED** - Keyframe Caching System (2025-08-04)
- Keyframes created every 1 second during playback
- Seek optimization using nearest keyframe as starting point
- Cost tracking for future cache eviction algorithms
- Terminal state reset for clean scrubbing experience
- Performance: O(target_time) → O(keyframe_interval) for seeks

## Next Steps

🔄 **IN PROGRESS** - File Offset Based Keyframes
- Store byte offsets in .cast files instead of just frame indices
- Enable streaming playback of massive cast files without loading everything into memory
- Lazy frame parsing from file positions
- True streaming for multi-GB recordings

### Implementation Plan:
1. **Enhance Keyframe class**: Add `file_offset` field to store byte position in .cast file
2. **Update CastParser**: Track file position during parsing, provide seek capability
3. **Streaming seek**: Jump to file offset, parse from there instead of replaying from memory
4. **Memory efficiency**: Only keep frames in memory around current playback position

### Benefits:
- Handle multi-GB cast files without memory exhaustion
- Instant seeking regardless of file size
- Constant memory usage independent of recording length


