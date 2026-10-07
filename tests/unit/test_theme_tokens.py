"""
T9 theme guards (docs/design-better-ui.md §4.6 and §4.10). Pure Python; no Docker, no browser.

- Token structure, parity and WCAG contrast, parsed from frontend/theme/tokens.css.
- A scan of frontend/{host,player,admin}/src for raw palette classes and other banned class
  patterns, plus self-tests of the scan's own patterns (a broken regex would pass silently).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOKENS_CSS = REPO / "frontend" / "theme" / "tokens.css"
PRESET_TS = REPO / "frontend" / "theme" / "preset.ts"
APPS = ("host", "player", "admin")

# ---------------------------------------------------------------------------
# tokens.css parsing (§4.3.3)
# ---------------------------------------------------------------------------

INVARIANT = ":root"
LIGHT = ":root, [data-theme=light]"
DARK = "[data-theme=dark]"
DENSITY = ("[data-density=compact]", "[data-density=projector]")
PROPERTY_ONLY = ("html", "html[data-theme=dark]", "body")
KNOWN_SELECTORS = {INVARIANT, LIGHT, DARK, *DENSITY, *PROPERTY_ONLY}

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def parse_blocks(css: str) -> list[tuple[str, dict[str, str]]]:
    css = _COMMENT.sub("", css)
    blocks = []
    for selector, body in _RULE.findall(css):
        selector = " ".join(selector.split())
        blocks.append(
            (selector, {name: value.strip() for name, value in _VAR.findall(body)})
        )
    return blocks


def themes() -> dict[str, dict[str, str]]:
    blocks = dict(parse_blocks(TOKENS_CSS.read_text()))
    return {
        "light": {**blocks[INVARIANT], **blocks[LIGHT]},
        "dark": {**blocks[INVARIANT], **blocks[DARK]},
    }


def test_tokens_css_structure():
    blocks = parse_blocks(TOKENS_CSS.read_text())
    selectors = [s for s, _ in blocks]
    assert len(selectors) == len(set(selectors)), (
        f"every selector must be unique: {selectors}"
    )
    assert set(selectors) == KNOWN_SELECTORS, (
        f"unexpected or missing blocks: {set(selectors) ^ KNOWN_SELECTORS}"
    )
    for selector, variables in blocks:
        if selector in PROPERTY_ONLY:
            assert not variables, (
                f"{selector} must hold no custom properties, found {sorted(variables)}"
            )
        if selector in DENSITY:
            assert all(v.startswith("--nb-") for v in variables), (
                f"{selector} may only override --nb-* variables"
            )


def test_token_parity():
    blocks = dict(parse_blocks(TOKENS_CSS.read_text()))
    light, dark, invariant = (
        set(blocks[LIGHT]),
        set(blocks[DARK]),
        set(blocks[INVARIANT]),
    )
    assert light == dark, (
        f"light-only: {sorted(light - dark)}; dark-only: {sorted(dark - light)}"
    )
    assert not (invariant & light), (
        f"invariant variables redefined per theme: {sorted(invariant & light)}"
    )


def test_every_preset_token_is_defined():
    tokens = re.search(
        r"const TOKENS = \[(.*?)\] as const", PRESET_TS.read_text(), re.S
    )
    assert tokens, "preset.ts TOKENS list not found"
    names = re.findall(r"'([\w-]+)'", tokens.group(1))
    for theme, variables in themes().items():
        missing = [n for n in names if f"--{n}" not in variables]
        assert not missing, (
            f"{theme} theme is missing tokens used by preset.ts: {missing}"
        )


# ---------------------------------------------------------------------------
# WCAG 2.1 contrast (§4.2)
# ---------------------------------------------------------------------------

_CHANNELS = re.compile(r"^(\d{1,3}) (\d{1,3}) (\d{1,3})$")


def luminance(rgb: tuple[int, int, int]) -> float:
    def lin(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def channels(variables: dict[str, str]) -> dict[str, tuple[int, int, int]]:
    out = {}
    for name, value in variables.items():
        m = _CHANNELS.match(value)
        if m:  # --pin-* and density variables are skipped: not RGB channels
            out[name[2:]] = tuple(int(x) for x in m.groups())
    return out


SURFACES = ("canvas", "surface", "surface-muted")
FILLS = (
    "accent",
    "accent-2",
    "info",
    "success",
    "danger",
    "warning",
    *(f"option-{i}" for i in range(1, 9)),
)
PAIRS = (
    [(fg, bg, 4.5) for fg in ("ink", "ink-muted") for bg in SURFACES]
    + [("on-fill", bg, 4.5) for bg in (*FILLS, "image-bg", "qr-bg")]
    + [
        (fg, bg, 4.5)
        for fg in ("success-text", "danger-text", "warning-text")
        for bg in SURFACES
    ]
    + [("line", bg, 3.0) for bg in SURFACES]
    + [("focus", bg, 3.0) for bg in ("canvas", "surface")]
)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_token_contrast(theme):
    colours = channels(themes()[theme])
    failures = [
        f"{fg} on {bg}: {ratio(colours[fg], colours[bg]):.2f} < {minimum}"
        for fg, bg, minimum in PAIRS
        if ratio(colours[fg], colours[bg]) < minimum
    ]
    assert not failures, f"{theme} theme fails WCAG AA:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Class-rule scan (§4.6)
# ---------------------------------------------------------------------------

PALETTE = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|"
    "indigo|violet|purple|fuchsia|pink|rose|white|black"
)
FILL_TOKENS = r"accent-2|accent|info|success|danger|warning|option-\d"

# Rules applied to every string literal in .ts/.tsx (Tailwind classes always live in strings).
STRING_RULES: dict[str, re.Pattern[str]] = {
    "raw palette class": re.compile(
        r"\b(bg|text|border(-[trblxyse])?|ring|ring-offset|outline|from|via|to|fill|stroke|divide|placeholder"
        rf"|accent|caret|decoration|shadow)-({PALETTE})\b"
    ),
    "focus removed (outline-none)": re.compile(r"\boutline-none\b"),
    "focus ring utility": re.compile(r"\b(focus|focus-visible|focus-within):ring\b"),
    "ring-offset utility": re.compile(r"\bring-offset\b"),
    "opacity on a fill token": re.compile(rf"\b(bg|border|text)-({FILL_TOKENS})/\d+"),
    "opacity on text": re.compile(r"\btext-[a-z][\w-]*/\d+"),
    "element opacity outside disabled:": re.compile(r"(?<![\w:-])opacity-\d+"),
    "unloaded font weight": re.compile(r"\bfont-(black|extrabold)\b"),
    "soft radius": re.compile(r"\brounded-(?:[trblse]{1,2}-)?(sm|md|lg|xl|2xl|3xl)\b"),
    "soft shadow": re.compile(
        r"(?<![\w-])shadow(?:-(sm|md|lg|xl|2xl|inner))?(?![\w-])"
    ),
    "blur": re.compile(r"\b(backdrop-blur|blur|drop-shadow)(-[a-z0-9]+)?\b"),
    "hex colour": re.compile(r"#[0-9a-fA-F]{3,8}\b"),
    "rgb()/hsl() literal": re.compile(r"\b(rgba?|hsla?)\("),
    "named colour string": re.compile(
        r"^(white|black|red|green|blue|yellow|gray|grey|orange|purple|pink)$"
    ),
}
PLAYER_PAGE_RULES = {
    "page sized by min-h-screen/min-h-full": re.compile(r"\bmin-h-(screen|full)\b")
}
JSX_ATTR_COLOUR = re.compile(
    r"\b(fill|stroke|color)=\{?[\"'](?!currentColor|none)[a-z]+[\"']"
)

NB_TYPE = re.compile(r"\bnb-(h1|h2|h3|body|prompt|caption|stat|hero|code)\b")
TYPE_UTILITY = re.compile(
    r"\btext-(xs|sm|base|lg|[2-9]?xl)\b|\bfont-(normal|medium|semibold|bold)\b|\btracking-[\w-]+|\bleading-[\w-]+"
)
NB_SPACE = re.compile(r"\bnb-(page|card|stack)\b")
SPACE_UTILITY = re.compile(r"\b(p|px|py|pt|pb|pl|pr)-\d|\b(gap|space-y|space-x)-\d")
FONT_DISPLAY = re.compile(r"\bfont-display\b")
LIGHT_WEIGHT = re.compile(r"\bfont-(normal|medium|semibold)\b")

# A colour inside the fallback (third argument, one string literal) of cssVar() is not styling (§4.6).
CSSVAR_FALLBACK = re.compile(
    r"""cssVar\(\s*[^,()]+,\s*(['"])--[\w-]+\1\s*,\s*(['"])([^'"]*)\2\s*\)"""
)
ALLOW_COLOUR_FILES = {
    "host/src/lib/imageFile.ts"
}  # JPEG flatten background for uploads, not UI

_LINE_COMMENT = re.compile(r"(^|[\s;{}()])//[^\n]*")
_STRING = re.compile(
    r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|`(?:[^`\\]|\\.)*`", re.S
)


@dataclass
class Violation:
    path: str
    line: int
    rule: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.text.strip()[:100]}"


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def strip_comments(source: str) -> str:
    """Replace comments with spaces, keeping offsets and line numbers."""
    for m in reversed(list(_COMMENT.finditer(source))):
        source = _blank(source, m.start(), m.end())
    for m in reversed(list(_LINE_COMMENT.finditer(source))):
        source = _blank(source, m.start() + len(m.group(1)), m.end())
    return source


def blank_cssvar_fallbacks(source: str) -> str:
    for m in reversed(list(CSSVAR_FALLBACK.finditer(source))):
        source = _blank(source, m.start(3), m.end(3))
    return source


def cn_argument_strings(source: str) -> list[tuple[int, str]]:
    """All string literals inside each cn(...) call, joined: one class string per call (§4.6)."""
    out = []
    for m in re.finditer(r"\bcn\(", source):
        depth, i = 1, m.end()
        while i < len(source) and depth:
            if source[i] in "'\"`":
                s = _STRING.match(source, i)
                i = s.end() if s else i + 1
                continue
            depth += {"(": 1, ")": -1}.get(source[i], 0)
            i += 1
        literals = [s.group(0)[1:-1] for s in _STRING.finditer(source, m.end(), i)]
        out.append((m.start(), " ".join(literals)))
    return out


def scan_source(rel_path: str, source: str) -> list[Violation]:
    source = strip_comments(source)
    if rel_path.endswith(".css"):
        return [
            Violation(
                rel_path,
                source.count("\n", 0, m.start()) + 1,
                "hex colour in index.css",
                m.group(0),
            )
            for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", source)
        ]
    source = blank_cssvar_fallbacks(source)
    line_of = lambda pos: source.count("\n", 0, pos) + 1  # noqa: E731
    found: list[Violation] = []
    rules = dict(STRING_RULES)
    if rel_path.startswith("player/src/pages/"):
        rules.update(PLAYER_PAGE_RULES)
    if rel_path in ALLOW_COLOUR_FILES:
        for name in ("hex colour", "rgb()/hsl() literal"):
            rules.pop(name)

    class_strings: list[tuple[int, str]] = []
    for m in _STRING.finditer(source):
        body = m.group(0)[1:-1]
        class_strings.append((m.start(), body))
        for name, pattern in rules.items():
            if pattern.search(body):
                found.append(Violation(rel_path, line_of(m.start()), name, body))
    for m in JSX_ATTR_COLOUR.finditer(source):
        found.append(
            Violation(
                rel_path, line_of(m.start()), "named colour attribute", m.group(0)
            )
        )

    # Mixing rules work on whole class strings: each literal, and each cn(...) call's literals together.
    for pos, text in class_strings + cn_argument_strings(source):
        if NB_TYPE.search(text) and TYPE_UTILITY.search(text):
            found.append(
                Violation(
                    rel_path,
                    line_of(pos),
                    ".nb-* type class mixed with a size/weight utility",
                    text,
                )
            )
        if NB_SPACE.search(text) and SPACE_UTILITY.search(text):
            found.append(
                Violation(
                    rel_path,
                    line_of(pos),
                    ".nb-* spacing class mixed with padding/gap",
                    text,
                )
            )
        if FONT_DISPLAY.search(text) and LIGHT_WEIGHT.search(text):
            found.append(
                Violation(rel_path, line_of(pos), "font-display is always 700", text)
            )
    return found


def scan_repo() -> list[Violation]:
    found = []
    for app in APPS:
        root = REPO / "frontend" / app / "src"
        for path in sorted(root.rglob("*")):
            if path.suffix in (".ts", ".tsx", ".css") and path.is_file():
                rel = path.relative_to(REPO / "frontend").as_posix()
                found += scan_source(rel, path.read_text())
    return found


@pytest.mark.xfail(
    strict=True,
    reason="pages are migrated in step 4; this flips with REPLACE_DEFAULT_SCALES",
)
def test_no_raw_palette_or_forbidden_classes():
    violations = scan_repo()
    assert not violations, f"{len(violations)} theme violations:\n" + "\n".join(
        map(str, violations)
    )


@pytest.mark.parametrize(
    "path, source, flagged",
    [
        ("host/src/x.tsx", '<div className="border-t-slate-700" />', True),
        ("host/src/x.tsx", '<b className="hover:bg-indigo-500" />', True),
        ("host/src/x.tsx", '<i className="text-white" />', True),
        ("host/src/x.tsx", '<input className="focus:outline-none" />', True),
        (
            "host/src/x.tsx",
            '<input className="focus:ring-2 focus:ring-indigo-500" />',
            True,
        ),
        ("host/src/x.tsx", '<b className="ring-offset-2" />', True),
        ("host/src/x.tsx", '<b className="bg-accent/40 text-on-fill" />', True),
        ("host/src/x.tsx", '<b className="text-ink/50" />', True),
        ("host/src/x.tsx", '<b className="opacity-50" />', True),
        ("host/src/x.tsx", '<b className="font-black" />', True),
        ("host/src/x.tsx", '<b className="rounded-xl" />', True),
        ("host/src/x.tsx", '<b className="rounded-t-lg" />', True),
        ("host/src/x.tsx", '<b className="shadow-xl" />', True),
        ("host/src/x.tsx", '<b className="p-4 shadow" />', True),
        ("host/src/x.tsx", '<b className="backdrop-blur-sm" />', True),
        ("host/src/x.tsx", "const c = '#ff0000';", True),
        ("host/src/x.tsx", "ctx.strokeStyle = 'white';", True),
        ("host/src/x.tsx", '<path fill="black" />', True),
        ("host/src/x.tsx", "cn('nb-hero', big && 'tracking-tight')", True),
        ("host/src/x.tsx", "cn('nb-h1', cond && 'text-xl')", True),
        ("host/src/x.tsx", '<div className="nb-card p-4" />', True),
        ("host/src/x.tsx", '<h2 className="font-display font-semibold" />', True),
        ("player/src/pages/JoinPage.tsx", '<div className="min-h-screen" />', True),
        ("player/src/pages/JoinPage.tsx", '<div className="min-h-full" />', True),
        ("host/src/index.css", "body { color: #fff; }", True),
        # allowed
        ("host/src/x.tsx", "cssVar(c, '--x', '#fff')", False),
        (
            "host/src/x.tsx",
            "ctx.fillStyle = cssVar(canvas, '--pin-full-fill', 'rgba(74, 222, 128, 0.3)');",
            False,
        ),
        (
            "host/src/x.tsx",
            '<div className="bg-surface/80 border-line shadow-brutal" />',
            False,
        ),
        (
            "host/src/x.tsx",
            '<div className="bg-scrim/60 shadow-none rounded rounded-full" />',
            False,
        ),
        (
            "host/src/x.tsx",
            '<b className="disabled:opacity-60 bg-accent text-on-fill" />',
            False,
        ),
        ("host/src/x.tsx", '<h1 className="nb-h1 text-ink mb-4" />', False),
        ("host/src/x.tsx", '<h2 className="font-display font-bold" />', False),
        ("host/src/x.tsx", '<svg fill="none" stroke="currentColor" />', False),
        ("host/src/x.tsx", "// bg-slate-800 in a comment\n/* text-white */", False),
        ("host/src/x.tsx", "<p>A drop shadow, in prose</p>", False),
        ("host/src/lib/imageFile.ts", "drawScaled(img, MAX_SIDE, '#ffffff')", False),
        (
            "host/src/pages/HomePage.tsx",
            '<div className="min-h-screen" />',
            False,
        ),  # min-h rule is player-only
    ],
)
def test_scan_patterns(path, source, flagged):
    violations = scan_source(path, source)
    assert bool(violations) is flagged, violations
