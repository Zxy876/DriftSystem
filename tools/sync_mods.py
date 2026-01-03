#!/usr/bin/env python3
"""Synchronise Ideal City mods into the server runtime and refresh backend cache.

Usage example:
    python tools/sync_mods.py --mods-root mods --server-root server/idealcity_mods \
        --backend http://localhost:8000

The script copies every directory under --mods-root containing a mod.json manifest
into the server directory, preserving the folder structure. After a successful
sync it triggers the backend /ideal-city/mods/refresh endpoint so natural
language submissions will immediately see the new manifests.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional

import requests

DEFAULT_BACKEND = "http://localhost:8000"
DEFAULT_MODS_ROOT = Path("mods")
DEFAULT_SERVER_ROOT = Path("server/idealcity_mods")


def iter_mod_folders(mods_root: Path) -> Iterable[Path]:
    if not mods_root.exists():
        return []
    return [path for path in mods_root.iterdir() if (path / "mod.json").exists()]


def load_manifest(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[mods-sync] skip {path}: {exc}")
        return None


def copy_mod(src: Path, dest_root: Path) -> Optional[str]:
    manifest_path = src / "mod.json"
    manifest = load_manifest(manifest_path)
    if not manifest:
        return None
    mod_id = manifest.get("mod_id")
    if not mod_id:
        print(f"[mods-sync] skip {src}: missing mod_id")
        return None
    dest_dir = dest_root / src.name
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src, dest_dir)
    print(f"[mods-sync] copied {src} -> {dest_dir}")
    return mod_id


def refresh_backend(backend_url: str) -> bool:
    try:
        resp = requests.post(f"{backend_url.rstrip('/')}/ideal-city/mods/refresh", timeout=10)
        resp.raise_for_status()
        print(f"[mods-sync] backend refresh ok: {resp.json().get('status')}")
        return True
    except requests.RequestException as exc:
        print(f"[mods-sync] backend refresh failed: {exc}")
        return False


def summarise_queue(queue_file: Path) -> None:
    if not queue_file.exists():
        print(f"[mods-sync] queue file {queue_file} not found; skipping")
        return
    print("[mods-sync] pending build plans:")
    for line in queue_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(f"  - {payload.get('plan_id')}: {payload.get('summary')}")
        steps = payload.get("steps", [])
        for step in steps[:3]:
            title = step.get("title")
            desc = step.get("description")
            print(f"      • {title}: {desc}")
        remaining = max(0, len(steps) - 3)
        if remaining:
            print(f"      • ... {remaining} more steps")
        hooks = payload.get("mod_hooks") or []
        if hooks:
            print(f"      • mod hooks: {', '.join(hooks)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Sync Ideal City mods and refresh backend cache.")
    parser.add_argument("--mods-root", type=Path, default=DEFAULT_MODS_ROOT,
                        help="Directory containing mod folders (default: mods)")
    parser.add_argument("--server-root", type=Path, default=DEFAULT_SERVER_ROOT,
                        help="Destination directory inside the Minecraft server")
    parser.add_argument("--backend", default=DEFAULT_BACKEND,
                        help="Backend base URL for /ideal-city/mods/refresh")
    parser.add_argument("--queue", type=Path,
                        default=Path("backend/data/ideal_city/build_queue/build_queue.jsonl"),
                        help="Path to build_queue.jsonl for summary output")
    parser.add_argument("--dry-run", action="store_true", help="Only list actions without copying")
    args = parser.parse_args(argv)

    mods_root = args.mods_root
    server_root = args.server_root
    server_root.mkdir(parents=True, exist_ok=True)

    manifests_synced = []
    for folder in iter_mod_folders(mods_root):
        if args.dry_run:
            print(f"[mods-sync] would copy {folder} -> {server_root / folder.name}")
            continue
        mod_id = copy_mod(folder, server_root)
        if mod_id:
            manifests_synced.append(mod_id)

    if not args.dry_run and manifests_synced:
        refresh_backend(args.backend)
    elif not manifests_synced:
        print("[mods-sync] no mod manifests found; nothing to copy")

    summarise_queue(args.queue)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
