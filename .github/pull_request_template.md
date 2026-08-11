Organization members: review the [canonical engineering policy](https://github.com/Albert-Maxwell/amt-meta/blob/main/ENGINEERING.md) before submitting. Repository-local instructions and owning contracts remain authoritative when more specific.

## Current behavior and owner

<!-- What happens today, who owns it, and what current evidence demonstrates the need? -->

## Proposed change and affected surface

<!-- Describe the smallest complete change. List affected code, data/schemas, interfaces, repositories, artifacts, deployments, and consumers. -->

## Reuse decision

<!-- What existing owner, maintained library, or current dependency is reused? If none applies, explain why. -->

## Obsolete paths to delete

<!-- Name old code, aliases, fallbacks, workflows, artifacts, or duplicate paths removed by this change and the deletion point. Use `None — <reason>` when needed. -->

## Dependency and rollout order

<!-- For a cross-repository or breaking change: owner contract/release -> consumer migration and verification -> old-contract removal. Otherwise use `None — <reason>`. -->

## Data preservation and migration

<!-- Explain how existing data is preserved, including the owning migration and recovery evidence for any authorized change. -->

## Verification and recovery

<!-- Give local/remote tests, operational evidence, success postconditions, and rollback or recovery steps. -->

## Interim-state retirement

<!-- Name the owner, tracking issue, and exact retirement condition for temporary paths. Otherwise use `None — <reason>`. -->

## Review checklist

- [ ] Repository-specific instructions and owning contracts were reconciled.
- [ ] Each rollout stage leaves a working, verifiable system.
- [ ] Existing data is preserved unless its owning migration explicitly authorizes a change.
- [ ] Obsolete paths are removed at the documented point, with no unowned compatibility state.
