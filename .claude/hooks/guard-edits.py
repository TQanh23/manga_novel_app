#!/usr/bin/env python3
"""PreToolUse guard for Edit/Write/MultiEdit. Blocks edits CLAUDE.md forbids.

Exit code 2 blocks the tool call and shows stderr to Claude.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

project = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
payload = json.load(sys.stdin)
raw = payload.get("tool_input", {}).get("file_path")
if not raw:
    sys.exit(0)
path = Path(raw).resolve()
try:
    rel = path.relative_to(project).as_posix()
except ValueError:
    sys.exit(0)


def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def on_main(rel_path: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ["git", "cat-file", "-e", f"origin/main:{rel_path}"],  # noqa: S607
        cwd=project,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


name = path.name
if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
    block(f"{rel} holds local secrets. Put new variables in .env.example with a dev default.")

if rel.startswith("api/migrations/versions/") and path.exists() and on_main(rel):
    block(
        f"{rel} is already on main, so it may be applied. Never edit an applied "
        "migration; add a new one (see the db-migration skill)."
    )

if rel.startswith("app/src/api/generated/") or rel == "app/openapi.json":
    block(f"{rel} is generated. Change the API and run `cd app && npm run gen:api`.")
