"""Convenience entrypoint for ``python -m scripts.seed``."""

from __future__ import annotations

import asyncio

from scripts.seed_data import main

if __name__ == "__main__":
    asyncio.run(main())
