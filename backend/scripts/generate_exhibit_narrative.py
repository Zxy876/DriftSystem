#!/usr/bin/env python3
"""Build ExhibitNarrative JSON payloads from curated Markdown sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SECTION_FILES = {
    "overview": "overview.md",
    "risks": "risks.md",
    "history": "history.md",
    "interpretation": "interpretation.md",
    "appendix": "appendix.md",
}


def parse_markdown_section(path: Path) -> Tuple[Dict[str, str], List[str]]:
    if not path.exists():
        return {}, []
    metadata: Dict[str, str] = {}
    entries: List[str] = []
    paragraph: List[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            if paragraph:
                entries.append(" ".join(paragraph))
                paragraph.clear()
            continue
        if line.startswith("#"):
            heading = line.lstrip("# ").strip()
            if heading:
                metadata.setdefault("heading", heading)
            continue
        lower = line.lower()
        if ":" in line and not line.startswith("- "):
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if key in {"timeframe", "mode", "title"}:
                metadata[key] = value.strip()
                continue
        if line.startswith("- "):
            if paragraph:
                entries.append(" ".join(paragraph))
                paragraph.clear()
            text = line[2:].strip()
            if text:
                entries.append(text)
        else:
            paragraph.append(line)
    if paragraph:
        entries.append(" ".join(paragraph))
    return metadata, entries


def dedupe(entries: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen: set[str] = set()
    for entry in entries:
        text = str(entry).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def build_payload(scenario_id: str, source_dir: Path) -> Dict[str, object]:
    overview_meta, overview_lines = parse_markdown_section(source_dir / SECTION_FILES["overview"])
    risks_meta, risks_lines = parse_markdown_section(source_dir / SECTION_FILES["risks"])
    history_meta, history_lines = parse_markdown_section(source_dir / SECTION_FILES["history"])
    interpretation_meta, interpretation_lines = parse_markdown_section(source_dir / SECTION_FILES["interpretation"])
    appendix_meta, appendix_lines = parse_markdown_section(source_dir / SECTION_FILES["appendix"])

    appendix_payload: Dict[str, List[str]] = {}
    if appendix_lines:
        label = appendix_meta.get("heading") or appendix_meta.get("title") or "附录"
        appendix_payload[label] = dedupe(appendix_lines)

    payload: Dict[str, object] = {
        "scenario_id": scenario_id,
        "title": overview_meta.get("title") or overview_meta.get("heading"),
        "timeframe": overview_meta.get("timeframe"),
        "mode": overview_meta.get("mode"),
        "archive_state": dedupe(overview_lines),
        "unresolved_risks": dedupe(risks_lines),
        "historic_notes": dedupe(history_lines),
        "city_interpretation": dedupe(interpretation_lines),
    }
    if appendix_payload:
        payload["appendix"] = appendix_payload
    return payload


def emit_payload(payload: Dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{payload['scenario_id']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def discover_scenarios(docs_root: Path, target: Optional[List[str]]) -> List[Tuple[str, Path]]:
    if target:
        return [
            (scenario_id, docs_root / scenario_id)
            for scenario_id in target
            if (docs_root / scenario_id).exists()
        ]
    scenarios: List[Tuple[str, Path]] = []
    for entry in sorted(docs_root.iterdir()):
        if not entry.is_dir():
            continue
        scenarios.append((entry.name, entry))
    return scenarios


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("docs/narratives"),
        help="Root directory containing scenario narrative markdown files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("backend/data/ideal_city/exhibits"),
        help="Destination directory for ExhibitNarrative JSON payloads.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        help="Optional scenario_id to limit generation. Can be specified multiple times.",
    )
    args = parser.parse_args(argv)

    docs_root = args.docs_root.resolve()
    output_root = args.output_root.resolve()
    if not docs_root.exists():
        raise SystemExit(f"docs root not found: {docs_root}")

    scenarios = discover_scenarios(docs_root, args.scenarios)
    if not scenarios:
        print("[narrative] no scenarios discovered; nothing to do")
        return 0

    for scenario_id, path in scenarios:
        payload = build_payload(scenario_id, path)
        dest = emit_payload(payload, output_root)
        print(f"[narrative] wrote {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
