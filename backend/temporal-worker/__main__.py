"""Module entry point for temporal-worker."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from main import main

if __name__ == "__main__":
    asyncio.run(main())
