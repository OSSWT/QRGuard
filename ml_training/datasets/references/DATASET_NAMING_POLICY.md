# Dataset naming policy

Canonical dataset records use stable, explicit identifiers:

`<branch>-<source>-<version>-<split>-<case_id>`

Generated QR records additionally store generator version, seed, payload hash,
image SHA-256, intended role and model-exposure state. Valid exposure states
are `training`, `validation`, `locked_test`, `capture_reference`, `demo_only`
and `legacy_not_current`.

Folder names describe data role rather than a temporary workflow, device or
person. Timestamps belong in manifests and receipts, not in the canonical
dataset identifier.
