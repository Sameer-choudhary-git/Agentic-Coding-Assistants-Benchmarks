"""Versioned JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from library.models import Library
from library.serializers import library_from_dict, library_to_dict

SCHEMA_VERSION = 2
SUPPORTED_VERSIONS = (1, 2)


class StorageError(Exception):
    pass


def save(library: Library, path: Union[str, Path]) -> None:
    document: Dict[str, Any] = {"schema_version": SCHEMA_VERSION, **library_to_dict(library)}
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def load(path: Union[str, Path]) -> Library:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    version = document.get("schema_version")
    if version not in SUPPORTED_VERSIONS:
        raise StorageError(f"unsupported schema version: {version}")
    if version == 1:
        document = _migrate_v1(document)
    return library_from_dict(document)


def _migrate_v1(document: Dict[str, Any]) -> Dict[str, Any]:
    books = [{**book, "isbn": None} for book in document.get("books", [])]
    return {**document, "books": books, "schema_version": 2}
