"""An editable line of text and the window of it that is on screen.

The prompt used to hand the whole job to curses.getstr, which capped what could
be typed at the width of the field and, on a window whose keypad translation was
never enabled, echoed the raw bytes of backspace and the arrow keys into the
buffer as symbols instead of acting on them. Keeping the editing rules here,
free of curses, is what makes them testable without a terminal.
"""

from __future__ import annotations

# Where a word ends, for the purpose of rubbing one out. A path separator counts
# so that killing a word walks up a directory at a time.
WORD_BREAKS = " /"


class EditLine:
    """A string and a cursor into it. Every operation clamps rather than raises."""

    def __init__(self, text: str = ""):
        self.text = text
        self.cursor = len(text)

    # ---- editing ------------------------------------------------------------

    def insert(self, chunk: str) -> None:
        self.text = self.text[: self.cursor] + chunk + self.text[self.cursor :]
        self.cursor += len(chunk)

    def backspace(self) -> None:
        if self.cursor > 0:
            self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
            self.cursor -= 1

    def delete(self) -> None:
        self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]

    def kill_to_start(self) -> None:
        self.text = self.text[self.cursor :]
        self.cursor = 0

    def kill_word(self) -> None:
        """Remove the word before the cursor.

        Trailing separators go first, so a path ending in one loses the segment
        before it rather than nothing at all.
        """
        head = self.text[: self.cursor].rstrip(WORD_BREAKS)
        cut = max((head.rfind(break_) for break_ in WORD_BREAKS), default=-1) + 1
        self.text = self.text[:cut] + self.text[self.cursor :]
        self.cursor = cut

    # ---- movement -----------------------------------------------------------

    def move(self, step: int) -> None:
        self.cursor = min(max(0, self.cursor + step), len(self.text))

    def to_start(self) -> None:
        self.cursor = 0

    def to_end(self) -> None:
        self.cursor = len(self.text)


def scroll_offset(cursor: int, width: int, offset: int) -> int:
    """The smallest shift of the visible window that keeps the cursor inside it.

    The cursor sits one past the last character when appending, so the window
    has to admit column width - 1 as well as every character before it.
    """
    if width <= 0:
        return 0
    if cursor < offset:
        return cursor
    if cursor > offset + width - 1:
        return cursor - width + 1
    return offset
