"""Check tracked files for accidentally committed credentials.

Only file names, line numbers and finding kinds are printed. Matching values
are never echoed, so the check is safe to run in CI logs or a shared chat.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "telegram-token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
    "long-secret-assignment": re.compile(
        r"(?i)\b(secret|token|password|api[_-]?key)\b\s*=\s*"
        r"['\"]?[A-Za-z0-9_./+-]{32,}"
    ),
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pptx", ".pdf", ".ico", ".woff2"}


def main() -> int:
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    findings: list[str] = []
    for name in files:
        if not name or Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        path = Path(name)
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{name}:{number}: {kind}")

    if findings:
        print("Потенциальные секреты в отслеживаемых файлах:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print("Секретов в отслеживаемых файлах не найдено")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
