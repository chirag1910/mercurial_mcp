#!/bin/bash
export HOME=/home/chirag
export PATH="$PATH:/home/chirag/Documents/arcanist/bin"
cd /home/chirag/repo/mercurial_mcp
source .venv/bin/activate
python3 server.py
