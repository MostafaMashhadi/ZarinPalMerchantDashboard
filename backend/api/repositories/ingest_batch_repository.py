"""Django API wrapper / re-export for IngestBatchRepository."""

import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from repositories.ingest_batch_repository import (  # noqa: E402
    DuplicateBatchError,
    IngestBatchError,
    IngestBatchRecord,
    IngestBatchRepository,
)

__all__ = [
    "DuplicateBatchError",
    "IngestBatchError",
    "IngestBatchRecord",
    "IngestBatchRepository",
]
