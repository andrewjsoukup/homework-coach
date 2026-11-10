"""Catalog rules 11/17 + privacy: no binaries, bytecode, credential reads, or real family data."""
import re

from .conftest import ROOT

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
# Local run outputs; gitignored (see .gitignore), never published.
SKIP_PREFIXES = {("demo", "out"), ("packets",), ("out",)}
BINARY_MAGIC = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\x00asm")
# Generic guard words only — real names are never written into the repo, even here.
CREDENTIAL_PATTERNS = [r"auth\.json", r"\.env\b", r"os\.environ\["]


def _files():
    for p in ROOT.rglob("*"):
        parts = p.relative_to(ROOT).parts
        if any(parts[:len(x)] == x for x in SKIP_PREFIXES):
            continue
        if p.is_file() and not (set(parts) & SKIP_DIRS):
            yield p


def test_no_bytecode_or_binaries():
    for p in _files():
        assert p.suffix not in (".pyc", ".pyo", ".so", ".dll", ".exe", ".dylib"), p
        assert not p.read_bytes()[:4].startswith(BINARY_MAGIC), p


def test_no_credential_reads_in_code():
    for p in _files():
        if p.suffix == ".py" and "tests" not in p.parts:
            text = p.read_text(encoding="utf-8")
            for pat in CREDENTIAL_PATTERNS:
                assert not re.search(pat, text), (p, pat)


def test_no_absolute_user_paths():
    for p in _files():
        if p.suffix in (".py", ".md", ".yaml", ".json", ".toml", ".js"):
            assert not re.search(r"[A-Za-z]:[\\/]+Users[\\/]", p.read_text(encoding="utf-8")), p
