# Public repository-hygiene provider

This public repository provides the Albert-Maxwell reusable generated-artifact
gate. The checker and workflow here are generated, byte-identical copies of the
canonical files in `easy-ci`; do not edit them in this repository.

## Caller

After this provider is merged, add a small workflow to a canary repository and
replace the example revision with the provider's full merge commit SHA:

```yaml
name: Repository hygiene

on:
  pull_request:
  push:
    branches: [main] # use master where it is the actual default
  workflow_dispatch:

permissions:
  contents: read

jobs:
  repository-hygiene:
    uses: Albert-Maxwell/.github/.github/workflows/repository-hygiene.yml@<provider-full-commit-sha>
```

The provider rejects tracked Python bytecode/cache, Cargo/build/distribution
output, coverage output, local databases/WALs, and generated/output/artifact
directories. It accepts no secrets and does not execute consumer code, so the
ordinary `pull_request` event supports contributions from forks. Never use
`pull_request_target`.

Deletion is the default. A genuinely immutable generated contract may be
allowed only through a tracked
`.repository-hygiene/sealed-artifacts.json` manifest that names each exact
path, SHA-256 digest, owner, and contract. Invalid, duplicate, stale,
non-canonical, traversal, symlink, untracked, or digest-mismatched entries fail
closed.

See the canonical policy, local command, manifest schema, and synchronization
contract in
[`easy-ci/docs/REPOSITORY-HYGIENE.md`](https://github.com/Albert-Maxwell/easy-ci/blob/main/docs/REPOSITORY-HYGIENE.md).
