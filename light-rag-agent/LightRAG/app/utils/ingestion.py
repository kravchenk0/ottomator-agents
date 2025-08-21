"""Utilities for incremental document ingestion into LightRAG.

Mechanism:
 - Maintain a JSON index (ingested_files.json) in working_dir with file hash & size.
 - Avoid re-ingesting unchanged files.
 - Provide helper functions used by API endpoints.
 - Optimized with parallel processing and batching for improved performance.
"""
from __future__ import annotations

import json
import hashlib
import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple
from concurrent.futures import ThreadPoolExecutor

INDEX_FILENAME = "ingested_files.json"
SUPPORTED_EXT = {".txt", ".md", ".rst", ".py", ".json", ".yaml", ".yml", ".csv", ".log", ".html", ".htm", ".xml"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB safety cap

# Performance optimization settings
DEFAULT_BATCH_SIZE = int(os.getenv("RAG_INGEST_BATCH_SIZE", "10"))
DEFAULT_MAX_WORKERS = int(os.getenv("RAG_INGEST_MAX_WORKERS", "4"))
DEFAULT_CONCURRENT_INSERTS = int(os.getenv("RAG_INGEST_CONCURRENT_INSERTS", "3"))


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


def _process_file_sync(file_path: Path) -> Tuple[Path, str, bytes, int, str | None]:
    """Process a single file synchronously for parallel execution.
    
    Returns: (file_path, status, content_bytes, size, error_message)
    """
    try:
        size = file_path.stat().st_size
        if size == 0 or size > MAX_FILE_BYTES:
            return file_path, "skip", b"", size, "size_limit_or_empty"
        
        content_bytes = file_path.read_bytes()
        return file_path, "ready", content_bytes, size, None
    except Exception as e:
        return file_path, "error", b"", 0, str(e)


async def _process_files_parallel(files: List[Path], max_workers: int = None) -> List[Tuple[Path, str, bytes, int, str | None]]:
    """Process multiple files in parallel using ThreadPoolExecutor."""
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [loop.run_in_executor(executor, _process_file_sync, fp) for fp in files]
        return await asyncio.gather(*tasks)


def scan_directory(directory: str | Path) -> List[Path]:
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        return []
    files: List[Path] = []
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
    return files


async def ingest_files(rag, files: Iterable[Path], working_dir: str | Path, 
                      batch_size: int = None, max_workers: int = None, 
                      concurrent_inserts: int = None) -> Dict[str, Any]:  # rag: LightRAG
    """Optimized file ingestion with parallel processing and batching.
    
    Args:
        rag: LightRAG instance
        files: Files to ingest
        working_dir: Working directory for index
        batch_size: Number of files to process in each batch
        max_workers: Max threads for parallel file processing
        concurrent_inserts: Max concurrent RAG insertions
    """
    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    if concurrent_inserts is None:
        concurrent_inserts = DEFAULT_CONCURRENT_INSERTS
    
    start_time = time.time()
    idx = load_index(working_dir)
    added, skipped = 0, 0
    details: List[Dict[str, Any]] = []
    
    files_list = list(files)
    if not files_list:
        return {"added": 0, "skipped": 0, "details": [], "total_indexed": len(idx)}
    
    # Process files in batches
    for i in range(0, len(files_list), batch_size):
        batch = files_list[i:i + batch_size]
        
        # Step 1: Process files in parallel (I/O bound)
        processed_files = await _process_files_parallel(batch, max_workers)
        
        # Step 2: Filter files that need ingestion and prepare for insertion
        texts_to_insert = []
        updates_to_index = {}
        
        for fp, status, content_bytes, size, error in processed_files:
            if status == "skip":
                details.append({"file": str(fp), "status": "skip", "reason": error})
                skipped += 1
            elif status == "error":
                details.append({"file": str(fp), "status": "error", "error": error})
            elif status == "ready":
                try:
                    h = compute_hash(content_bytes)
                    if not should_ingest(fp, idx, h):
                        details.append({"file": str(fp), "status": "skip", "reason": "unchanged"})
                        skipped += 1
                        continue
                    
                    text = content_bytes.decode("utf-8", errors="ignore")
                    texts_to_insert.append((fp, text, h, size))
                except Exception as e:  # noqa: BLE001
                    details.append({"file": str(fp), "status": "error", "error": str(e)})
        
        # Step 3: Insert texts concurrently with controlled concurrency
        if texts_to_insert:
            semaphore = asyncio.Semaphore(concurrent_inserts)
            
            async def insert_with_semaphore(fp: Path, text: str, h: str, size: int):
                async with semaphore:
                    try:
                        await rag.ainsert(text)
                        updates_to_index[str(fp)] = {"hash": h, "size": size}
                        details.append({"file": str(fp), "status": "ingested"})
                        return True
                    except Exception as e:  # noqa: BLE001
                        details.append({"file": str(fp), "status": "error", "error": str(e)})
                        return False
            
            # Run insertions concurrently
            insert_tasks = [insert_with_semaphore(fp, text, h, size) for fp, text, h, size in texts_to_insert]
            results = await asyncio.gather(*insert_tasks, return_exceptions=True)
            
            # Count successful insertions
            batch_added = sum(1 for r in results if r is True)
            added += batch_added
            
            # Update index with successful insertions
            idx.update(updates_to_index)
            
            # Save index after each batch to avoid losing progress
            save_index(working_dir, idx)
    
    total_time = time.time() - start_time
    files_per_second = len(files_list) / total_time if total_time > 0 else 0
    
    return {
        "added": added, 
        "skipped": skipped, 
        "details": details, 
        "total_indexed": len(idx),
        "performance": {
            "total_files": len(files_list),
            "processing_time_seconds": round(total_time, 2),
            "files_per_second": round(files_per_second, 2),
            "batch_size": batch_size,
            "max_workers": max_workers,
            "concurrent_inserts": concurrent_inserts
        }
    }


# Legacy function for backward compatibility
async def ingest_files_legacy(rag, files: Iterable[Path], working_dir: str | Path) -> Dict[str, Any]:
    """Legacy sequential ingestion function for compatibility."""
    return await ingest_files(rag, files, working_dir, batch_size=1, max_workers=1, concurrent_inserts=1)


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
