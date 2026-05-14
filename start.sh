#!/bin/bash
set -e
PY=$(command -v python3 || command -v python)
exec "$PY" run.py
