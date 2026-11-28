from __future__ import annotations

import html
import re

# Telegram's HTML mode supports only a small subset of tags. Keep our own
# formatting, escape everything else (including malformed provider output).
_ALLOWED_TAG_RE = re.compile(
    r"</?(?:b|strong|i|em|u|s|code|pre|a)(?:\s+[^<>]*)?/?>",
    re.IGNORECASE,
)


def esc(value: object) -> str:
    """Escape a value that is inserted into Telegram HTML markup."""
    return html.escape(str(value), quote=False)


def safe_html(value: object) -> str:
    """Keep allowlisted markup, escape all other HTML from dynamic text."""
    text = html.unescape(str(value))
    parts: list[str] = []
    position = 0
    for match in _ALLOWED_TAG_RE.finditer(text):
        parts.append(html.escape(text[position : match.start()], quote=False))
        parts.append(match.group(0))
        position = match.end()
    parts.append(html.escape(text[position:], quote=False))
    return "".join(parts)
