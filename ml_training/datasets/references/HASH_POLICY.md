# Dataset hash policy

- Original archives use SHA-256 over the exact downloaded bytes.
- Expanded archives are validated by member path, uncompressed size and CRC32
  before an expanded duplicate is removed.
- Generated images use SHA-256 per file plus a deterministic manifest hash.
- Payloads that should not be disclosed are represented by a salted or scoped
  payload hash; raw secrets and credentials are never stored in a manifest.
- A moved file is accepted only when its post-move SHA-256 matches the recorded
  source hash.
