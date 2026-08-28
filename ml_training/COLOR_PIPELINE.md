# Structural colour pipeline

QRGuard trains and serves the Structural image branch in **three-channel RGB**.
It does not use CMYK, CIELAB/Lab, or a CMYK-like “CMYKL” representation.

## Exact tensor contract

1. Decode the PNG/JPEG and convert it to RGB.
2. Resize to `224 × 224` using bilinear interpolation for model input.
3. Convert each channel from integer `[0, 255]` to float `[0, 1]`.
4. Normalise with the ImageNet channel statistics:
   `mean = [0.485, 0.456, 0.406]` and
   `std = [0.229, 0.224, 0.225]`.
5. Pass an `N × 3 × 224 × 224` tensor to the ResNet-18 Structural model.

The serving implementation in `backend/structural/structural_service.py` uses
the same RGB order, interpolation and normalisation. Export parity tests compare
native PyTorch probabilities with ONNX probabilities.

## Coloured QR coverage

The generated base set is not black-and-white only. A deterministic 35% of base
QRs use a dark RGB module colour sampled independently in `[0, 90]` and a light
RGB background sampled in `[200, 255]`. Some high-error-correction examples also
contain coloured centre logos. Training adds mild RGB brightness, contrast and
saturation jitter; exact app-camera crops retain their real sensor colour.

The app corrects only a global camera colour cast estimated from bright
quiet-zone/paper pixels. It deliberately preserves local colour changes,
stickers, occlusions and adversarial perturbations. Converting everything to
greyscale or Lab would erase some of that evidence and would no longer match the
deployed three-channel model.

CMYK is a print-production colour model, not the native representation returned
by the phone camera or expected by the ImageNet-pretrained network. Lab can be
useful in specialised colour-invariance experiments, but adopting it would
require a new architecture/input contract, retraining, calibration and a fresh
camera holdout—not a transparent preprocessing switch.
