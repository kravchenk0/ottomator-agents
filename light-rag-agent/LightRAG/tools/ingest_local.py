#!/usr/bin/env python3
"""
Local ingestion CLI (no REST).

Usage examples:
  python tools/ingest_local.py --directory /app/documents/raw_uploads
  # or inside container name 'lightrag-api':
  # docker exec -it lightrag-api python tools/ingest_local.py --directory /app/documents/raw_uploads

By default, working_dir is taken from env RAG_WORKING_DIR (fallback /app/documents),
scan directory from --directory or env RAG_INGEST_DIR or <working_dir>/raw_uploads.
"""
from __future__ import annotations

import os
import sys
import argparse
import asyncio
import json
from pathlib import Path

from app.core import RAGConfig, RAGManager, get_default_config  # type: ignore
from app.utils.ingestion import scan_directory, ingest_files  # type: ignore


def _resolve_working_dir(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    return os.getenv("RAG_WORKING_DIR", "/app/documents")


def _resolve_scan_dir(cli_value: str | None, working_dir: str) -> str:
    if cli_value:
        return cli_value
    return os.getenv("RAG_INGEST_DIR", str(Path(working_dir) / "raw_uploads"))


async def _run(directory: str | None, working_dir: str | None, dry_run: bool) -> int:
    wd = _resolve_working_dir(working_dir)
    scan_dir = _resolve_scan_dir(directory, wd)

    # Ensure dir exists
    p = Path(scan_dir)
    if not p.exists() or not p.is_dir():
        print(json.dumps({
            "status": "error",
            "error": f"scan directory not found: {scan_dir}",
            "working_dir": wd,
        }, ensure_ascii=False))
        return 2

    files = scan_directory(p)
    if dry_run:
        print(json.dumps({
            "status": "dry_run",
            "directory": scan_dir,
            "working_dir": wd,
            "files": len(files),
            "note": "no changes applied",
        }, ensure_ascii=False))
        return 0

    # Initialize RAG
    try:
        config = RAGConfig(working_dir=wd)
        mgr = RAGManager(config)
        rag = await mgr.get_rag()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({
            "status": "error",
            "error": f"failed to initialize RAG: {e}",
            "working_dir": wd,
        }, ensure_ascii=False))
        return 3

    # Ingest
    res = await ingest_files(rag, files, wd)
    print(json.dumps({
        "status": "ok",
        "directory": scan_dir,
        "working_dir": wd,
        **res,
    }, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local ingestion without REST")
    parser.add_argument("--directory", help="Directory to scan for files", default=None)
    parser.add_argument("--working-dir", help="LightRAG working directory", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Scan only; do not ingest")
    args = parser.parse_args()

    # Basic env checks
    if not os.getenv("OPENAI_API_KEY"):
        # Ingest requires embeddings; warn clearly
        print(json.dumps({
            "status": "error",
            "error": "OPENAI_API_KEY is not set in environment",
            "hint": "export OPENAI_API_KEY=... inside container or host env",
        }, ensure_ascii=False))
        return 4

    return asyncio.run(_run(args.directory, args.working_dir, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
