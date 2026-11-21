"""Minimal unified-diff parsing and in-memory patch application.

We avoid needing a full repository checkout: the code-quality module fetches
only the touched files at ``base_commit`` and applies hunks in memory.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

EXT_LANG = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".java": "java", ".kt": "kotlin", ".rs": "rust", ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".swift": "swift", ".scala": "scala",
}

TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|testing|__tests__|spec|specs)(/|$)|(_test\.(go|py|rs)$)|(^|/)test_[^/]*\.py$"
    r"|\.(test|spec)\.[jt]sx?$|Test[^/]*\.java$|_spec\.rb$|Tests?\.cs$"
)
DOC_PATH_RE = re.compile(r"\.(md|rst|txt|adoc)$|(^|/)(docs?|changelog|CHANGES)(/|$)", re.I)


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[str] = field(default_factory=list)  # with leading ' ', '+', '-'


@dataclass
class FileDiff:
    old_path: str | None
    new_path: str | None
    hunks: list[Hunk] = field(default_factory=list)
    is_binary: bool = False

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ""

    @property
    def is_new(self) -> bool:
        return self.old_path is None

    @property
    def is_deleted(self) -> bool:
        return self.new_path is None

    @property
    def added(self) -> list[str]:
        return [l[1:] for h in self.hunks for l in h.lines if l.startswith("+")]

    @property
    def removed(self) -> list[str]:
        return [l[1:] for h in self.hunks for l in h.lines if l.startswith("-")]


def _strip(p: str) -> str | None:
    p = p.strip().split("\t")[0]
    if p == "/dev/null":
        return None
    return p[2:] if p[:2] in ("a/", "b/") else p


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)", line)
            cur = FileDiff(m.group(1) if m else None, m.group(2) if m else None)
            files.append(cur)
            hunk = None
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            if cur is None or cur.hunks:
                cur = FileDiff(None, None)
                files.append(cur)
            cur.old_path = _strip(line[4:])
            cur.new_path = _strip(lines[i + 1][4:])
            i += 1
            hunk = None
        elif line.startswith("Binary files") and cur is not None:
            cur.is_binary = True
        elif line.startswith("new file mode") and cur is not None:
            cur.old_path = None
        elif line.startswith("deleted file mode") and cur is not None:
            cur.new_path = None
        elif (m := _HUNK_RE.match(line)) and cur is not None:
            hunk = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1))
            cur.hunks.append(hunk)
        elif hunk is not None and line[:1] in (" ", "+", "-"):
            hunk.lines.append(line)
        elif hunk is not None and line == "":
            hunk.lines.append(" ")
        i += 1
    return files


def language_of(path: str) -> str:
    return EXT_LANG.get(os.path.splitext(path)[1].lower(), "other")


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def is_doc_path(path: str) -> bool:
    return bool(DOC_PATH_RE.search(path))


def patch_stats(text: str) -> dict:
    files = parse_diff(text)
    src = [f for f in files if not is_test_path(f.path) and not is_doc_path(f.path)]
    added = sum(len(f.added) for f in files)
    removed = sum(len(f.removed) for f in files)
    langs: dict[str, int] = {}
    for f in src:
        lang = language_of(f.path)
        langs[lang] = langs.get(lang, 0) + len(f.added) + len(f.removed)
    return {
        "files": len(files),
        "source_files": len(src),
        "test_files": sum(is_test_path(f.path) for f in files),
        "new_files": sum(f.is_new for f in files),
        "hunks": sum(len(f.hunks) for f in files),
        "added": added,
        "removed": removed,
        "changed": added + removed,
        "languages": langs,
        "paths": [f.path for f in files],
    }


def dominant_language(text: str) -> str:
    langs = patch_stats(text)["languages"]
    langs.pop("other", None)
    return max(langs, key=langs.get) if langs else "other"


def apply_file_diff(original: str, fd: FileDiff) -> str:
    """Apply one file's hunks to ``original``. Tolerates line offsets (fuzz).

    Raises ValueError if a hunk's context cannot be located.
    """
    src = [] if fd.is_new else original.splitlines()
    out: list[str] = []
    pos = 0  # index into src
    for h in fd.hunks:
        old_block = [l[1:] for l in h.lines if l[:1] in (" ", "-")]
        new_block = [l[1:] for l in h.lines if l[:1] in (" ", "+")]
        expected = max(h.old_start - 1, 0)
        start = _locate(src, old_block, expected, pos)
        if start is None:
            raise ValueError(f"hunk @@ -{h.old_start} does not apply to {fd.path}")
        out.extend(src[pos:start])
        out.extend(new_block)
        pos = start + len(old_block)
    out.extend(src[pos:])
    return "\n".join(out) + ("\n" if out else "")


def _locate(src: list[str], block: list[str], expected: int, floor: int) -> int | None:
    if not block:
        return min(max(expected, floor), len(src))
    n = len(block)
    for delta in range(0, len(src) + 1):
        for cand in (expected - delta, expected + delta) if delta else (expected,):
            if cand < floor or cand + n > len(src):
                continue
            if src[cand:cand + n] == block:
                return cand
            # whitespace-insensitive fallback
            if [s.rstrip() for s in src[cand:cand + n]] == [b.rstrip() for b in block]:
                return cand
        if expected - delta < floor and expected + delta + n > len(src):
            break
    return None
