import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:qrguard/services/capture_quality.dart';

Uint8List _qrLike({int dark = 0, int light = 255}) {
  final image = img.Image(width: 280, height: 280);
  img.fill(image, color: img.ColorRgb8(light, light, light));
  for (var row = 0; row < 29; row++) {
    for (var column = 0; column < 29; column++) {
      if ((row * 7 + column * 11 + row * column) % 5 < 2) {
        img.fillRect(
          image,
          x1: column * 8 + 24,
          y1: row * 8 + 24,
          x2: column * 8 + 31,
          y2: row * 8 + 31,
          color: img.ColorRgb8(dark, dark, dark),
        );
      }
    }
  }
  return Uint8List.fromList(img.encodePng(image));
}

void main() {
  test('quality report measures exposure and detail without attack labels', () {
    final report = assessCaptureQuality(_qrLike());

    expect(report, isNotNull);
    expect(report!.status, CaptureQualityStatus.usable);
    expect(report.dynamicRange, greaterThan(200));
    expect(report.laplacianVariance, greaterThan(55));
    expect(report.conditions, const ['normal']);
    expect(
      report.conditions,
      isNot(contains(anyOf('clean', 'adversarial', 'tampered'))),
    );
  });

  test('flat and severely overexposed crops are rejected', () {
    final flat = img.Image(width: 280, height: 280);
    img.fill(flat, color: img.ColorRgb8(190, 190, 190));
    final flatReport = assessCaptureQuality(
      Uint8List.fromList(img.encodePng(flat)),
    );
    final overexposed = assessCaptureQuality(_qrLike(dark: 180));

    expect(flatReport!.status, CaptureQualityStatus.unusable);
    expect(overexposed!.status, CaptureQualityStatus.unusable);
    expect(overexposed.conditions, contains('overexposure'));
  });

  test('blur lowers the measured Laplacian detail', () {
    final sharpBytes = _qrLike();
    final sharpImage = img.decodePng(sharpBytes)!;
    final blurredImage = img.gaussianBlur(sharpImage, radius: 6);
    final sharp = assessCaptureQuality(sharpBytes)!;
    final blurred = assessCaptureQuality(
      Uint8List.fromList(img.encodePng(blurredImage)),
    )!;

    expect(blurred.laplacianVariance, lessThan(sharp.laplacianVariance));
  });

  test('ranking excludes unusable crops and returns the best three', () {
    final marginal = _qrLike(light: 170);
    final unusable = _qrLike(dark: 180);
    final normalA = _qrLike();
    final normalB = _qrLike(dark: 8, light: 248);
    final ranked = rankCaptureCrops([unusable, marginal, normalA, normalB]);

    expect(ranked, hasLength(3));
    expect(ranked.map((sample) => sample.originalIndex), isNot(contains(0)));
    expect(ranked.every((sample) => sample.quality.usable), isTrue);
    expect(ranked.first.quality.status, CaptureQualityStatus.usable);
  });

  test('live frame quality measures only the detected QR region', () {
    final frame = img.Image(width: 420, height: 420);
    img.fill(frame, color: img.ColorRgb8(120, 120, 120));
    final qr = img.decodePng(_qrLike())!;
    img.compositeImage(frame, qr, dstX: 70, dstY: 70);

    final telemetry = assessFrameCaptureQuality(
      CaptureFrameQualityRequest(
        frame: Uint8List.fromList(img.encodeJpg(frame, quality: 90)),
        cornerCoordinates: const [70, 70, 350, 70, 350, 350, 70, 350],
        frameWidth: 420,
        frameHeight: 420,
      ),
    );
    final report = CaptureQualityReport.fromTelemetry(telemetry!);

    expect(report.dynamicRange, greaterThan(180));
    expect(report.status, isNot(CaptureQualityStatus.unusable));
  });
}
