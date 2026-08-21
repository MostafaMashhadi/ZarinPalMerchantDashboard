#!/usr/bin/env bash
set -euo pipefail

echo "==> Running ClickHouse schema migrations..."
python -m ingestion.schema.migrate || true

echo "==> Ingestion service ready."
if [ "$#" -gt 0 ]; then
    exec "$@"
else
    echo "No CSV file specified. Keeping container idle."
    exec tail -f /dev/null
fi
