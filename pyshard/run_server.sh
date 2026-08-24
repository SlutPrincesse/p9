#!/bin/bash
set -e

echo "Starting PyShard-P9 backend..."
python3 -m uvicorn pyshard.server:app --host 0.0.0.0 --port 8000 --reload
