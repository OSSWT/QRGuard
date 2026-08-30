# Local Structural RUN5 legacy files

The active production artifact directory was cleaned during the r01 promotion.
Large RUN5-only files were moved to ignored local storage under `local_legacy/`
so they are not baked into the new container or accidentally selected as part of
the r01 fingerprint.

| Local file | Bytes | SHA-256 |
|---|---:|---|
| `local_legacy/artifacts-20260731T173150Z-1-001.zip` | 17,900,034 | `714BF1497B4FCECC186CAECDFB330A4A022BFEF8D64D27A5CE2E45877A978E10` |
| `local_legacy/artifacts-20260802T122524Z-1-001.zip` | 17,896,282 | `7C54EF77BCFB653E5EC39A33EB62AAC4A1329227DB82782EB19D866568FEDF3C` |
| `local_legacy/structural_int8.onnx` | 4,360,735 | `D68FC4A5EB6EA960A24B6E5B182734E1033550A6E163D4B507F5ADFC0F02F342` |

The removed production-folder `metrics_summary.json` was an exact duplicate of
the retained rollback file with SHA-256
`12F3201AB1BB063FCACD8C5CA57719D0136B8FEA12A288906BCF9C6D7F1D9285`.
