#!/bin/bash
set -e

# Add Arcanist to PATH
export PATH="$PATH:/app/arcanist/bin"

# Export custom PROJECT_PATH if provided (for use by the app/scripts)
# Note: The actual working directory for hg commands is set via HG_REPO_ROOT env var
# which fits the server.py logic.

echo "Starting Mercurial MCP Container..."

# Basic validation
if [ ! -d "/app/repo/.hg" ]; then
    echo "WARNING: /app/repo does not appear to be a Mercurial repository. Did you mount it correctly?"
else
    echo "Found Mercurial repository at /app/repo."
fi

if ! command -v arc &> /dev/null; then
    echo "WARNING: 'arc' command not found. Did you mount the Arcanist directory to /app/arcanist?"
else
    echo "Arcanist found: $(arc version | head -n 1)"
fi

# Run the server
echo "Starting MCP Server..."
python server.py
