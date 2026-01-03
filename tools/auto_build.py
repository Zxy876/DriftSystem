#!/usr/bin/env python3
"""Process Ideal City build plans and emit executable command logs."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.ideal_city.build_executor import BuildExecutor, CommandLogWriter  # noqa: E402
from app.core.ideal_city.build_scheduler import BuildScheduler, BuildSchedulerConfig  # noqa: E402
from app.core.minecraft.rcon_client import RconClient  # noqa: E402
from app.core.mods import ModManager  # noqa: E402


def resolve_data_root() -> Path:
    override = os.getenv("IDEAL_CITY_DATA_ROOT")
    if override:
        return Path(override)
    return BACKEND_ROOT / "data" / "ideal_city"


def process_once(executor: BuildExecutor) -> int:
    results = executor.process_all()
    if not results:
        print("[auto-build] no pending plans")
        return 0
    for result in results:
        status = result.status.value
        commands = ", ".join(result.commands) if result.commands else "<none>"
        print(f"[auto-build] plan {result.plan_id} -> {status} (commands: {commands})")
        if result.log_path:
            print(f"[auto-build]   log: {result.log_path}")
        if result.missing_mods:
            print(f"[auto-build]   missing mods: {', '.join(result.missing_mods)}")
        if result.dispatched:
            print("[auto-build]   dispatched via RCON")
        if result.dispatch_error:
            print(f"[auto-build]   dispatch error: {result.dispatch_error}")
    return 0


def configure_dispatcher(args: argparse.Namespace) -> Tuple[Optional[Callable[[list[str]], None]], Optional[str]]:
    if getattr(args, "no_dispatch", False):
        return None, None

    env_host = os.getenv("MINECRAFT_RCON_HOST")
    env_port = os.getenv("MINECRAFT_RCON_PORT")
    env_password = os.getenv("MINECRAFT_RCON_PASSWORD")

    host = args.rcon_host or env_host
    password = args.rcon_password or env_password

    port_value: Optional[int]
    if args.rcon_port is not None:
        port_value = args.rcon_port
    elif env_port:
        try:
            port_value = int(env_port)
        except ValueError:
            print(f"[auto-build] invalid RCON port from environment: {env_port}", file=sys.stderr)
            return None, None
    else:
        port_value = 25575

    if host and password:
        client = RconClient(host=host, port=port_value, password=password)
        return client.run, f"{host}:{port_value}"

    if host or password or args.rcon_port is not None:
        print("[auto-build] incomplete RCON configuration; host, port, and password required", file=sys.stderr)

    return None, None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Automate Ideal City build queue processing.")
    parser.add_argument("--watch", action="store_true", help="Continuously poll the queue")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds")
    parser.add_argument("--log-dir", type=Path, help="Directory for execution logs")
    parser.add_argument("--rcon-host", help="Minecraft server host for RCON dispatch")
    parser.add_argument("--rcon-port", type=int, help="Minecraft server RCON port")
    parser.add_argument("--rcon-password", help="Minecraft server RCON password")
    parser.add_argument("--no-dispatch", action="store_true", help="Disable command dispatch even if RCON is configured")
    args = parser.parse_args(argv)

    data_root = resolve_data_root()
    queue_root = data_root / "build_queue"
    scheduler = BuildScheduler(BuildSchedulerConfig(root_dir=queue_root))
    mod_manager = ModManager()
    log_dir = args.log_dir or (queue_root / "executed")
    log_writer = CommandLogWriter(log_dir)
    dispatcher, endpoint = configure_dispatcher(args)
    if endpoint:
        print(f"[auto-build] RCON dispatch enabled -> {endpoint}")
    executor = BuildExecutor(scheduler, mod_manager, log_writer, command_dispatcher=dispatcher)

    if not args.watch:
        return process_once(executor)

    print(f"[auto-build] watching {scheduler.queue_path}")
    try:
        while True:
            process_once(executor)
            time.sleep(max(0.5, args.interval))
    except KeyboardInterrupt:
        print("\n[auto-build] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
