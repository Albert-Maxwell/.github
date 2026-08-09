# Repository Retirement

Retirement is a governed migration, not deletion. Start it when a repository has no supported contract, owner, real consumer, or viable release/deployment path; when a successor fully owns its behavior; or when its registry retirement condition is met.

The retirement owner must open an owning issue and complete these gates in order:

1. **Inventory use.** Search organization code, package references, deployments, workflows, documentation, sibling-checkout assumptions, mutable branch installs, credentials, and external consumers. Record evidence and resolve every live dependency.
2. **Map the successor.** Name the new repository, package, service, dataset, or explicit "no successor" outcome. Migrate breaking cross-repository contracts in owner-first dependency order.
3. **Preserve data and evidence.** Identify the data/schema owner and retention rule. Preserve required databases, objects, WALs, artifacts, release records, audit evidence, and reproducibility inputs. Use the owning numbered migration; do not delete or rewrite data merely because code is retiring.
4. **Remove access safely.** Revoke or rotate repository-specific credentials, secrets, deploy keys, tokens, webhooks, and external integrations. Preserve only evidence required by policy.
5. **Close the product surface.** Stop release/deployment paths, deprecate packages through their owning process, close or transfer issues, and remove obsolete copies only after consumers have migrated.
6. **Publish the outcome.** Put a prominent retirement notice in the README with status, date, owner, successor, migration path, support contact, and preserved-data location. Update [`lifecycle/repositories.yaml`](lifecycle/repositories.yaml) and link all migration/cleanup issues.
7. **Verify and archive.** Re-run consumer and deployment searches, verify successor behavior and data recovery evidence, obtain owner approval, then archive the repository.

A repository may remain a `retirement-candidate` only while its registry entry names an owner, tracking issue, target date, and exact retirement condition. Any interim compatibility or deployment state must also document rollout, verification, and the event that removes it. New product code resets the review; it must not enter an archived repository or silently revive a retirement candidate.
