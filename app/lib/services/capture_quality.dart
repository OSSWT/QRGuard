/// Pixel-level acquisition quality for rectified live-camera QR crops.
///
/// This service never predicts whether a QR is clean or manipulated. It only
/// answers whether the captured pixels preserve enough contrast and detail for
/// the Structural branch, then ranks usable temporal frames. The measurements
/// intentionally mirror the backend quality gate so a frame rejected on-device
/// is not silently treated as safe.
library;

import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' show Offset, Size;

import 'package:image/image.dart' as img;

import 'qr_cropper.dart';

const int _measureSide = 224;

enum CaptureQualityStatus { usable, marginal, unusable }

class CaptureQualityReport {
  const CaptureQualityReport({
    required this.width,
    required this.height,
    required this.meanLuminance,
    required this.p05Luminance,
    required this.p95Luminance,
    required this.dynamicRange,
    required this.laplacianVariance,
    required this.darkFraction,
    required this.brightFraction,
    required this.status,
    required this.conditions,
  });

  factory CaptureQualityReport.fromTelemetry(Map<Object?, Object?> map) {
    final statusName = map['status'] as String?;
    return CaptureQualityReport(
      width: (map['width'] as num?)?.round() ?? 0,
      height: (map['height'] as num?)?.round() ?? 0,
      meanLuminance: (map['mean_luminance'] as num?)?.toDouble() ?? 0,
      p05Luminance: (map['p05_luminance'] as num?)?.toDouble() ?? 0,
      p95Luminance: (map['p95_luminance'] as num?)?.toDouble() ?? 0,
      dynamicRange: (map['dynamic_range'] as num?)?.toDouble() ?? 0,
      laplacianVariance: (map['laplacian_variance'] as num?)?.toDouble() ?? 0,
      darkFraction: (map['dark_fraction'] as num?)?.toDouble() ?? 0,
      brightFraction: (map['bright_fraction'] as num?)?.toDouble() ?? 0,
      status: CaptureQualityStatus.values.firstWhere(
        (value) => value.name == statusName,
        orElse: () => CaptureQualityStatus.unusable,
      ),
      conditions: List.unmodifiable(
        ((map['conditions'] as List<Object?>?) ?? const [])
            .whereType<String>()
            .toList(),
      ),
    );
  }

  final int width;
  final int height;
  final double meanLuminance;
  final double p05Luminance;
  final double p95Luminance;
  final double dynamicRange;
  final double laplacianVariance;
  final double darkFraction;
  final double brightFraction;
  final CaptureQualityStatus status;
  final List<String> conditions;

  bool get usable => status != CaptureQualityStatus.unusable;

  /// A bounded, source-neutral score used only to choose between frames of the
  /// same QR observation. Status dominates; detail and contrast break ties.
  double get selectionScore {
    final statusScore = switch (status) {
      CaptureQualityStatus.usable => 4.0,
      CaptureQualityStatus.marginal => 2.0,
      CaptureQualityStatus.unusable => -10.0,
    };
    final contrastScore = (dynamicRange / 255).clamp(0.0, 1.0) * 1.5;
    final focusScore =
        (math.log(1 + laplacianVariance) / math.log(2001)).clamp(0.0, 1.0) *
        1.25;
    return statusScore + contrastScore + focusScore;
  }

  Map<String, Object> toTelemetry() => {
    'width': width,
    'height': height,
    'mean_luminance': meanLuminance,
    'p05_luminance': p05Luminance,
    'p95_luminance': p95Luminance,
    'dynamic_range': dynamicRange,
    'laplacian_variance': laplacianVariance,
    'dark_fraction': darkFraction,
    'bright_fraction': brightFraction,
    'status': status.name,
    'conditions': conditions,
    'selection_score': selectionScore,
  };
}

/// A sendable request for lightweight quality feedback while the camera stays
/// open. Coordinates are flattened because dart:ui objects should not cross the
/// background-isolate boundary.
class CaptureFrameQualityRequest {
  const CaptureFrameQualityRequest({
    required this.frame,
    required this.cornerCoordinates,
    required this.frameWidth,
    required this.frameHeight,
  });

  final Uint8List frame;
  final List<double> cornerCoordinates;
  final double frameWidth;
  final double frameHeight;
}

/// Rectify only the detected QR and measure its raw exposure in a worker
/// isolate. Global colour correction is deliberately disabled here because the
/// result controls acquisition rather than Structural preprocessing.
Map<String, Object>? assessFrameCaptureQuality(
  CaptureFrameQualityRequest request,
) {
  if (request.cornerCoordinates.length != 8) return null;
  final crop = cropToCode(
    frame: request.frame,
    corners: [
      for (var index = 0; index < 8; index += 2)
        Offset(
          request.cornerCoordinates[index],
          request.cornerCoordinates[index + 1],
        ),
    ],
    frameSize: Size(request.frameWidth, request.frameHeight),
    normalizeCameraColor: false,
  );
  if (crop == null) return null;
  return assessCaptureQuality(crop)?.toTelemetry();
}

class RankedCaptureCrop {
  const RankedCaptureCrop({
    required this.bytes,
    required this.quality,
    required this.originalIndex,
  });

  final Uint8List bytes;
  final CaptureQualityReport quality;
  final int originalIndex;
}

CaptureQualityReport? assessCaptureQuality(Uint8List encodedCrop) {
  img.Image? decoded;
  try {
    decoded = img.decodeImage(encodedCrop);
  } catch (_) {
    return null;
  }
  if (decoded == null || decoded.width < 2 || decoded.height < 2) return null;

  final side = math.min(_measureSide, math.min(decoded.width, decoded.height));
  final measured = decoded.width == side && decoded.height == side
      ? decoded
      : img.copyResize(
          decoded,
          width: side,
          height: side,
          interpolation: img.Interpolation.linear,
        );
  final luminance = Float64List(side * side);
  var sum = 0.0;
  var dark = 0;
  var bright = 0;
  var offset = 0;
  for (var y = 0; y < side; y++) {
    for (var x = 0; x < side; x++) {
      final pixel = measured.getPixel(x, y);
      final value =
          0.299 * pixel.r.toDouble() +
          0.587 * pixel.g.toDouble() +
          0.114 * pixel.b.toDouble();
      luminance[offset++] = value;
      sum += value;
      if (value <= 24) dark++;
      if (value >= 240) bright++;
    }
  }

  final sorted = luminance.toList()..sort();
  final p05 = _percentile(sorted, 0.05);
  final p95 = _percentile(sorted, 0.95);
  final dynamicRange = p95 - p05;
  final focus = _laplacianVariance(luminance, side);
  final conditions = <String>[];
  if (p95 < 145) conditions.add('underexposure');
  if (p05 > 85) conditions.add('overexposure');
  if (dynamicRange < 90) conditions.add('low_contrast');
  if (focus < 55) conditions.add('blur');
  if (math.min(decoded.width, decoded.height) < 48) {
    conditions.add('small_input');
  }

  final severe =
      math.min(decoded.width, decoded.height) < 24 ||
      dynamicRange < 35 ||
      focus < 10 ||
      p95 < 105 ||
      p05 > 145;
  final status = severe
      ? CaptureQualityStatus.unusable
      : conditions.isEmpty
      ? CaptureQualityStatus.usable
      : CaptureQualityStatus.marginal;

  return CaptureQualityReport(
    width: decoded.width,
    height: decoded.height,
    meanLuminance: sum / luminance.length,
    p05Luminance: p05,
    p95Luminance: p95,
    dynamicRange: dynamicRange,
    laplacianVariance: focus,
    darkFraction: dark / luminance.length,
    brightFraction: bright / luminance.length,
    status: status,
    conditions: List.unmodifiable(
      conditions.isEmpty ? const ['normal'] : conditions,
    ),
  );
}

/// Select usable crops by pixel quality, with a small bonus for exposure
/// diversity. The bonus can never promote an unusable frame over a usable one.
List<RankedCaptureCrop> rankCaptureCrops(
  List<Uint8List> crops, {
  int maximum = 3,
}) {
  if (maximum <= 0) return const [];
  final remaining = <RankedCaptureCrop>[];
  for (var index = 0; index < crops.length; index++) {
    final quality = assessCaptureQuality(crops[index]);
    if (quality == null || !quality.usable) continue;
    remaining.add(
      RankedCaptureCrop(
        bytes: crops[index],
        quality: quality,
        originalIndex: index,
      ),
    );
  }

  final selected = <RankedCaptureCrop>[];
  while (remaining.isNotEmpty && selected.length < maximum) {
    remaining.sort((left, right) {
      final rightScore = _diverseScore(right, selected);
      final leftScore = _diverseScore(left, selected);
      final scoreOrder = rightScore.compareTo(leftScore);
      if (scoreOrder != 0) return scoreOrder;
      return left.originalIndex.compareTo(right.originalIndex);
    });
    selected.add(remaining.removeAt(0));
  }
  return selected;
}

double _diverseScore(
  RankedCaptureCrop candidate,
  List<RankedCaptureCrop> selected,
) {
  if (selected.isEmpty) return candidate.quality.selectionScore;
  final nearestExposureDistance = selected
      .map(
        (sample) =>
            (candidate.quality.meanLuminance - sample.quality.meanLuminance)
                .abs(),
      )
      .reduce(math.min);
  final diversityBonus = (nearestExposureDistance / 32).clamp(0.0, 1.0) * 0.20;
  return candidate.quality.selectionScore + diversityBonus;
}

double _percentile(List<double> sorted, double fraction) {
  if (sorted.length == 1) return sorted.first;
  final position = (sorted.length - 1) * fraction;
  final lower = position.floor();
  final upper = position.ceil();
  if (lower == upper) return sorted[lower];
  final weight = position - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

double _laplacianVariance(Float64List luminance, int side) {
  if (side < 3) return 0;
  var sum = 0.0;
  var squareSum = 0.0;
  var count = 0;
  for (var y = 1; y < side - 1; y++) {
    for (var x = 1; x < side - 1; x++) {
      final centre = y * side + x;
      final value =
          -4 * luminance[centre] +
          luminance[centre - side] +
          luminance[centre + side] +
          luminance[centre - 1] +
          luminance[centre + 1];
      sum += value;
      squareSum += value * value;
      count++;
    }
  }
  if (count == 0) return 0;
  final mean = sum / count;
  return math.max(0, squareSum / count - mean * mean);
}
