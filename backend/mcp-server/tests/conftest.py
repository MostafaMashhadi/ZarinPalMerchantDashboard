"""conftest for MCP server tests.

Ensures `api/` and `backend/` directories are on sys.path so that
shared packages and facades can be imported.
"""

from __future__ import annotations

import os
import sys

backend_dir = os.path.join(
    os.path.dirname(__file__), "..", ".."
)
api_dir = os.path.join(backend_dir, "api")

for p in (backend_dir, api_dir):
    if p not in sys.path:
        sys.path.insert(0, p)
