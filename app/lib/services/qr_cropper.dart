/// Cuts the detected QR code out of the camera frame.
///
/// WHY THIS EXISTS. `mobile_scanner` hands back the whole camera frame — on the
/// test device a 640x480 photo of a room in which the code is a small patch —
/// but the structural CNN was trained on images that contain ONLY a QR code. A
/// room photo is far outside that distribution, and the model answers, quite
/// correctly, "this is not a clean QR image". Measured on one and the same code
/// (`data/test_qrs/01_safe_google.png`, payload `https://www.google.com/maps`):
///
///   uploaded as its own PNG   -> p_structural 0.000146  clean     -> safe
///   sent as a camera frame    -> p_structural 0.99      tampered  -> BLOCKED
///
/// Since `p_structural` carries the largest fusion weight, an uncropped frame
/// makes every live scan Blocked and collapses the dual-branch design. Cropping
/// is what makes the structural branch mean anything on a real scan.
library;

import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' show Offset, Size;

import 'package:image/image.dart' as img;

/// Padding kept around the code, as a fraction of its size.
///
/// A QR needs a quiet zone to read as a QR at all, and the training images had
/// a white margin. Cropping flush to the corners would itself look like a
/// damaged code.
const double _quietZone = 0.15;

/// Below this the crop is too small to carry usable detail.
const int _minSide = 24;

/// The result is re-encoded as PNG: the backend re-reads it with PIL, and a
/// second JPEG generation would add compression artefacts to the very signal
/// the tampering classifier is looking at.
///
/// Returns null when no trustworthy crop can be produced. The caller must then
/// send NO image rather than the full frame, so the structural branch abstains
/// instead of reporting a false "tampered" — an absent branch contributes 0,
/// which is the locked behaviour for an abstaining branch.
Uint8List? cropToCode({
  required Uint8List frame,
  required List<Offset> corners,
  Size frameSize = Size.zero,
  bool normalizeCameraColor = false,
  int minimumOutputSide = _minSide,
}) {
  if (corners.isEmpty) return null;

  // decodeImage does not merely return null on malformed input: it probes the
  // bytes against each format in turn and a truncated frame throws out of one
  // of those probes. Uncaught, that would take down the scan callback.
  img.Image? decoded;
  try {
    decoded = img.decodeImage(frame);
  } catch (_) {
    return null;
  }
  if (decoded == null) return null;

  // The corners are expressed in the coordinate space of `frameSize`. That is
  // normally the decoded image's own size, but scale rather than assume it.
  var scaleX = 1.0;
  var scaleY = 1.0;
  if (frameSize.width > 0 && frameSize.height > 0) {
    scaleX = decoded.width / frameSize.width;
    scaleY = decoded.height / frameSize.height;
  }

  // Mobile Scanner supplies four clockwise points starting at top-left on
  // Android/iOS. Fewer points cannot define a trustworthy square QR crop.
  if (corners.length != 4) return null;
  final points = [
    for (final corner in corners)
      Offset(corner.dx * scaleX, corner.dy * scaleY),
  ];
  if (points.any((point) => !point.dx.isFinite || !point.dy.isFinite)) {
    return null;
  }

  final edges = [
    _distance(points[0], points[1]),
    _distance(points[1], points[2]),
    _distance(points[2], points[3]),
    _distance(points[3], points[0]),
  ];
  final shortest = edges.reduce(math.min);
  final longest = edges.reduce(math.max);
  if (shortest < _minSide || longest / shortest > 3.5) return null;

  // Rectify the four detected corners before the CNN sees the image. An
  // axis-aligned crop leaves a photographed QR as a trapezoid with large pieces
  // of the room in its corners; that capture geometry can look like tampering.
  final centre = Offset(
    points.map((point) => point.dx).reduce((a, b) => a + b) / 4,
    points.map((point) => point.dy).reduce((a, b) => a + b) / 4,
  );
  final expansion = 1 + 2 * _quietZone;
  final expanded = [
    for (final point in points)
      Offset(
        (centre.dx + (point.dx - centre.dx) * expansion).clamp(
          0.0,
          decoded.width - 1.0,
        ),
        (centre.dy + (point.dy - centre.dy) * expansion).clamp(
          0.0,
          decoded.height - 1.0,
        ),
      ),
  ];
  final averageEdge = edges.reduce((a, b) => a + b) / edges.length;
  final outputSide = math
      .min(
        (averageEdge * expansion).round(),
        math.min(decoded.width, decoded.height),
      )
      .toInt();
  if (outputSide < math.max(_minSide, minimumOutputSide)) return null;

  try {
    var rectified = img.copyRectify(
      decoded,
      topLeft: img.Point(expanded[0].dx, expanded[0].dy),
      topRight: img.Point(expanded[1].dx, expanded[1].dy),
      bottomRight: img.Point(expanded[2].dx, expanded[2].dy),
      bottomLeft: img.Point(expanded[3].dx, expanded[3].dy),
      interpolation: img.Interpolation.linear,
      toImage: img.Image(width: outputSide, height: outputSide),
    );
    // Laptop webcams can turn a neutral black-and-white code purple or brown.
    // Removing all chroma fixed that cast, but it also erased the local colour
    // perturbations used by FGSM/PGD adversarial examples. Correct only the
    // GLOBAL cast estimated from bright paper/quiet-zone pixels. Local RGB
    // variation, stickers, occlusion and altered edges are deliberately kept.
    if (normalizeCameraColor) _correctGlobalCameraCast(rectified);
    return Uint8List.fromList(img.encodePng(rectified));
  } catch (_) {
    return null;
  }
}

void _correctGlobalCameraCast(img.Image image) {
  var red = 0.0;
  var green = 0.0;
  var blue = 0.0;
  var brightPixels = 0;

  // A QR crop normally contains a large white quiet zone and white modules.
  // Use those pixels as a neutral reference instead of averaging black modules,
  // whose sensor noise is relatively large. The cut is intentionally broad so
  // mild under-exposure still has enough samples.
  for (var y = 0; y < image.height; y++) {
    for (var x = 0; x < image.width; x++) {
      final pixel = image.getPixel(x, y);
      final r = pixel.r.toDouble();
      final g = pixel.g.toDouble();
      final b = pixel.b.toDouble();
      final luminance = 0.299 * r + 0.587 * g + 0.114 * b;
      if (luminance < 160) continue;
      red += r;
      green += g;
      blue += b;
      brightPixels++;
    }
  }
  if (brightPixels < math.max(16, image.width * image.height ~/ 20)) return;

  final meanRed = red / brightPixels;
  final meanGreen = green / brightPixels;
  final meanBlue = blue / brightPixels;
  if (meanRed < 1 || meanGreen < 1 || meanBlue < 1) return;
  final neutral = (meanRed + meanGreen + meanBlue) / 3;
  final redGain = (neutral / meanRed).clamp(0.70, 1.45);
  final greenGain = (neutral / meanGreen).clamp(0.70, 1.45);
  final blueGain = (neutral / meanBlue).clamp(0.70, 1.45);

  for (var y = 0; y < image.height; y++) {
    for (var x = 0; x < image.width; x++) {
      final pixel = image.getPixel(x, y);
      image.setPixelRgb(
        x,
        y,
        (pixel.r * redGain).round().clamp(0, 255),
        (pixel.g * greenGain).round().clamp(0, 255),
        (pixel.b * blueGain).round().clamp(0, 255),
      );
    }
  }
}

double _distance(Offset a, Offset b) {
  final dx = a.dx - b.dx;
  final dy = a.dy - b.dy;
  return math.sqrt(dx * dx + dy * dy);
}
