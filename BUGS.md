# Known Bugs

## Terminal Display Issues

1. **Vertical Scrollbar** - Terminal shows a vertical scrollbar even when content fits
   - May be a textual-tty issue or our sizing configuration
   - Should investigate if this is expected behavior

2. **Shell Requirement** - TextualTerminal requires a command/shell even for display-only
   - Should be able to pass `None` or disable process spawning entirely
   - Current workaround: override `start_process()` method

3. **Terminal Not Refreshing** - Terminal doesn't update display when content is written
   - `write_text()` doesn't trigger automatic refresh
   - Need to call `terminal_view.update_content()` after writing
   - FIXED: Added `terminal_view.update_content()` calls

4. **Terminal Word Wrapping** - Terminal content is word-wrapping incorrectly
   - Terminal widget may not be respecting the width parameter
   - Content designed for 94 columns appears to wrap at a narrower width

## Playback Issues

4. **~~Play Button Not Working~~** - FIXED
   - Was due to async/sync mismatch between controls and engine

## Future Investigation

- Test with different terminal sizes/content
- Verify ANSI escape sequence handling
- Performance with large cast files