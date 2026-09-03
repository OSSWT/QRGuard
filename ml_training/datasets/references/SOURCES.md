# Dataset sources and report usage

Last verified: 2026-09-02. Links below point to the official repository, data
record, publisher, or project page. `REFERENCES.bib` contains report-ready citation
records.

## Local acquisition record (2026-08-21)

- QR-DN1.0 v2 was downloaded from the official Mendeley file endpoint and verified
  as 1,025,545,184 bytes, SHA-256
  `1f175a62239646bd7d6b179245cb0970c03b179c2baf1a5e8e59ba0b156cdf61`.
  The prepared manifest contains 4,500 official-train and 2,250 official-test
  images, with 50/25 disjoint QR identities and no invalid JPEGs.
- QR Codes on Different Surfaces v1 was verified as 384,232,282 bytes, SHA-256
  `706352654a744217b6853c77362f4a32cc318d941b715423948ba2108aae7523`.
  Sixty-seven of 92 real photographs produced trustworthy rectified crops. All
  photographs encode the same QR bitmap, so the complete set is auxiliary train
  data and contributes zero independent test identities.
- The Dynamsoft selection contains 73 Git-blob-verified source files totalling
  90,378,510 bytes. Preparation accepted 232 annotated challenging-image QR crops
  and one automatically detected video crop. They remain licence-quarantined and
  are not admitted to training or Structural class metrics; the low video detector
  yield is reported as an acquisition-robustness finding rather than hidden.

## Structural Training

### Primary project data

- **QRGuard Runtime Captures** — exact post-rectification crops produced by the
  application. This is the only source that directly measures the deployed camera
  input distribution. Collection is still required for all three labels.

- **Consumed M8 clean development replay** — 80 exact-app clean crops from 16
  previously blinded QR identities. r07 uses a fixed 12-identity train / 4-identity
  validation split to repair the real V12 dense-screen gap. The source is permanently
  non-promoting, its 160 attack crops are excluded, and it does not replace a fresh
  blind device/display/session holdout.

### Admitted auxiliary sources

- **QR-DN1.0 v2** — 6,750 distorted/noisy QR images created through a real
  screen-camera optical channel, with clean counterparts. Use for camera-noise
  robustness; do not interpret distortion as tampering.
  <https://data.mendeley.com/datasets/t2bdr663ms/2>
- **QR Codes on Different Surfaces v1** — flat, challenging-surface, and synthetic
  subsets with JSON annotations. Use real originals for geometry robustness and
  keep synthetic derivatives explicitly tagged.
  <https://data.mendeley.com/datasets/m6mfwc52vk/1>

### Access-controlled or conditional sources

- **BarBeR** — 8,748 real barcode images and 9,818 annotations, including 1,756
  two-dimensional codes across several symbologies. Filter `Type == QR Code` and
  verify the terms of its component datasets. Account required.
  <https://ditto.ing.unimore.it/barber/>
- **Sensors 2025 genuine/forged QR data** — the paper reports 5,000 original and
  forged samples, but the data-availability statement requires a request to the
  corresponding author. Treat it as unavailable until access is granted.
  <https://www.mdpi.com/1424-8220/25/13/3855>
- **OQR** — 600 distance-dependent optical QR templates evaluated on six
  smartphones. Templates are adversarial source material, not QRGuard camera
  sessions; print/display and recapture them locally.
  <https://www.usenix.org/conference/usenixsecurity26/presentation/garg-pulkit>

### Independent holdout candidates

- **BoofCV QR benchmark** — blur, brightness, glare, curved, damaged,
  pathological, perspective, shadow, and display conditions. Reserve for final
  robustness evaluation.
  <https://boofcv.org/index.php?title=Performance%3AQrCode>
- **Dynamsoft datasets** — challenging real images plus damaged and reflective QR
  videos. Treat a complete video as one capture group and verify per-folder terms
  before use.
  <https://github.com/Dynamsoft/datasets-from-dynamsoft>

### Acquisition/detector expansion candidates

- **ZVZ-real / ZVZ-synth** - QR and one-dimensional barcode localization data
  linked by ABBYY's benchmark repository. The repository code is Apache-2.0, but
  the image archive needs its own licence check before use. Keep it quarantined
  and use it only to improve or evaluate acquisition after that check.
  <https://github.com/abbyy/barcode_detection_benchmark>
- **Barcode-30k** - the paper describes 30,000 synthetic segmentation images for
  QR/barcode localization under scale, occlusion, deformation and illumination.
  It does not supply Structural manipulation labels, and no exact licensed local
  archive is registered, so it is not currently admitted.
  <https://arxiv.org/abs/1807.11886>
- **EgoQR** - useful acquisition design evidence: multi-scale preprocessing,
  uneven-light handling, and explicit closer/rescan feedback. Its 528-image,
  697-code benchmark is described as internally collected; no licensed public
  archive is registered, so it is a method reference rather than training data.
  <https://arxiv.org/abs/2410.05497>

These sources can broaden detection and decoding robustness. None can replace
QRGuard's exact post-rectification Camera crops or verified physical Structural
attacks, because localization/noise labels do not prove manipulation.

## Semantic Training

- **PhiUSIIL** — primary labelled phishing/legitimate URL corpus from UCI, CC BY
  4.0. QRGuard remaps the published labels to `0=benign`, `1=dangerous`.
  <https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset>
- **Malicious URLs** — multi-class URL corpus (`benign`, `phishing`, `defacement`,
  `malware`). Keep its source tag because its provenance and label quality differ
  from UCI.
  <https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset>
- **Tranco** — research-oriented top-site ranking used only to broaden benign
  registered-domain coverage. Record the exact list ID/date in each run.
  <https://tranco-list.eu/>

## Non-duplication rule

BarBeR aggregates earlier public barcode datasets. If BarBeR is acquired, its
component images must be perceptually hashed against separately downloaded sources
before either source is counted. Augmented images, video frames, and burst frames
are not independent sessions.
