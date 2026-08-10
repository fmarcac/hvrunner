from __future__ import annotations

import curses
from types import SimpleNamespace

from hvrunner.tui.screens.base import Screen


class FakeScreen:
    """Enough of a curses window to drive Screen.run, recording its timeouts."""

    def __init__(self, keys: list[int]):
        self.keys = list(keys)
        self.timeouts: list[int] = []

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)

    def erase(self) -> None:
        pass

    def refresh(self) -> None:
        pass

    def getch(self) -> int:
        # Anything unconsumed ends the loop rather than hanging the test.
        return self.keys.pop(0) if self.keys else ord("q")


def fake_app(keys: list[int]) -> SimpleNamespace:
    return SimpleNamespace(screen=FakeScreen(keys), paint=None)


class Leaf(Screen):
    """Leaves on the first key it is given."""

    def draw(self):
        return None

    def handle(self, key: int) -> bool:
        return False


class Blocking(Leaf):
    poll_interval = None


class Polling(Leaf):
    poll_interval = 500


def test_a_screen_without_an_interval_blocks():
    app = fake_app([ord("q")])
    Blocking(app).run()
    assert app.screen.timeouts == [-1]


def test_a_polling_screen_sets_its_interval():
    app = fake_app([ord("q")])
    Polling(app).run()
    assert app.screen.timeouts == [500]


def test_a_poll_timeout_redraws_without_leaving():
    app = fake_app([-1, -1, ord("q")])
    Polling(app).run()
    assert app.screen.timeouts == [500, 500, 500]


def test_a_resize_redraws_without_leaving():
    app = fake_app([curses.KEY_RESIZE, ord("q")])
    Polling(app).run()
    assert app.screen.timeouts == [500, 500]


def test_a_nested_screen_does_not_steal_the_interval():
    """One stdscr: a nested screen used to leave its own timeout behind.

    The log feed opened from the library reset the timeout to blocking on the
    way out, after which the library stopped polling and the launch watcher
    only ran when a key happened to be pressed.
    """

    class Nested(Screen):
        poll_interval = 400

        def draw(self):
            return None

        def handle(self, key: int) -> bool:
            return False

    class Outer(Screen):
        poll_interval = 500

        def __init__(self, app):
            super().__init__(app)
            self.opened = False

        def draw(self):
            return None

        def handle(self, key: int) -> bool:
            if self.opened:
                return False
            self.opened = True
            Nested(self.app).run()
            return True

    app = fake_app([ord("l"), ord("x"), ord("q")])
    Outer(app).run()
    # 500 to start, 400 while nested, then 500 again. The old code left the
    # nested screen's restore of -1 in place here, and the outer never re-set it.
    assert app.screen.timeouts == [500, 400, 500]
