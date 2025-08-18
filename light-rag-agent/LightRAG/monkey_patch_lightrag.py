"""Monkey patch для устранения KeyError: 'file_path' внутри LightRAG.

Цель: при вызове LightRAG.get_vector_context некоторые версии lightrag
(до фикса upstream) ожидали наличие поля file_path в элементах чанков,
что приводило к KeyError, если ingest не сохранил метадату.

Подход:
1. Патчим метод LightRAG.get_vector_context на уровне класса (однократно).
2. При возникновении KeyError('file_path') – проходим по известным kv-хранилищам
   и добавляем placeholder "unknown_source" в отсутствующие поля.
3. Повторяем вызов. Если снова KeyError – возвращаем пустой список и логируем ошибку.

Патч идемпотентен: повторный импорт не создаёт дополнительную вложенность.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from lightrag import LightRAG  # type: ignore
except Exception:  # pragma: no cover - если библиотека не установлена
    LightRAG = None  # type: ignore

logger = logging.getLogger(__name__)

_PATCH_APPLIED = False


def _inject_placeholders(self: Any) -> int:
    added = 0
    for attr_name in [
        "kv_store_full_docs",
        "kv_store_text_chunks",
        "kv_store_doc_status",
    ]:
        store = getattr(self, attr_name, None)
        if store is None:
            continue
        inner = getattr(store, "_store", None)
        if isinstance(inner, dict):
            for _k, _v in inner.items():
                if isinstance(_v, dict) and "file_path" not in _v:
                    _v["file_path"] = "unknown_source"
                    added += 1
    return added


def apply_lightrag_file_path_patch() -> bool:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return True
    if LightRAG is None or not hasattr(LightRAG, "get_vector_context"):
        logger.debug("LightRAG not present or get_vector_context missing; skip monkey patch")
        return False

    original = LightRAG.get_vector_context  # type: ignore[attr-defined]

    # Определяем — coroutine ли исходный метод
    import inspect
    is_async = inspect.iscoroutinefunction(original)

    if is_async:
        async def patched(self, *args, **kwargs):  # type: ignore[override]
            try:
                return await original(self, *args, **kwargs)
            except KeyError as e:  # noqa: BLE001
                if str(e).strip("'\"") == "file_path":
                    added = _inject_placeholders(self)
                    if added:
                        logger.warning(f"MonkeyPatch(get_vector_context): added placeholder file_path to {added} records; retrying")
                    try:
                        return await original(self, *args, **kwargs)
                    except KeyError as e2:  # noqa: BLE001
                        if str(e2).strip("'\"") == "file_path":
                            logger.error("MonkeyPatch(get_vector_context): still failing after placeholder injection; returning []")
                            return []
                        raise
                raise
    else:
        def patched(self, *args, **kwargs):  # type: ignore[override]
            try:
                return original(self, *args, **kwargs)
            except KeyError as e:  # noqa: BLE001
                if str(e).strip("'\"") == "file_path":
                    added = _inject_placeholders(self)
                    if added:
                        logger.warning(f"MonkeyPatch(get_vector_context-sync): added placeholder file_path to {added} records; retrying")
                    try:
                        return original(self, *args, **kwargs)
                    except KeyError as e2:  # noqa: BLE001
                        if str(e2).strip("'\"") == "file_path":
                            logger.error("MonkeyPatch(get_vector_context-sync): still failing; returning []")
                            return []
                        raise
                raise

    LightRAG.get_vector_context = patched  # type: ignore[assignment]
    _PATCH_APPLIED = True
    logger.info("Applied LightRAG get_vector_context monkey patch for missing file_path handling")
    return True


# Авто-применение при импорте
try:  # pragma: no cover
    apply_lightrag_file_path_patch()
except Exception as _e:  # noqa: BLE001
    logger.debug(f"Monkey patch application failed (non-fatal): {_e}")


def is_patch_applied() -> bool:
    return _PATCH_APPLIED
