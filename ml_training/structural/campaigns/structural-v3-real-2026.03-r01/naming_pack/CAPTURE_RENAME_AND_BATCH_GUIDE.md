# Structural v3 capture rename and batch guide

Campaign: `structural-v3-real-2026.03-r01`
Checkpoint: 2 of 450 pairs complete; 448 pairs / 896 authoritative pictures remain.

## Remaining pictures

| Structural label | Remaining pairs | Gallery | Live Camera | Total pictures |
|---|---:|---:|---:|---:|
| clean | 148 | 148 | 148 | 296 |
| adversarial | 150 | 150 | 150 | 300 |
| tampered | 150 | 150 | 150 | 300 |
| **Total** | **448** | **448** | **448** | **896** |

Within `clean`, 13 normal pairs remain. Each of the other nine clean quality
conditions has 15 pairs. Across all three labels, 43 normal pairs remain and
each nuisance condition has 45 pairs.

The complete one-time filename list is
`CAPTURE_NAMING_CHECKLIST_REMAINING_896.csv`. The 900-row audit view, including
the four completed pictures, is `CAPTURE_NAMING_CHECKLIST_ALL_900.csv`.

## Required filename pattern

For Gallery:

```text
{case_id}__gallery_reference.png
```

For the exact Android app camera crop:

```text
{case_id}__live_camera__xiaomi-10t-pro.png
```

Example pair:

```text
01_clean/overexposure/mild/gallery/
  cln-overexp-02__gallery_reference.png
01_clean/overexposure/mild/live_camera/
  cln-overexp-02__live_camera__xiaomi-10t-pro.png
```

## Source rule

- `gallery_reference` means the unchanged reference PNG was selected through
  **QRGuard Capture > Gallery**.
- `live_camera` means the QR was scanned through **QRGuard Capture > Live
  Camera**, and the backend saved the exact crop and metadata.
- A picture taken with the normal Xiaomi Camera app and later imported through
  Gallery is an `external_camera` picture. Renaming it to `live_camera` does not
  make it exact app evidence and it cannot close the Live Camera deployment
  gate.
- Filename, folder and visual appearance never prove the source on their own;
  the matching backend metadata is required.

## Label and quality rule

- Exposure, blur, distance, perspective, glare, shadow and screen artefacts are
  quality conditions. They never turn a clean QR into an adversarial/tampered
  label.
- Adversarial pictures require a verified attack method and attack-reference
  SHA-256 before capture.
- Tampered pictures require a documented physical manipulation method.
- Do not rename an ordinary clean QR as adversarial or tampered.
- Gallery and Live Camera members of one pair must carry the same QR payload and
  case ID. Only the Live Camera member receives the scheduled acquisition
  nuisance.

## Handoff rule

One authoritative Gallery picture and one authoritative Live Camera picture are
counted per case. Failed attempts, duplicates and screenshots of result pages do
not count. Keep failed attempts outside the listed folders so they can be
reviewed without entering the trainer.

The checklist can be delivered once as a complete naming reference. For exact
app evidence, however, capture should still be audited in small batches so a
wrong payload, label or quality setup cannot contaminate hundreds of pictures.
