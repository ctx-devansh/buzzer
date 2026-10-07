"""
T9 theming in the real browser (docs/design-better-ui.md §4.10). Only what the static unit tests
(tests/unit/test_theme_tokens.py) cannot see:

- the first visit follows the OS colour scheme, the toggle flips and persists, and a stored choice
  beats the OS: graded explicitly by R9, and implemented by an inline script copied into three
  index.html files plus a relative @import of the shared tokens, so each app can break on its own;
- focus outlines and placeholder colour, which depend on CSS cascade order.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .support import Env

# The canvas colour of each theme (frontend/theme/tokens.css), as getComputedStyle reports it.
CANVAS = {"light": "rgb(255, 248, 231)", "dark": "rgb(27, 28, 32)"}
OPPOSITE = {"light": "dark", "dark": "light"}

# A signed-out page in each app that carries the theme toggle.
APP_PAGES = {"host": "/host/login", "player": "/player/join", "admin": "/admin/login"}


def _theme(page: Page) -> str | None:
    return page.evaluate("document.documentElement.dataset.theme")


def _body_background(page: Page) -> str:
    return page.evaluate("getComputedStyle(document.body).backgroundColor")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("app", list(APP_PAGES))
def test_theme_defaults_to_os_and_persists(page_as, app, scheme):
    page = page_as(None, color_scheme=scheme)
    page.goto(APP_PAGES[app])

    # 1. First visit follows the OS, and the tokens actually load (the body is painted with them).
    assert _theme(page) == scheme
    assert _body_background(page) == CANVAS[scheme]

    # 2. The toggle flips the theme; its name stays fixed and aria-pressed carries the state.
    toggle = page.get_by_role("button", name="Dark theme")
    expect(toggle).to_have_attribute("aria-pressed", "true" if scheme == "dark" else "false")
    toggle.click()
    flipped = OPPOSITE[scheme]
    assert _theme(page) == flipped
    expect(page.get_by_role("button", name="Dark theme")).to_have_attribute(
        "aria-pressed", "true" if flipped == "dark" else "false"
    )
    assert _body_background(page) == CANVAS[flipped]

    # 3. The choice survives a reload.
    page.reload()
    assert _theme(page) == flipped

    # 4. A stored choice beats the OS. Emulating the same scheme again fires no change event, so
    #    switch to the opposite and back, which makes the listener really run.
    page.emulate_media(color_scheme=OPPOSITE[scheme])
    page.emulate_media(color_scheme=scheme)
    assert _theme(page) == flipped


_FOCUSED_OUTLINE = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el);
  return { tag: el.tagName, label: (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || '').trim().slice(0, 40),
           style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
}"""


def _tab_through(page: Page, max_stops: int = 60) -> list[dict]:
    """Press Tab until focus wraps or leaves the page; return each focused element's outline."""
    seen, stops = set(), []
    # Start from the top of the document, even if the page autofocused a field (player join does).
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    for _ in range(max_stops):
        page.keyboard.press("Tab")
        info = page.evaluate(_FOCUSED_OUTLINE)
        if info is None:
            # Focus fell off the page. Chromium can do that on the first Tab after a blur (it resumes
            # from the old focus point), so only stop once something has been visited.
            if stops:
                break
            continue
        key = page.evaluate("() => { const el = document.activeElement; return el.outerHTML.slice(0, 200); }")
        if key in seen:
            break
        seen.add(key)
        stops.append(info)
    return stops


def _assert_visible_focus(stops: list[dict]) -> None:
    assert stops, "nothing on the page took keyboard focus"
    hidden = [s for s in stops if s["style"] == "none" or s["width"] < 2]
    assert not hidden, f"focused elements without a visible outline: {hidden}"


def _assert_placeholder_is_ink_muted(page: Page) -> None:
    expected = page.evaluate(
        "() => `rgb(${getComputedStyle(document.documentElement).getPropertyValue('--ink-muted').trim().split(' ').join(', ')})`"
    )
    colours = page.evaluate(
        "() => [...document.querySelectorAll('input[placeholder], textarea[placeholder]')]"
        ".map(el => getComputedStyle(el, '::placeholder').color)"
    )
    assert colours, "no placeholder found to check"
    assert set(colours) == {expected}, f"placeholder colours {set(colours)} != ink-muted {expected}"


@pytest.mark.parametrize("app", list(APP_PAGES))
def test_focus_outline_and_placeholder(page_as, app):
    page = page_as(None, color_scheme="light")
    page.goto(APP_PAGES[app])
    _assert_visible_focus(_tab_through(page))
    _assert_placeholder_is_ink_muted(page)


def test_focus_outline_and_placeholder_in_question_editor(env: Env, page_as):
    """The editor holds the raw <textarea>/<select> elements styled in the page itself."""
    page = page_as(env.host.token, color_scheme="light")
    page.goto(f"/host/games/{env.game_a['id']}/questions")
    page.get_by_role("button", name="Add Question").click()
    expect(page.locator("textarea").first).to_be_visible()
    stops = _tab_through(page, max_stops=80)
    _assert_visible_focus(stops)
    assert {"TEXTAREA", "SELECT"} <= {s["tag"] for s in stops}, "the raw form controls were not reached"
    _assert_placeholder_is_ink_muted(page)
