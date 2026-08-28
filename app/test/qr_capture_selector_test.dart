import 'dart:typed_data';
import 'dart:ui' show Offset, Size;

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:qrguard/services/qr_capture_selector.dart';

img.Image _qrLikeFrame() {
  final image = img.Image(width: 320, height: 320);
  img.fill(image, color: img.ColorRgb8(245, 245, 245));
  const left = 48;
  const top = 48;
  const modules = 21;
  const moduleSide = 10;
  for (var row = 0; row < modules; row++) {
    for (var column = 0; column < modules; column++) {
      final black = (row * 3 + column * 5 + row * column) % 7 < 3;
      if (!black) continue;
      img.fillRect(
        image,
        x1: left + column * moduleSide,
        y1: top + row * moduleSide,
        x2: left + (column + 1) * moduleSide - 1,
        y2: top + (row + 1) * moduleSide - 1,
        color: img.ColorRgb8(0, 0, 0),
      );
    }
  }
  return image;
}

QrCaptureSample _sample(img.Image image) => QrCaptureSample(
  frame: Uint8List.fromList(img.encodePng(image)),
  corners: const [
    Offset(48, 48),
    Offset(258, 48),
    Offset(258, 258),
    Offset(48, 258),
  ],
  frameSize: const Size(320, 320),
);

void main() {
  group('selectBestQrCapture', () {
    test(
      'prefers the clear crop over an otherwise identical blurred frame',
      () {
        final sharp = _qrLikeFrame();
        final blurred = img.gaussianBlur(sharp.clone(), radius: 7);

        expect(selectBestQrCapture([_sample(blurred), _sample(sharp)]), 1);
        expect(selectBestQrCapture([_sample(sharp), _sample(blurred)]), 0);
      },
    );

    test('ignores an unusable candidate when a valid crop exists', () {
      final malformed = QrCaptureSample(
        frame: Uint8List.fromList([1, 2, 3]),
        corners: const [],
        frameSize: Size.zero,
      );

      expect(selectBestQrCapture([malformed, _sample(_qrLikeFrame())]), 1);
    });

    test('empty input has no selected index', () {
      expect(selectBestQrCapture(const []), -1);
    });

    test('ranking puts the clearest usable frame first', () {
      final sharp = _sample(_qrLikeFrame());
      final medium = _sample(img.gaussianBlur(_qrLikeFrame(), radius: 2));
      final blurred = _sample(img.gaussianBlur(_qrLikeFrame(), radius: 7));

      final ranked = rankQrCaptures([blurred, sharp, medium]);

      expect(ranked, hasLength(3));
      expect(ranked.first, 1);
      expect(ranked.last, 0);
    });
  });
}
