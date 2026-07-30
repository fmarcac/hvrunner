"""Pure text shaping. Nothing here touches curses."""

from __future__ import annotations


def fit(text: str, width: int, ellipsis: str = "...") -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= len(ellipsis):
        return text[:width]
    return text[: width - len(ellipsis)] + ellipsis


def shorten_path(text: str, width: int, ellipsis: str = "...") -> str:
    """Keep the tail of a path, which is the part that identifies it."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= len(ellipsis):
        return text[-width:]
    return ellipsis + text[-(width - len(ellipsis)) :]


def letterspace(text: str, gap: int = 1) -> str:
    return (" " * gap).join(text)


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap. A word longer than width is left to be clipped."""
    if width <= 0:
        return []
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
