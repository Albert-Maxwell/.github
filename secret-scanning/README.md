# Public secret-scanning provider

This public repository provides the Albert-Maxwell reusable Gitleaks workflow
and pre-commit hook. The policy and local runner here are generated,
byte-identical copies of the canonical files in `easy-ci`; do not edit them in
this repository.

## GitHub Actions

Add a small caller workflow to each product repository and replace the example
revision with the full merge commit of this provider:

```yaml
name: Secret scan

on:
  pull_request:
  push:
    branches: [main] # use master where it is the actual default
  workflow_dispatch:

permissions:
  contents: read

jobs:
  secret-scan:
    uses: Albert-Maxwell/.github/.github/workflows/secret-scan.yml@<provider-full-commit-sha>
```

Pull-request and default-branch events scan only introduced commits. Manual
dispatch scans all reachable history. The provider pins the checkout Action to
a full SHA and installs Gitleaks 8.30.1 only after verifying the Linux x64 or
arm64 release archive against a hard-coded SHA-256. It forces redaction, creates
no findings report, and grants only `contents: read`.

The workflow accepts no secrets and does not execute repository code, so the
ordinary `pull_request` trigger also supports contributions from forks. Do not
change callers to `pull_request_target`.

## Pre-commit

Install checksum-verified Gitleaks 8.30.1, then add the stanza in
[`pre-commit.example.yaml`](pre-commit.example.yaml) to the consuming
repository's `.pre-commit-config.yaml`. Pin `rev` to this provider's full merge
commit, never `main` or a moving tag. The provider hook calls
`run-gitleaks.sh staged`, which requires the exact CLI version and always
redacts output.

## Findings

A manual history scan is read-only. If a scan fails, preserve only redacted
rule/path/commit metadata and rotate or revoke the credential before cleanup.
Never paste a secret into an issue or job log. Never rewrite history until the
credential owner approves the evidence-preservation and force-push plan.

See the canonical policy, audit matrix, rollout contract, and incident process
in [`easy-ci/docs/SECRET-SCANNING.md`](https://github.com/Albert-Maxwell/easy-ci/blob/main/docs/SECRET-SCANNING.md).
