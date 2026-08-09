# Repository Creation

Create a repository only when its boundary and first useful outcome are known. A placeholder is not an acceptable lifecycle state.

Before creation, the sponsoring owner must document:

- a primary owner and backup owner;
- the product, library, research, or data contract and why an existing repository cannot own it;
- real intended consumers and the boundary with related repositories;
- a README that states purpose, status, owners, setup, and support expectations;
- the first end-to-end deliverable, including how it will be verified;
- the release, publication, or deployment mechanism appropriate to the contract;
- persisted-data/schema ownership, retention, and migration responsibilities;
- an initial lifecycle entry in [`lifecycle/repositories.yaml`](lifecycle/repositories.yaml);
- an archive date or an objective archive/retirement condition, with a tracking issue.

Do not create the repository until the owner accepts these responsibilities. If work cannot yet satisfy them, keep the proposal in the owning product's issue tracker or branch.

At first release or deployment, verify that the README, registry entry, consumers, owner, dependency contracts, and release path describe the actual system. Apply [ENGINEERING.md](ENGINEERING.md) to later changes and [RETIREMENT.md](RETIREMENT.md) when the contract no longer has a supported consumer.
