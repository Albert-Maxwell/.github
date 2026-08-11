Organization members: review the [canonical engineering policy](https://github.com/Albert-Maxwell/amt-meta/blob/main/ENGINEERING.md) before submitting. Repository-local instructions and owning contracts remain authoritative when more specific.

## Current behavior and owner

<!-- What happens today, who owns it, and what current evidence demonstrates the need? -->

## Change and affected surface

<!-- Describe the smallest complete change. List affected code, data/schemas, interfaces, repositories, artifacts, deployments, and consumers. -->

## Reuse and obsolete paths

<!-- What existing owner/library/dependency is reused? What duplicate, fallback, compatibility, or obsolete path is removed? Use `None — <reason>` when needed. -->

## Dependency and rollout order

<!-- For a cross-repository or breaking change: owner contract/release -> consumer migration and verification -> old-contract removal. Otherwise use `None — <reason>`. -->

## Data safety, verification, and recovery

<!-- Explain preservation or migration of existing data, local/remote evidence, operational checks, and rollback or recovery. -->

## Interim-state retirement

<!-- Name the owner, tracking issue, and exact retirement condition for temporary paths. Otherwise use `None — <reason>`. -->

## Review checklist

- [ ] Repository-specific instructions and owning contracts were reconciled.
- [ ] Each rollout stage leaves a working, verifiable system.
- [ ] Existing data is preserved unless its owning migration explicitly authorizes a change.
- [ ] Obsolete paths are removed at the documented point, with no unowned compatibility state.
