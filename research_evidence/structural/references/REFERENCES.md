# Structural references

Links point to the official dataset record, publisher, project, conference, or
primary paper page. Access/licence status must be rechecked before admitting a new
source to training.

## Datasets and benchmarks

1. QR-DN1.0 v2, Mendeley Data, DOI
   [10.17632/t2bdr663ms.2](https://doi.org/10.17632/t2bdr663ms.2). Used as clean
   optical-channel training data and an identity-disjoint external clean holdout.
2. QR Codes on Different Surfaces v1, Mendeley Data, DOI
   [10.17632/m6mfwc52vk.1](https://doi.org/10.17632/m6mfwc52vk.1). Auxiliary
   geometry/appearance training only.
3. BarBeR dataset and paper,
   [official project page](https://ditto.ing.unimore.it/barber/), DOI
   [10.1007/978-3-031-78447-7_13](https://doi.org/10.1007/978-3-031-78447-7_13).
4. BoofCV QR benchmark,
   [official benchmark page](https://boofcv.org/index.php?title=Performance%3AQrCode).
5. Dynamsoft datasets,
   [official GitHub repository](https://github.com/Dynamsoft/datasets-from-dynamsoft).
   QRGuard keeps the acquired revision quarantined because no repository-wide
   licence was found.
6. Garg et al., OQR optical adversarial QR work,
   [USENIX Security 2026 page](https://www.usenix.org/conference/usenixsecurity26/presentation/garg-pulkit).
7. Genuine/forged QR study, *Sensors* 2025, DOI
   [10.3390/s25133855](https://doi.org/10.3390/s25133855). Data requires an author
   request.

## Methods supporting the implementation

1. He et al., “Deep Residual Learning for Image Recognition,”
   [arXiv:1512.03385](https://arxiv.org/abs/1512.03385). Basis for ResNet-18.
2. Goodfellow et al., “Explaining and Harnessing Adversarial Examples,”
   [arXiv:1412.6572](https://arxiv.org/abs/1412.6572). FGSM background.
3. Madry et al., “Towards Deep Learning Models Resistant to Adversarial Attacks,”
   [arXiv:1706.06083](https://arxiv.org/abs/1706.06083). PGD/adversarial robustness
   background.
4. Guo et al., “On Calibration of Modern Neural Networks,”
   [PMLR v70](https://proceedings.mlr.press/v70/guo17a.html). Temperature scaling
   and expected calibration error background.

The repository-wide BibTeX source remains
`ml_training/datasets/references/REFERENCES.bib`.
