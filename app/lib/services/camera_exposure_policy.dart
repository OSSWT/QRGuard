/// Conservative exposure decisions for live QR acquisition.
///
/// This policy consumes pixel-quality measurements only. It never changes or
/// interprets a Structural label, and it allows at most the caller-controlled
/// number of adjustments per stable QR sequence.
library;

import 'package:mobile_scanner/mobile_scanner.dart';

import 'capture_quality.dart';

class ExposureAdjustmentPlan {
  const ExposureAdjustmentPlan({
    required this.previousIndex,
    required this.targetIndex,
    required this.stepEv,
    required this.condition,
  });

  final int previousIndex;
  final int targetIndex;
  final double stepEv;
  final String condition;

  double get targetEv => targetIndex * stepEv;
}

ExposureAdjustmentPlan? planCaptureExposureAdjustment({
  required CaptureQualityReport quality,
  required ExposureCompensationState exposure,
}) {
  if (!exposure.supported || exposure.stepEv <= 0) return null;

  var requestedEvDelta = 0.0;
  var condition = '';
  if (quality.conditions.contains('overexposure')) {
    condition = 'overexposure';
    requestedEvDelta = quality.p05Luminance > 145 ? -0.67 : -0.34;
  } else if (quality.conditions.contains('underexposure')) {
    condition = 'underexposure';
    // Keep this small: a large positive EV can trade darkness for motion blur.
    requestedEvDelta = 0.34;
  } else {
    return null;
  }

  var indexDelta = (requestedEvDelta / exposure.stepEv).round();
  if (indexDelta == 0) indexDelta = requestedEvDelta.isNegative ? -1 : 1;
  final target = exposure.clampIndex(exposure.currentIndex + indexDelta);
  if (target == exposure.currentIndex) return null;
  return ExposureAdjustmentPlan(
    previousIndex: exposure.currentIndex,
    targetIndex: target,
    stepEv: exposure.stepEv,
    condition: condition,
  );
}
