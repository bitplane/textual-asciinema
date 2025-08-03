# Known Bugs

## Terminal Display Issues

1. **Vertical Scrollbar** - Terminal shows a vertical scrollbar even when content fits
   - May be a textual-tty issue or our sizing configuration
   - Should investigate if this is expected behavior

2. **Shell Requirement** - TextualTerminal requires a command/shell even for display-only
   - Should be able to pass `None` or disable process spawning entirely
   - Current workaround: override `start_process()` method

## Playback Issues

3. **Play Button Not Working** - Time doesn't progress when play button is clicked
   - Controls may not be properly wired to engine
   - Engine may not be starting playback loop correctly

## Future Investigation

- Test with different terminal sizes/content
- Verify ANSI escape sequence handling
- Performance with large cast files