#!/usr/bin/env bash
# Double-clickable launcher for the Image to STL app.
# In your file manager, choose "Run" when prompted.
cd "$(dirname "$(readlink -f "$0")")"
exec python3 main.py
