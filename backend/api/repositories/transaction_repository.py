"""Django API wrapper / re-export for TransactionRepository."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from repositories.transaction_repository import TransactionRepository  # noqa: E402

__all__ = ["TransactionRepository"]
