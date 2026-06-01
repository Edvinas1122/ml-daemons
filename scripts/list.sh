#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

"$VENV/bin/python3" -c "
from huggingface_hub import scan_cache_dir
cache = scan_cache_dir()
repos = sorted(cache.repos, key=lambda r: r.repo_id)
for repo in repos:
    for rev in repo.revisions:
        size = rev.size_on_disk / 1024 / 1024
        print(f'{repo.repo_id:50s} {size:>8.1f} MB')
if not repos:
    print('No cached models found.')
"
