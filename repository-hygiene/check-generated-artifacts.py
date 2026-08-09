#!/usr/bin/env python3
"""Reject tracked generated artifacts unless an exact sealed manifest permits them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_PATH = ".repository-hygiene/sealed-artifacts.json"
SCHEMA_VERSION = 1
ENTRY_KEYS = {"path", "sha256", "owner", "contract"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")

DENIED_DIRECTORIES = {
    "__pycache__": "Python bytecode cache",
    "target": "Cargo build output",
    "build": "build output",
    "dist": "distribution output",
    "coverage": "coverage output",
    "htmlcov": "coverage output",
    ".nyc_output": "coverage output",
    "generated": "generated output",
    "generated-output": "generated output",
    "generated_outputs": "generated output",
    "output": "generated output",
    "outputs": "generated output",
    "artifacts": "generated output",
}
LOCAL_DATA_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
    ".wal",
    "-shm",
    "-wal",
)


class ManifestError(ValueError):
    """The sealed-artifact manifest is unsafe or inconsistent."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        default=".",
        help="Git worktree to inspect (default: current directory)",
    )
    return parser.parse_args()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def tracked_paths(root: Path) -> list[str]:
    process = subprocess.run(
        [
            "git",
            "-C",
            os.fspath(root),
            "ls-files",
            "-z",
            "--cached",
            "--full-name",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"cannot list tracked files: {detail}")
    try:
        return [raw.decode("utf-8") for raw in process.stdout.split(b"\0") if raw]
    except UnicodeDecodeError as error:
        raise RuntimeError("tracked paths must be valid UTF-8") from error


def denied_reason(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    for component in parts[:-1]:
        if component in DENIED_DIRECTORIES:
            return DENIED_DIRECTORIES[component]

    name = parts[-1]
    lower = name.lower()
    if lower.endswith(".pyc"):
        return "Python bytecode"
    if lower == ".coverage" or lower.startswith(".coverage."):
        return "coverage output"
    if lower in {"coverage.xml", "lcov.info"}:
        return "coverage output"
    if lower.endswith(LOCAL_DATA_SUFFIXES):
        return "local database or WAL"
    return None


def normalized_manifest_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError("artifact path must be a non-empty string")
    if (
        "\\" in value
        or value.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ManifestError(f"artifact path is not a safe repository path: {value!r}")
    candidate = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ManifestError(f"artifact path is not normalized: {value!r}")
    if candidate.as_posix() != value:
        raise ManifestError(f"artifact path is not normalized: {value!r}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(root: Path, tracked: set[str]) -> dict[str, str]:
    manifest = root / MANIFEST_PATH
    present = manifest.exists() or manifest.is_symlink()
    if MANIFEST_PATH not in tracked and not present:
        return {}
    if MANIFEST_PATH not in tracked:
        raise ManifestError(f"{MANIFEST_PATH} must itself be tracked")
    if not present:
        raise ManifestError(f"{MANIFEST_PATH} is tracked but missing from the worktree")
    if manifest.is_symlink() or not manifest.is_file():
        raise ManifestError(f"{MANIFEST_PATH} must be a regular file")

    try:
        document = json.loads(
            manifest.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot parse {MANIFEST_PATH}: {error}") from error

    if not isinstance(document, dict):
        raise ManifestError("manifest root must be a JSON object")
    unknown = set(document) - {"schema_version", "artifacts"}
    missing = {"schema_version", "artifacts"} - set(document)
    if missing or unknown:
        raise ManifestError(
            f"manifest keys invalid; missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != SCHEMA_VERSION
    ):
        raise ManifestError(f"schema_version must be the integer {SCHEMA_VERSION}")
    entries = document["artifacts"]
    if not isinstance(entries, list):
        raise ManifestError("artifacts must be a JSON array")

    exemptions: dict[str, str] = {}
    for index, entry in enumerate(entries):
        label = f"artifacts[{index}]"
        if not isinstance(entry, dict):
            raise ManifestError(f"{label} must be a JSON object")
        if set(entry) != ENTRY_KEYS:
            raise ManifestError(f"{label} keys must be exactly {sorted(ENTRY_KEYS)!r}")
        path = normalized_manifest_path(entry["path"])
        if path in exemptions:
            raise ManifestError(f"duplicate artifact path: {path!r}")
        digest = entry["sha256"]
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            raise ManifestError(f"{label}.sha256 must be 64 lowercase hex characters")
        for field in ("owner", "contract"):
            value = entry[field]
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"{label}.{field} must be a non-empty string")
        if path not in tracked:
            raise ManifestError(f"sealed artifact is not tracked: {path!r}")
        reason = denied_reason(path)
        if reason is None:
            raise ManifestError(
                f"sealed artifact is not a denied generated path: {path!r}"
            )

        artifact = root / path
        try:
            mode = artifact.lstat().st_mode
        except FileNotFoundError as error:
            raise ManifestError(
                f"sealed artifact is missing from the worktree: {path!r}"
            ) from error
        if not stat.S_ISREG(mode):
            raise ManifestError(f"sealed artifact must be a regular file: {path!r}")
        actual = sha256_file(artifact)
        if actual != digest:
            raise ManifestError(f"sealed artifact digest mismatch: {path!r}")
        exemptions[path] = reason
    return exemptions


def main() -> int:
    args = parse_args()
    root = Path(args.repository).resolve()
    try:
        top_level = subprocess.run(
            ["git", "-C", os.fspath(root), "rev-parse", "--show-toplevel"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if top_level.returncode != 0:
            raise RuntimeError("--repository must name a Git worktree root")
        if Path(top_level.stdout.strip()).resolve() != root:
            raise RuntimeError(
                "--repository must name the Git worktree root, not a subdirectory"
            )
        tracked = tracked_paths(root)
        tracked_set = set(tracked)
        exemptions = load_manifest(root, tracked_set)
    except (ManifestError, RuntimeError) as error:
        print(f"repository hygiene failed: {error}", file=sys.stderr)
        return 1

    denied = [(path, reason) for path in tracked if (reason := denied_reason(path))]
    unsealed = [(path, reason) for path, reason in denied if path not in exemptions]
    if unsealed:
        print(
            "repository hygiene failed: tracked generated artifacts found",
            file=sys.stderr,
        )
        for path, reason in unsealed:
            print(f"  {json.dumps(path)}: {reason}", file=sys.stderr)
        print(
            f"remove them, or explicitly seal immutable files in {MANIFEST_PATH}",
            file=sys.stderr,
        )
        return 1

    print(
        "repository hygiene passed: "
        f"{len(tracked)} tracked paths, {len(exemptions)} sealed generated artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
