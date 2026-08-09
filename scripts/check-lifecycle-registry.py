#!/usr/bin/env python3
"""Validate an organization lifecycle registry and retirement code guard.

This file is the canonical source for generated copies in governance repos.
Use scripts/sync-lifecycle-registry-checker.sh to update or verify a copy.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the runtime, not unit tests
    yaml = None

if yaml is not None:

    class UniqueKeyLoader(yaml.SafeLoader):
        """Safe YAML loader that treats duplicate mapping keys as an error."""

    def construct_unique_mapping(
        loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
    )
else:
    UniqueKeyLoader = None


LIFECYCLES = {
    "production",
    "maintained-library",
    "research",
    "data-artifact",
    "migrating",
    "retirement-candidate",
    "archived",
}
ACTIVE_LIFECYCLES = LIFECYCLES - {"retirement-candidate", "archived"}
RESTRICTED_LIFECYCLES = {"retirement-candidate", "archived"}
ENTRY_FIELDS = {
    "repository",
    "lifecycle",
    "owner",
    "backup_owner",
    "product_or_contract",
    "real_consumers",
    "release_or_deployment_mechanism",
    "persisted_data_or_schema_owner",
    "critical_dependencies",
    "last_validated",
    "retirement_condition_or_successor",
    "issues",
}
ISSUE_FIELDS = {"cleanup", "release", "archive"}
PLACEHOLDER = re.compile(
    r"^(?:unknown|todo|tbd|n/?a|none|null|unassigned)(?:\b|\s*[-:—])",
    re.IGNORECASE,
)
VAGUE_RETIREMENT = re.compile(
    r"^(?:not scheduled|no (?:date|deadline|plan)|indefinite|later|someday)$",
    re.IGNORECASE,
)
REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class Problem:
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate lifecycle registry policy and optional repository changes."
    )
    parser.add_argument("registry", type=Path, help="registry YAML or JSON file")
    parser.add_argument(
        "--repository",
        help="short name or owner/name to require in the registry and code-guard",
    )
    parser.add_argument(
        "--base-ref",
        help="git base revision used to find added files and the previous lifecycle",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        metavar="PATH",
        help="added path to evaluate (repeatable; useful outside a git checkout)",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        help="GitHub repository inventory (JSON array or one short name per line)",
    )
    parser.add_argument(
        "--inventory-scope",
        choices=("exact", "discovered"),
        default="exact",
        help="require an exact set, or only require every visible/discovered repo",
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", dest="output_format"
    )
    return parser.parse_args()


def load_document(path: Path, content: str | None = None) -> tuple[Any, list[Problem]]:
    try:
        text = path.read_text(encoding="utf-8") if content is None else content
    except OSError as exc:
        return None, [Problem(str(path), f"cannot read registry: {exc}")]

    try:
        if path.suffix.lower() == ".json":
            return json.loads(text), []
        if yaml is None:
            return None, [
                Problem(
                    str(path),
                    "YAML input requires PyYAML (install scripts/requirements-registry.txt)",
                )
            ]
        return yaml.load(text, Loader=UniqueKeyLoader), []
    except Exception as exc:
        return None, [Problem(str(path), f"cannot parse registry: {exc}")]


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def concrete_string(value: Any) -> bool:
    return nonempty_string(value) and PLACEHOLDER.match(value.strip()) is None


def valid_date(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_registry(document: Any) -> tuple[list[Problem], dict[str, dict[str, Any]]]:
    problems: list[Problem] = []
    entries_by_name: dict[str, dict[str, Any]] = {}
    if not isinstance(document, dict):
        return [Problem("$", "top level must be a mapping")], entries_by_name

    if document.get("schema_version") != 1:
        problems.append(Problem("schema_version", "must equal 1"))
    if not valid_date(document.get("last_inventory_sync")):
        problems.append(
            Problem("last_inventory_sync", "must be an ISO date (YYYY-MM-DD)")
        )
    if not nonempty_string(document.get("source_organization")):
        problems.append(Problem("source_organization", "must be a non-empty string"))
    unknown_policy = document.get("unknown_policy")
    if not (
        nonempty_string(unknown_policy)
        or isinstance(unknown_policy, dict)
        and bool(unknown_policy)
    ):
        problems.append(
            Problem("unknown_policy", "must be a non-empty string or mapping")
        )

    entries = document.get("repositories")
    if not isinstance(entries, list):
        problems.append(Problem("repositories", "must be a list"))
        return problems, entries_by_name

    for index, entry in enumerate(entries):
        prefix = f"repositories[{index}]"
        if not isinstance(entry, dict):
            problems.append(Problem(prefix, "must be a mapping"))
            continue

        missing = sorted(ENTRY_FIELDS - entry.keys())
        for field in missing:
            problems.append(Problem(f"{prefix}.{field}", "field is required"))

        name = entry.get("repository")
        if not nonempty_string(name) or REPOSITORY_NAME.fullmatch(name) is None:
            problems.append(
                Problem(f"{prefix}.repository", "must be a short repository name")
            )
        elif name in entries_by_name:
            problems.append(
                Problem(f"{prefix}.repository", f"duplicate repository {name!r}")
            )
        else:
            entries_by_name[name] = entry

        lifecycle = entry.get("lifecycle")
        if lifecycle not in LIFECYCLES:
            allowed = ", ".join(sorted(LIFECYCLES))
            problems.append(
                Problem(f"{prefix}.lifecycle", f"must be one of: {allowed}")
            )

        if lifecycle in ACTIVE_LIFECYCLES and not concrete_string(entry.get("owner")):
            problems.append(
                Problem(
                    f"{prefix}.owner",
                    "active repository must have a concrete owner, not a placeholder",
                )
            )
        elif lifecycle in RESTRICTED_LIFECYCLES and not nonempty_string(
            entry.get("owner")
        ):
            problems.append(
                Problem(f"{prefix}.owner", "retirement repository must have an owner")
            )

        for field in (
            "backup_owner",
            "product_or_contract",
            "release_or_deployment_mechanism",
            "persisted_data_or_schema_owner",
            "retirement_condition_or_successor",
        ):
            if field in entry and not nonempty_string(entry[field]):
                problems.append(
                    Problem(f"{prefix}.{field}", "must be a non-empty string")
                )

        for field in ("real_consumers", "critical_dependencies"):
            value = entry.get(field)
            if field in entry and not (
                isinstance(value, list) and all(nonempty_string(item) for item in value)
            ):
                problems.append(
                    Problem(f"{prefix}.{field}", "must be a list of non-empty strings")
                )

        if "last_validated" in entry and not valid_date(entry.get("last_validated")):
            problems.append(
                Problem(f"{prefix}.last_validated", "must be an ISO date (YYYY-MM-DD)")
            )

        retirement = entry.get("retirement_condition_or_successor")
        if lifecycle == "retirement-candidate" and (
            not concrete_string(retirement)
            or VAGUE_RETIREMENT.fullmatch(retirement.strip()) is not None
        ):
            problems.append(
                Problem(
                    f"{prefix}.retirement_condition_or_successor",
                    "retirement candidate must name a concrete deadline, condition, or successor",
                )
            )

        issues = entry.get("issues")
        if "issues" in entry:
            if not isinstance(issues, dict):
                problems.append(Problem(f"{prefix}.issues", "must be a mapping"))
            else:
                for field in sorted(ISSUE_FIELDS):
                    value = issues.get(field)
                    if not (
                        isinstance(value, list)
                        and all(nonempty_string(item) for item in value)
                    ):
                        problems.append(
                            Problem(
                                f"{prefix}.issues.{field}",
                                "must be a list of non-empty strings",
                            )
                        )

    return problems, entries_by_name


def load_inventory(path: Path) -> tuple[set[str], list[Problem]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return set(), [Problem(str(path), f"cannot read inventory: {exc}")]
    try:
        if path.suffix.lower() == ".json":
            raw = json.loads(text)
            if not isinstance(raw, list):
                raise ValueError("JSON top level must be a list")
            values = [
                item.get("name") if isinstance(item, dict) else item for item in raw
            ]
        else:
            values = [line.strip() for line in text.splitlines() if line.strip()]
    except (json.JSONDecodeError, ValueError) as exc:
        return set(), [Problem(str(path), f"cannot parse inventory: {exc}")]

    problems: list[Problem] = []
    names: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or REPOSITORY_NAME.fullmatch(value) is None:
            problems.append(
                Problem(f"inventory[{index}]", "must be a short repository name")
            )
        elif value in names:
            problems.append(
                Problem(f"inventory[{index}]", f"duplicate repository {value!r}")
            )
        else:
            names.add(value)
    return names, problems


def validate_inventory(
    inventory: set[str], entries: dict[str, dict[str, Any]], scope: str
) -> list[Problem]:
    problems = [
        Problem(
            "repositories", f"GitHub repository {name!r} is missing from the registry"
        )
        for name in sorted(inventory - entries.keys())
    ]
    if scope == "exact":
        problems.extend(
            Problem(
                "repositories", f"registry repository {name!r} is absent from inventory"
            )
            for name in sorted(entries.keys() - inventory)
        )
    return problems


def short_repository(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def git_output(arguments: list[str]) -> tuple[str | None, Problem | None]:
    process = subprocess.run(
        ["git", *arguments], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if process.returncode:
        detail = process.stderr.strip() or "git command failed"
        return None, Problem("git", detail)
    return process.stdout, None


def previous_lifecycle(base_ref: str, registry: Path, repository: str) -> str | None:
    root_text, error = git_output(["rev-parse", "--show-toplevel"])
    if error or root_text is None:
        return None
    root = Path(root_text.strip()).resolve()
    try:
        relative = registry.resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    content, error = git_output(["show", f"{base_ref}:{relative}"])
    if error or content is None:
        return None
    document, parse_problems = load_document(registry, content)
    if parse_problems or not isinstance(document, dict):
        return None
    entries = document.get("repositories")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("repository") == repository:
            lifecycle = entry.get("lifecycle")
            return lifecycle if isinstance(lifecycle, str) else None
    return None


def added_paths(base_ref: str) -> tuple[list[str], Problem | None]:
    output, error = git_output(
        [
            "diff",
            "--name-only",
            "--diff-filter=ACR",
            "--find-renames",
            f"{base_ref}...HEAD",
        ]
    )
    if error or output is None:
        return [], error
    return [line for line in output.splitlines() if line], None


def is_governance_path(value: str) -> bool:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    if path.as_posix() == ".immutable-dependencies/manifest.json":
        return True
    if path.parts and path.parts[0] in {".github", "docs", "lifecycle"}:
        return True
    if len(path.parts) != 1:
        return False
    name = path.name
    if name in {
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "CODEOWNERS",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "SUPPORT.md",
    }:
        return True
    upper = name.upper()
    return upper.startswith("README") or upper.startswith("LICENSE")


def validate_repository_guard(
    repository_arg: str,
    entries: dict[str, dict[str, Any]],
    registry: Path,
    base_ref: str | None,
    explicit_paths: list[str],
) -> list[Problem]:
    problems: list[Problem] = []
    repository = short_repository(repository_arg)
    entry = entries.get(repository)
    if entry is None:
        return [Problem("repository", f"{repository!r} is not present in the registry")]

    lifecycles = {entry.get("lifecycle")}
    if base_ref:
        old_lifecycle = previous_lifecycle(base_ref, registry, repository)
        if old_lifecycle:
            lifecycles.add(old_lifecycle)

    paths = list(explicit_paths)
    if base_ref:
        discovered, error = added_paths(base_ref)
        if error:
            problems.append(error)
        paths.extend(discovered)

    if lifecycles.isdisjoint(RESTRICTED_LIFECYCLES):
        return problems

    for path in sorted(set(paths)):
        if not is_governance_path(path):
            lifecycle_text = "/".join(sorted(str(item) for item in lifecycles if item))
            problems.append(
                Problem(
                    path,
                    f"{repository} ({lifecycle_text}) cannot silently add product code; "
                    "reactivate it through a separately reviewed lifecycle change first",
                )
            )
    return problems


def emit(problems: list[Problem], output_format: str) -> None:
    if output_format == "json":
        print(
            json.dumps(
                {
                    "ok": not problems,
                    "problems": [
                        {"path": problem.path, "message": problem.message}
                        for problem in problems
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if not problems:
        print("lifecycle registry hygiene: ok")
        return
    for problem in problems:
        print(f"ERROR {problem.path}: {problem.message}", file=sys.stderr)
    print(f"lifecycle registry hygiene: {len(problems)} problem(s)", file=sys.stderr)


def main() -> int:
    args = parse_args()
    document, problems = load_document(args.registry)
    entries: dict[str, dict[str, Any]] = {}
    if not problems:
        validation_problems, entries = validate_registry(document)
        problems.extend(validation_problems)
    if args.inventory:
        inventory, inventory_problems = load_inventory(args.inventory)
        problems.extend(inventory_problems)
        if not inventory_problems:
            problems.extend(
                validate_inventory(inventory, entries, args.inventory_scope)
            )
    if args.repository and not any(
        problem.path == "repositories" for problem in problems
    ):
        problems.extend(
            validate_repository_guard(
                args.repository,
                entries,
                args.registry,
                args.base_ref,
                args.changed_path,
            )
        )
    emit(problems, args.output_format)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
