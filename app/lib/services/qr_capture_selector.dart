/// Selects the clearest rectified QR crop from a short live-camera sequence.
library;

import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' show Offset, Size;

import 'package:image/image.dart' as img;

import 'qr_cropper.dart';

/// One decoded live-camera observation of the same QR payload.
class QrCaptureSample {
  const QrCaptureSample({
    required this.frame,
    required this.corners,
    required this.frameSize,
  });

  final Uint8List frame;
  final List<Offset> corners;
  final Size frameSize;
}

/// Returns the index of the sample with the clearest usable QR crop.
///
/// This function is top-level so callers can run it in a background isolate.
/// It never changes the pixels sent to the structural model: it only chooses
/// between camera frames that were already captured. That preserves genuine
/// sticker/adversarial evidence while avoiding an early out-of-focus frame.
int selectBestQrCapture(List<QrCaptureSample> samples) {
  final ranked = rankQrCaptures(samples);
  return ranked.isEmpty ? -1 : ranked.first;
}

/// Returns every usable sample index, best acquisition quality first.
///
/// The caller sends only the first-ranked crop to the backend. The score is an
/// acquisition-quality selector, never a Safe/Blocked prediction.
List<int> rankQrCaptures(List<QrCaptureSample> samples) {
  final scored = <(int, double)>[];
  for (var index = 0; index < samples.length; index++) {
    final sample = samples[index];
    final crop = cropToCode(
      frame: sample.frame,
      corners: sample.corners,
      frameSize: sample.frameSize,
    );
    if (crop == null) continue;

    final clarity = qrCropClarity(crop);
    if (clarity == null) continue;
    scored.add((index, clarity + _geometryTieBreaker(sample) * 0.02));
  }
  scored.sort((left, right) => right.$2.compareTo(left.$2));
  return [for (final entry in scored) entry.$1];
}

/// A capture-quality score for an already rectified QR crop.
///
/// Every crop is measured at the structural model's 224 px input size. The
/// score combines black/white separation with module-edge energy and contrast.
/// It is deliberately relative rather than a Safe/Blocked threshold: blur is a
/// capture condition, not evidence that the QR itself is malicious.
double? qrCropClarity(Uint8List cropBytes) {
  img.Image? decoded;
  try {
    decoded = img.decodeImage(cropBytes);
  } catch (_) {
    return null;
  }
  if (decoded == null || decoded.width < 3 || decoded.height < 3) return null;

  final measured = img.copyResize(
    decoded,
    width: 224,
    height: 224,
    interpolation: img.Interpolation.linear,
  );
  final luminance = List<double>.filled(measured.width * measured.height, 0);
  var sum = 0.0;
  var binarySeparation = 0.0;
  for (var y = 0; y < measured.height; y++) {
    for (var x = 0; x < measured.width; x++) {
      final pixel = measured.getPixel(x, y);
      final value = 0.2126 * pixel.r + 0.7152 * pixel.g + 0.0722 * pixel.b;
      luminance[y * measured.width + x] = value;
      sum += value;
      binarySeparation += (value - 127.5).abs() / 127.5;
    }
  }

  final count = luminance.length;
  final mean = sum / count;
  var squaredDifference = 0.0;
  var edgeEnergy = 0.0;
  var edgeCount = 0;
  for (var y = 0; y < measured.height; y++) {
    for (var x = 0; x < measured.width; x++) {
      final value = luminance[y * measured.width + x];
      squaredDifference += math.pow(value - mean, 2).toDouble();
      if (x + 1 < measured.width) {
        edgeEnergy +=
            (value - luminance[y * measured.width + x + 1]).abs() / 255;
        edgeCount++;
      }
      if (y + 1 < measured.height) {
        edgeEnergy +=
            (value - luminance[(y + 1) * measured.width + x]).abs() / 255;
        edgeCount++;
      }
    }
  }

  final separation = binarySeparation / count;
  final edges = edgeCount == 0 ? 0.0 : edgeEnergy / edgeCount;
  final contrast = math.sqrt(squaredDifference / count) / 127.5;
  return separation * 0.55 + edges * 0.35 + contrast * 0.10;
}

double _geometryTieBreaker(QrCaptureSample sample) {
  if (sample.corners.length != 4 ||
      sample.frameSize.width <= 0 ||
      sample.frameSize.height <= 0) {
    return 0;
  }
  final edges = <double>[];
  var twiceArea = 0.0;
  for (var index = 0; index < sample.corners.length; index++) {
    final current = sample.corners[index];
    final next = sample.corners[(index + 1) % sample.corners.length];
    edges.add(
      math.sqrt(
        math.pow(current.dx - next.dx, 2) + math.pow(current.dy - next.dy, 2),
      ),
    );
    twiceArea += current.dx * next.dy - next.dx * current.dy;
  }
  final shortest = edges.reduce(math.min);
  final longest = edges.reduce(math.max);
  if (shortest <= 0 || longest <= 0) return 0;
  final coverage =
      (twiceArea.abs() / 2 / (sample.frameSize.width * sample.frameSize.height))
          .clamp(0.0, 1.0);
  final balance = (shortest / longest).clamp(0.0, 1.0);
  return coverage * 0.6 + balance * 0.4;
}
