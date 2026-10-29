"""Vendor SDKs are imported by their provider implementation only (architecture rule 2, NFR-09).

Test code is exempt: it may use an SDK to arrange a fake, as the `storage`
fixture does with moto.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (REPO_ROOT / "api" / "api", REPO_ROOT / "worker" / "worker")

# Top-level package -> the one module allowed to import it.
ALLOWED = {
    "boto3": "api/api/core/storage_s3.py",
    "botocore": "api/api/core/storage_s3.py",
    "types_boto3_s3": "api/api/core/storage_s3.py",
}


def _is_test_code(path: Path) -> bool:
    return "tests" in path.parts or path.name in {"testing.py", "conftest.py"}


def _sources() -> list[Path]:
    return [
        path
        for root in SOURCE_ROOTS
        for path in sorted(root.rglob("*.py"))
        if not _is_test_code(path)
    ]


def _imported_packages(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


def test_the_scan_sees_the_storage_implementation() -> None:
    # Guards the test itself: a wrong root would make the next one pass on nothing.
    assert "boto3" in _imported_packages(REPO_ROOT / ALLOWED["boto3"])


def test_vendor_sdks_stay_in_their_implementation() -> None:
    misplaced = []
    for path in _sources():
        where = path.relative_to(REPO_ROOT).as_posix()
        for package in sorted(_imported_packages(path) & ALLOWED.keys()):
            if ALLOWED[package] != where:
                misplaced.append(f"{where} imports {package}")

    assert not misplaced
