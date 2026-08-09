## Current behavior and owner

<!-- What happens today? Name the owning repository/team/person and cite current evidence. -->

## Change and affected surface

<!-- What changes? List affected code, data/formats/schemas, contracts/APIs, repositories, deployments, artifacts, and consumers. -->

## Obsolete paths deleted

<!-- Name deleted code, aliases, fallbacks, workflows, artifacts, or duplicates. If none, write `None — <reason>`. -->

## Reuse and library decision

<!-- What existing owner/library/dependency is reused? For an extraction/addition, name real consumers and its versioned release mechanism. -->

## Cross-repository dependency order

<!-- For breaking contracts: owning contract land/release -> consumer migrations and verification -> old contract removal. Otherwise write `None — <reason>`. -->

## Data preservation and migration

<!-- Name the data/schema owner, numbered migration, retention/recovery evidence, and any explicitly authorized deletion/overwrite/normalization/rewrite. Otherwise write `None — <reason>`. -->

## Rollout and verification

<!-- Give end-to-end rollout steps, tests/observability/evidence, deployment/consumer checks, and rollback/recovery. -->

## Interim-state retirement

<!-- For every temporary path, name owner, tracking issue, target date if known, and exact retirement condition. Otherwise write `None — no interim state because ...`. -->

## Review checklist

- [ ] Each rollout stage leaves an end-to-end working system.
- [ ] Repository-specific contracts, determinism, storage ownership, and evidence rules remain authoritative.
- [ ] Obsolete paths are deleted at the documented point; no unowned compatibility shim remains.
- [ ] Existing data is preserved unless explicit authorization and the owning migration permit otherwise.
- [ ] Documentation and [`lifecycle/repositories.yaml`](https://github.com/Albert-Maxwell/.github/blob/main/lifecycle/repositories.yaml) are updated when ownership, consumers, release/deployment, lifecycle, or retirement conditions change.
