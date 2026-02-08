#!/bin/bash
set -euo pipefail

cd /home/chirag/repo/mercurial_mcp
exec docker compose run --rm -T mercurial-mcp
