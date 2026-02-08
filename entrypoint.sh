#!/bin/bash
set -e

# Add Arcanist to PATH
export PATH="$PATH:/app/arcanist/bin"

# Log to stderr to keep stdout clean for MCP JSON protocol
echo "Starting Mercurial MCP Container..." >&2

# Basic validation
if [ ! -d "/app/repo/.hg" ]; then
    echo "ERROR: /app/repo does not appear to be a Mercurial repository. Did you mount it correctly?" >&2
    exit 1
fi

if ! command -v arc &> /dev/null; then
    echo "ERROR: 'arc' command not found. Did you mount the Arcanist directory to /app/arcanist?" >&2
    exit 1
fi

# Run the server
echo "Starting MCP Server..." >&2
python server.py
