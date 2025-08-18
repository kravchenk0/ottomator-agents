"""Utilities for incremental document ingestion into LightRAG.

Mechanism:
 - Maintain a JSON index (ingested_files.json) in working_dir with file hash & size.
 - Avoid re-ingesting unchanged files.
 - Provide helper functions used by API endpoints.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Iterable, List

INDEX_FILENAME = "ingested_files.json"
SUPPORTED_EXT = {".txt", ".md", ".rst", ".py"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB safety cap


def _index_path(working_dir: str | Path) -> Path:
    p = Path(working_dir) / INDEX_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_index(working_dir: str | Path) -> Dict[str, Any]:
    path = _index_path(working_dir)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_index(working_dir: str | Path, data: Dict[str, Any]) -> None:
    path = _index_path(working_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def should_ingest(file_path: Path, idx: Dict[str, Any], content_hash: str) -> bool:
    rec = idx.get(str(file_path))
    if not rec:
        return True
    return rec.get("hash") != content_hash or rec.get("size") != file_path.stat().st_size


def scan_directory(directory: str | Path) -> List[Path]:
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        return []
    files: List[Path] = []
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
    return files


async def ingest_files(rag, files: Iterable[Path], working_dir: str | Path) -> Dict[str, Any]:  # rag: LightRAG
    idx = load_index(working_dir)
    added, skipped = 0, 0
    details: List[Dict[str, Any]] = []
    for fp in files:
        try:
            size = fp.stat().st_size
            if size == 0 or size > MAX_FILE_BYTES:
                details.append({"file": str(fp), "status": "skip", "reason": "size_limit_or_empty"})
                skipped += 1
                continue
            content = fp.read_bytes()
            h = compute_hash(content)
            if not should_ingest(fp, idx, h):
                details.append({"file": str(fp), "status": "skip", "reason": "unchanged"})
                skipped += 1
                continue
            text = content.decode("utf-8", errors="ignore")
            await rag.ainsert(text)
            idx[str(fp)] = {"hash": h, "size": size}
            details.append({"file": str(fp), "status": "ingested"})
            added += 1
        except Exception as e:  # noqa: BLE001
            details.append({"file": str(fp), "status": "error", "error": str(e)})
    save_index(working_dir, idx)
    return {"added": added, "skipped": skipped, "details": details, "total_indexed": len(idx)}


def list_index(working_dir: str | Path) -> List[Dict[str, Any]]:
    idx = load_index(working_dir)
    out = []
    for k, v in idx.items():
        out.append({"file": k, **v})
    return sorted(out, key=lambda x: x["file"])


def delete_from_index(working_dir: str | Path, files: Iterable[str | Path]) -> Dict[str, Any]:
    """Remove entries from ingestion index (does NOT remove vectors in LightRAG).

    Returns summary with counts and not_found list.
    """
    idx = load_index(working_dir)
    removed = 0
    not_found: List[str] = []
    for f in files:
        k = str(Path(f))
        if k in idx:
            del idx[k]
            removed += 1
        else:
            not_found.append(k)
    save_index(working_dir, idx)
    return {"removed": removed, "not_found": not_found, "total_indexed": len(idx)}


def clear_index(working_dir: str | Path) -> Dict[str, Any]:
    """Completely clear the ingestion index file."""
    save_index(working_dir, {})
    return {"cleared": True, "total_indexed": 0}
