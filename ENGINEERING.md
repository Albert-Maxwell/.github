# Engineering Contract

This is the canonical organization-wide engineering contract. Read it before every change. Repository-local instructions may add commands, domain constitutions, ownership, and safety exceptions; they must link here rather than copy these rules. Mechanically synchronized, byte-identical generated copies are the only exception. The owning repository's documented contracts remain authoritative when they are more specific.

## Make the current system smaller and clearer

1. Implement the simplest design that fully satisfies current requirements. Do not add speculative abstraction, configuration, or indirection.
2. Grow the product in working, end-to-end layers. Each change must leave a usable, verifiable system; unfinished complexity must not replace a working path.
3. Keep concerns modular and ownership explicit. Every behavior, persisted format, and interface has one named owner.
4. Delete obsolete paths. Backward-compatibility shims, aliases, fallbacks, dual dispatch, and historical-name probing are forbidden by default.
5. Reuse before copying. When repeated code is the same stable behavior, put it in its existing owner or in a versioned library with real consumers, migrate all consumers, and delete every duplicate. Do not extract a library for one consumer or merely similar code.
6. Prefer maintained libraries and dependencies already used by the project. Verify their current documentation, types, maintenance, and license before reimplementing behavior or adding a package.

## Protect contracts and data

Persisted formats and cross-repository interfaces are the compatibility exception. WALs, schemas, sealed artifacts, replay corpora, and imported APIs change only through their owner's versioned migration and deprecation process. Never silently reinterpret old data.

For a breaking cross-repository change, record owners and consumers, land and release the owning contract first, migrate and verify consumers in dependency order, and only then remove the old contract. Any temporary compatibility path must name its owner, tracking issue, and exact retirement condition.

Never delete, overwrite, normalize, or rewrite existing data unless the request explicitly authorizes it. Table and object retirement must use the owning numbered migration and retention workflow, with rollback or recovery evidence. Repository-specific rules for determinism, storage ownership, constitutions, and evidence override general cleanup preferences.

## Keep branches and CI deliberate

Start each topic on a fresh branch from the current remote default branch. One branch owns one topic: never stack unrelated work on it or reuse it after merge. Use an isolated worktree for long-running or parallel work so other checkouts and user changes remain untouched.

Run the repository's exact local gates before pushing. Treat shared or paid CI, including CodeBuild, as verification rather than an interactive compile or lint loop. Batch changes into meaningful commits and target a few deliberate CI runs per pull request, normally one per substantive review round.

## Own the whole lifecycle

Long-term architectural decisions are expected. An interim state is acceptable only when its owner, tracking issue, rollout, verification, and exact retirement condition are documented.

A repository is active only while it has a current owner, a supported product/library/data contract, a real consumer, and a working release or deployment path. A shared library requires immutable, versioned releases; a sibling checkout or mutable branch install is not a release mechanism. Otherwise follow [RETIREMENT.md](RETIREMENT.md): preserve data and evidence, prove no live dependency remains, and archive it. New repositories must satisfy [REPOSITORY_CREATION.md](REPOSITORY_CREATION.md) and be recorded in [`lifecycle/repositories.yaml`](lifecycle/repositories.yaml).

Review this contract periodically by changing this file. Do not maintain hand-copied organization policy in repository-local agent instructions.
