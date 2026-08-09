#!/usr/bin/env python3
"""Reject mutable dependencies in an exact, digest-bound manifest scope."""

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

MANIFEST_PATH = ".immutable-dependencies/manifest.json"
SCHEMA_VERSION = 1
POLICY_VERSION = 1
TARGET_KEYS = {"path", "environment", "sha256"}
EXCLUSION_KEYS = {"path", "environment", "sha256", "owner", "reason"}
TARGET_ENVIRONMENTS = {"production", "release"}
EXCLUSION_ENVIRONMENTS = {"development", "test"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
EDITABLE = re.compile(r"(?:^|\s)(?:-e|--editable)(?:\s|=|$)")
PRIVATE_PACKAGES = {
    "easy-ci",
    "easy-engine",
    "easy-etl",
    "easy-observability",
    "easy-portal",
    "easy-quant",
    "easy-storage",
    "easy-tg",
    "news-agent",
    "news-agent-core",
    "news-agent-storage",
    "news-core",
    "news-storage",
}
DEPENDENCY_BASENAMES = {
    "cargo.lock",
    "cargo.toml",
    "go.mod",
    "go.sum",
    "package-lock.json",
    "package.json",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "pyproject.toml",
    "uv.lock",
}
DEPLOYMENT_DIRECTORIES = {
    "deploy",
    "deployment",
    "docker",
    "infra",
    "ops",
    "systemd",
}


class ContractError(ValueError):
    """The manifest or repository violates the immutable-dependency contract."""


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
            raise ContractError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def tracked_paths(root: Path) -> list[str]:
    process = subprocess.run(
        ["git", "-C", os.fspath(root), "ls-files", "-z", "--cached"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(f"cannot list tracked files: {detail}")
    try:
        return [raw.decode("utf-8") for raw in process.stdout.split(b"\0") if raw]
    except UnicodeDecodeError as error:
        raise ContractError("tracked paths must be valid UTF-8") from error


def normalized_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a non-empty string")
    if (
        "\\" in value
        or value.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ContractError(f"{label} is not a safe repository path: {value!r}")
    candidate = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ContractError(f"{label} is not normalized: {value!r}")
    if candidate.as_posix() != value:
        raise ContractError(f"{label} is not normalized: {value!r}")
    if value == MANIFEST_PATH:
        raise ContractError("the immutable-dependency manifest cannot scan itself")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_candidate(path: str) -> bool:
    candidate = PurePosixPath(path)
    parts = candidate.parts
    lower = path.lower()
    name = candidate.name.lower()
    suffix = candidate.suffix.lower()
    if len(parts) >= 3 and parts[:2] == (".github", "workflows"):
        return suffix in {".yml", ".yaml"}
    if name in DEPENDENCY_BASENAMES:
        return True
    if name.startswith("requirements") and suffix in {".in", ".txt"}:
        return True
    if name == "dockerfile" or name.startswith("dockerfile."):
        return True
    if len(parts) == 1 and (
        re.fullmatch(r"(?:docker-)?compose(?:\.[a-z0-9_-]+)?\.ya?ml", lower) is not None
    ):
        return True
    if suffix == ".service":
        return True
    if any(part.lower() in DEPLOYMENT_DIRECTORIES for part in parts[:-1]):
        return suffix in {
            "",
            ".conf",
            ".hcl",
            ".json",
            ".service",
            ".sh",
            ".tf",
            ".tfvars",
            ".toml",
            ".yml",
            ".yaml",
        }
    if "scripts/slurm" in lower and suffix == ".sh":
        return True
    return False


def checked_regular_file(root: Path, path: str, tracked: set[str]) -> Path:
    if path not in tracked:
        raise ContractError(f"manifest path is not tracked: {path!r}")
    target = root / path
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError as error:
        raise ContractError(
            f"manifest path is missing from the worktree: {path!r}"
        ) from error
    if not stat.S_ISREG(mode):
        raise ContractError(f"manifest path must be a regular file: {path!r}")
    return target


def load_manifest(root: Path, tracked: set[str]) -> tuple[list[str], list[str]]:
    if MANIFEST_PATH not in tracked:
        raise ContractError(f"required manifest is not tracked: {MANIFEST_PATH}")
    manifest = checked_regular_file(root, MANIFEST_PATH, tracked)
    try:
        document = json.loads(
            manifest.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot parse {MANIFEST_PATH}: {error}") from error
    if not isinstance(document, dict):
        raise ContractError("manifest root must be a JSON object")
    required = {"schema_version", "policy_version", "targets", "exclusions"}
    if set(document) != required:
        missing = sorted(required - set(document))
        unknown = sorted(set(document) - required)
        raise ContractError(
            f"manifest keys invalid; missing={missing!r}, unknown={unknown!r}"
        )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != SCHEMA_VERSION
    ):
        raise ContractError(f"schema_version must be the integer {SCHEMA_VERSION}")
    if (
        type(document["policy_version"]) is not int
        or document["policy_version"] != POLICY_VERSION
    ):
        raise ContractError(f"policy_version must be the integer {POLICY_VERSION}")
    if not isinstance(document["targets"], list) or not document["targets"]:
        raise ContractError("targets must be a non-empty JSON array")
    if not isinstance(document["exclusions"], list):
        raise ContractError("exclusions must be a JSON array")

    seen: set[str] = set()
    targets: list[str] = []
    exclusions: list[str] = []
    for collection, keys, environments, destination in (
        (document["targets"], TARGET_KEYS, TARGET_ENVIRONMENTS, targets),
        (document["exclusions"], EXCLUSION_KEYS, EXCLUSION_ENVIRONMENTS, exclusions),
    ):
        label_root = "targets" if destination is targets else "exclusions"
        for index, entry in enumerate(collection):
            label = f"{label_root}[{index}]"
            if not isinstance(entry, dict) or set(entry) != keys:
                raise ContractError(f"{label} keys must be exactly {sorted(keys)!r}")
            path = normalized_path(entry["path"], f"{label}.path")
            if path in seen:
                raise ContractError(f"duplicate manifest path: {path!r}")
            seen.add(path)
            environment = entry["environment"]
            if environment not in environments:
                raise ContractError(
                    f"{label}.environment must be one of {sorted(environments)!r}"
                )
            digest = entry["sha256"]
            if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
                raise ContractError(
                    f"{label}.sha256 must be 64 lowercase hex characters"
                )
            if destination is exclusions:
                for field in ("owner", "reason"):
                    value = entry[field]
                    if not isinstance(value, str) or not value.strip():
                        raise ContractError(
                            f"{label}.{field} must be a non-empty string"
                        )
            target = checked_regular_file(root, path, tracked)
            if sha256_file(target) != digest:
                raise ContractError(f"manifest digest mismatch: {path!r}")
            destination.append(path)

    discovered = {path for path in tracked if is_candidate(path)}
    declared = set(targets) | set(exclusions)
    missing = sorted(discovered - declared)
    stale = sorted(declared - discovered)
    if missing or stale:
        raise ContractError(
            f"manifest scope mismatch; unclassified={missing!r}, non-candidates={stale!r}"
        )
    return targets, exclusions


def checkout_blocks(text: str) -> list[tuple[str | None, str | None]]:
    lines = text.splitlines()
    blocks: list[tuple[str | None, str | None]] = []
    for index, line in enumerate(lines):
        match = re.match(
            r"^(\s*)-?\s*uses:\s*actions/checkout@[0-9a-f]{40}(?:\s|#|$)", line
        )
        if match is None:
            continue
        indent = len(match.group(1))
        repository: str | None = None
        ref: str | None = None
        for following in lines[index + 1 :]:
            following_indent = len(following) - len(following.lstrip())
            if (
                re.match(r"^\s*-\s+(?:name|uses):", following)
                and following_indent <= indent
            ):
                break
            item = re.match(r"^\s*(repository|ref):\s*([^#]+?)\s*$", following)
            if item:
                if item.group(1) == "repository":
                    repository = item.group(2).strip(" '\"")
                else:
                    ref = item.group(2).strip(" '\"")
        blocks.append((repository, ref))
    return blocks


def requirement_fragments(text: str, path: str) -> list[str]:
    fragments: list[str] = []
    name = PurePosixPath(path).name.lower()
    if name.startswith("requirements") or name in {
        "pipfile",
        "pipfile.lock",
        "poetry.lock",
        "uv.lock",
    }:
        fragments.extend(text.splitlines())
    elif name == "pyproject.toml":
        section = ""
        in_array = False
        for line in text.splitlines():
            section_match = re.match(r"^\s*\[([^]]+)]\s*$", line)
            if section_match:
                section = section_match.group(1).lower()
                in_array = False
                continue
            dependency_table = section in {
                "project.optional-dependencies",
                "dependency-groups",
                "tool.poetry.dependencies",
                "tool.poetry.group.dev.dependencies",
            }
            starts_array = re.match(r"^\s*([a-z0-9_-]+)\s*=\s*\[", line, re.IGNORECASE)
            if starts_array and (
                (
                    section == "project"
                    and starts_array.group(1).lower() == "dependencies"
                )
                or dependency_table
            ):
                in_array = True
            if dependency_table and line.strip() and not line.lstrip().startswith("#"):
                fragments.append(line)
            elif in_array:
                fragments.append(line)
            if in_array:
                if "]" in line:
                    in_array = False
    for line in text.splitlines():
        if re.search(r"\b(?:python\d*(?:\.\d+)?\s+-m\s+)?pip\s+install\b", line):
            fragments.append(line)
    return fragments


def scan_target(path: str, text: str) -> list[str]:
    findings: list[str] = []
    for reference in USES.findall(text):
        if reference.startswith("./"):
            continue
        if (
            "@" not in reference
            or COMMIT.fullmatch(reference.rsplit("@", 1)[1]) is None
        ):
            findings.append(
                "third-party action or reusable workflow is not pinned to a full commit SHA"
            )
            break

    for repository, ref in checkout_blocks(text):
        if repository is None:
            continue
        if (
            repository == "${{ job.workflow_repository }}"
            and ref == "${{ job.workflow_sha }}"
        ):
            continue
        if ref is None or COMMIT.fullmatch(ref) is None:
            findings.append(
                "external repository checkout is missing an immutable full-SHA ref"
            )
            break

    for fragment in requirement_fragments(text, path):
        stripped = fragment.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if EDITABLE.search(stripped):
            findings.append(
                "editable install is forbidden in production/release manifests"
            )
            break

    if re.search(r"\bPYTHONPATH\s*=.*(?:\.\.|/|\$\{?GITHUB_WORKSPACE\}?/)", text):
        findings.append("sibling or absolute PYTHONPATH dependency is forbidden")

    if re.search(r"\b(?:git\s+clone|gh\s+repo\s+clone)\b", text):
        findings.append(
            "git clone is unresolved; use a digest-bound artifact or exact source revision"
        )
    if re.search(
        r"\bgit\s+(?:checkout|switch|fetch)\b[^\n]*(?:\bmain\b|\bmaster\b)", text
    ):
        findings.append("mutable Git branch is forbidden")
    if re.search(r"\bgit\s+pull\b", text) or re.search(
        r"\bgit\s+merge\b[^\n]*(?:@\{u\}|origin/(?:main|master)\b)", text
    ):
        findings.append("mutable Git tracking branch is forbidden")
    if re.search(
        r"github\.com/[^\s'\"]+/(?:archive/(?:refs/heads/)?|tarball/)(?:main|master)(?:[./'\"]|$)",
        text,
        re.IGNORECASE,
    ):
        findings.append("GitHub source archive uses a mutable main/master ref")

    for url in re.findall(r"git\+https?://[^\s'\"\]]+", text):
        revision = url.rsplit("@", 1)[1] if "@" in url else ""
        revision = revision.split("#", 1)[0]
        cargo_revision = re.search(r"[?&]rev=([0-9a-f]{40})(?:[#&]|$)", url)
        locked_revision = re.search(r"#([0-9a-f]{40})(?:\Z|[^0-9a-f])", url)
        if (
            COMMIT.fullmatch(revision) is None
            and cargo_revision is None
            and locked_revision is None
        ):
            findings.append("VCS dependency is not pinned to a full commit SHA")
            break

    cargo_lines = text.splitlines()
    for index, line in enumerate(cargo_lines):
        if re.search(r"\bgit\s*=\s*['\"]", line) is None:
            continue
        window = "\n".join(cargo_lines[index : index + 8])
        section_break = re.search(r"\n\s*\[", window)
        if section_break:
            window = window[: section_break.start()]
        revision = re.search(r"\brev\s*=\s*['\"]([0-9a-f]+)['\"]", window)
        if revision is None or COMMIT.fullmatch(revision.group(1)) is None:
            findings.append(
                "Cargo Git dependency is not pinned with rev = full commit SHA"
            )
            break
        if re.search(r"\b(?:branch|tag)\s*=", window):
            findings.append("Cargo Git dependency uses a mutable branch or tag")
            break

    for fragment in requirement_fragments(text, path):
        normalized = fragment.lower().replace("_", "-")
        for package in sorted(PRIVATE_PACKAGES):
            if (
                re.search(
                    rf"(?<![a-z0-9.-]){re.escape(package)}(?![a-z0-9.-])", normalized
                )
                is None
            ):
                continue
            exact_vcs = re.search(
                rf"{re.escape(package)}\s*@\s*git\+https://github\.com/albert-maxwell/[^\s@]+@([0-9a-f]{{40}})(?:[#\s'\"]|$)",
                normalized,
            )
            if exact_vcs is None:
                findings.append(
                    f"private package {package!r} has no exact Git source revision"
                )

    return list(dict.fromkeys(findings))


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
            raise ContractError("--repository must name a Git worktree root")
        if Path(top_level.stdout.strip()).resolve() != root:
            raise ContractError(
                "--repository must name the Git worktree root, not a subdirectory"
            )
        tracked = set(tracked_paths(root))
        targets, exclusions = load_manifest(root, tracked)
        findings: list[tuple[str, str]] = []
        for path in targets:
            try:
                text = (root / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise ContractError(
                    f"cannot read target as UTF-8 text: {path!r}: {error}"
                ) from error
            findings.extend((path, reason) for reason in scan_target(path, text))
    except ContractError as error:
        print(f"immutable dependency check failed: {error}", file=sys.stderr)
        return 1

    if findings:
        print(
            "immutable dependency check failed: mutable dependencies found",
            file=sys.stderr,
        )
        for path, reason in findings:
            print(f"  {json.dumps(path)}: {reason}", file=sys.stderr)
        return 1
    print(
        "immutable dependency check passed: "
        f"{len(targets)} production/release manifests, {len(exclusions)} explicit test/dev exclusions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
