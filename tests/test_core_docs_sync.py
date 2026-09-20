"""Guards against drift between the canonical contract and every doc that repeats it."""

import re
from pathlib import Path

import pytest

from contract.evguard_contract import (
    CONTRACT_VERSION,
    RATE_MAX_COMMANDS,
    RATE_WINDOW_SECONDS,
)

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "contract" / "evguard_contract.py"
MIRRORS = [ROOT / "contract" / "CONTRACT.md", ROOT / "docs" / "specs" / "EVGuard_CONTRACT.md"]
RATE_DOCS = MIRRORS + [
    ROOT / "docs" / "specs" / "EVGuard_FINAL_README.md",
    ROOT / "docs" / "specs" / "EVGuard_ROLE_1.md",
    ROOT / "README.md",
]

N = RATE_MAX_COMMANDS
# (regex, expected value for each capture group). Every match in every doc must agree.
RATE_PATTERNS = [
    (r"RATE_MAX_COMMANDS = (\d+)", [N]),
    (r"RATE_WINDOW_SECONDS = (\d+)", [RATE_WINDOW_SECONDS]),
    (r"max_commands_per_source: (\d+)", [N]),
    (r"window_seconds: (\d+)", [RATE_WINDOW_SECONDS]),
    (r"max (\d+) commands per source\+session per (\d+) s", [N, RATE_WINDOW_SECONDS]),
    (r"\(limit (\d+)\)", [N]),
    (r"(\d+) commands in \d+ s from one source", [N + 5]),
    (r"(\d+)(?:st|th) onward BLOCK", [N + 1]),
    (r"First (\d+) commands ALLOW", [N]),
    (r"3 setup commands \+ (\d+) × SET_POWER", [N + 2]),
    (r"steps 1[–-](\d+) ALLOW", [N]),
    (r"(?:steps )?(\d+)[–-](\d+) BLOCK", [N + 1, N + 5]),
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def python_block(markdown: str) -> str:
    start = markdown.index("```python\n") + len("```python\n")
    return markdown[start:markdown.index("\n```", start) + 1]


def test_markdown_mirrors_are_byte_identical():
    assert MIRRORS[0].read_bytes() == MIRRORS[1].read_bytes()


@pytest.mark.parametrize("mirror", MIRRORS, ids=lambda p: p.name)
def test_mirror_python_block_matches_canonical_file(mirror):
    assert python_block(text(mirror)) == text(CANONICAL)


@pytest.mark.parametrize("mirror", MIRRORS, ids=lambda p: p.name)
def test_mirror_version_matches_canonical(mirror):
    body = text(mirror)
    assert body.startswith(f"# EVGuard Shared Contract — v{CONTRACT_VERSION}\n")
    assert f'"contract_version": "{CONTRACT_VERSION}"' in body


@pytest.mark.parametrize("doc", RATE_DOCS, ids=lambda p: p.name)
def test_rate_limit_values_in_docs_match_contract(doc):
    body = text(doc)
    for pattern, expected in RATE_PATTERNS:
        for match in re.finditer(pattern, body):
            found = [int(g) for g in match.groups()]
            assert found == expected, (
                f"{doc.name}: '{match.group(0)}' says {found}, contract says {expected}")


@pytest.mark.parametrize("doc", MIRRORS + [ROOT / "docs" / "specs" / "EVGuard_FINAL_README.md"],
                         ids=lambda p: p.name)
def test_rate_scan_is_not_vacuous(doc):
    body = text(doc)
    assert any(re.search(pattern, body) for pattern, _ in RATE_PATTERNS), \
        f"no rate-limit mention found in {doc.name}; update RATE_PATTERNS"
