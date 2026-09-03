import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:qrguard/services/camera_exposure_policy.dart';
import 'package:qrguard/services/capture_quality.dart';

CaptureQualityReport _quality({
  required double p05,
  required double p95,
  required List<String> conditions,
}) => CaptureQualityReport(
  width: 300,
  height: 300,
  meanLuminance: (p05 + p95) / 2,
  p05Luminance: p05,
  p95Luminance: p95,
  dynamicRange: p95 - p05,
  laplacianVariance: 100,
  darkFraction: 0.2,
  brightFraction: 0.2,
  status: CaptureQualityStatus.marginal,
  conditions: conditions,
);

const _supported = ExposureCompensationState(
  supported: true,
  currentIndex: 0,
  minimumIndex: -6,
  maximumIndex: 6,
  stepEv: 1 / 3,
);

void main() {
  test('overexposure requests a small negative CameraX EV', () {
    final plan = planCaptureExposureAdjustment(
      quality: _quality(p05: 100, p95: 255, conditions: const ['overexposure']),
      exposure: _supported,
    );

    expect(plan, isNotNull);
    expect(plan!.targetIndex, -1);
    expect(plan.condition, 'overexposure');
  });

  test('severe overexposure uses two device EV steps', () {
    final plan = planCaptureExposureAdjustment(
      quality: _quality(p05: 180, p95: 255, conditions: const ['overexposure']),
      exposure: _supported,
    );

    expect(plan!.targetIndex, -2);
  });

  test('underexposure uses one small positive EV step', () {
    final plan = planCaptureExposureAdjustment(
      quality: _quality(p05: 0, p95: 130, conditions: const ['underexposure']),
      exposure: _supported,
    );

    expect(plan!.targetIndex, 1);
  });

  test('normal pixels and unsupported cameras do not change exposure', () {
    final normal = _quality(p05: 0, p95: 255, conditions: const ['normal']);
    const unsupported = ExposureCompensationState(
      supported: false,
      currentIndex: 0,
      minimumIndex: 0,
      maximumIndex: 0,
      stepEv: 0,
    );

    expect(
      planCaptureExposureAdjustment(quality: normal, exposure: _supported),
      isNull,
    );
    expect(
      planCaptureExposureAdjustment(
        quality: _quality(
          p05: 100,
          p95: 255,
          conditions: const ['overexposure'],
        ),
        exposure: unsupported,
      ),
      isNull,
    );
  });
}
