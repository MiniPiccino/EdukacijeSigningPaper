#!/usr/bin/env bash
set -euo pipefail

# Ensure the script always runs from the repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "Virtual environment directory '.venv' not found. Aborting." >&2
  exit 1
fi

source .venv/bin/activate

if [[ -z "${SKIP_GIT_PULL:-}" ]]; then
  git pull origin master
else
  echo "Skipping git pull because SKIP_GIT_PULL is set."
fi

pip install -r requirements.txt

sudo systemctl daemon-reload
sudo systemctl restart edukacije.service

echo "Tailing edukacije.service logs (press Ctrl+C to stop)..."
journalctl -u edukacije.service -f
