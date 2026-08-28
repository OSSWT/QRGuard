/// The cropper is what stops a photo of a room from reaching the structural
/// CNN, so the cases that matter most are the ones where it must REFUSE and
/// let the branch abstain.
library;

import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' show Offset, Size;

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:qrguard/services/qr_cropper.dart';

/// A frame with a distinctly coloured square standing in for the code, so a
/// correct crop can be recognised by what colour it contains.
Uint8List _frame({
  int width = 640,
  int height = 480,
  int codeLeft = 300,
  int codeTop = 200,
  int codeSide = 80,
}) {
  final image = img.Image(width: width, height: height);
  img.fill(image, color: img.ColorRgb8(200, 200, 200)); // the "room"
  img.fillRect(
    image,
    x1: codeLeft,
    y1: codeTop,
    x2: codeLeft + codeSide - 1,
    y2: codeTop + codeSide - 1,
    color: img.ColorRgb8(0, 0, 0), // the "code"
  );
  return Uint8List.fromList(img.encodePng(image));
}

List<Offset> _corners({int left = 300, int top = 200, int side = 80}) => [
  Offset(left.toDouble(), top.toDouble()),
  Offset((left + side).toDouble(), top.toDouble()),
  Offset((left + side).toDouble(), (top + side).toDouble()),
  Offset(left.toDouble(), (top + side).toDouble()),
];

void main() {
  group('cropToCode', () {
    test(
      'handles varied real QR payloads, positions and camera resolutions',
      () {
        final cases = [
          (
            file: '01_safe_google.png',
            width: 640,
            height: 480,
            left: 24,
            top: 40,
            side: 120,
          ),
          (
            file: '02_safe_youtube.png',
            width: 1280,
            height: 720,
            left: 910,
            top: 260,
            side: 220,
          ),
          (
            file: '03_safe_utar.png',
            width: 1920,
            height: 1080,
            left: 760,
            top: 340,
            side: 320,
          ),
          (
            file: '16_wifi_open.png',
            width: 800,
            height: 800,
            left: 140,
            top: 110,
            side: 500,
          ),
        ];

        for (final sample in cases) {
          final fixture = File(
            '${Directory.current.parent.path}/data/test_qrs/${sample.file}',
          );
          final qr = img.decodeImage(fixture.readAsBytesSync())!;
          final frame = img.Image(width: sample.width, height: sample.height);
          img.fill(frame, color: img.ColorRgb8(218, 212, 200));
          img.compositeImage(
            frame,
            qr,
            dstX: sample.left,
            dstY: sample.top,
            dstW: sample.side,
            dstH: sample.side,
          );

          final result = cropToCode(
            frame: Uint8List.fromList(img.encodeJpg(frame, quality: 82)),
            corners: _corners(
              left: sample.left,
              top: sample.top,
              side: sample.side,
            ),
            frameSize: Size(sample.width.toDouble(), sample.height.toDouble()),
            normalizeCameraColor: true,
          );

          expect(result, isNotNull, reason: sample.file);
          final crop = img.decodeImage(result!)!;
          expect(crop.width, crop.height, reason: sample.file);
          expect(crop.width, greaterThanOrEqualTo(24), reason: sample.file);
        }
      },
    );

    test('cuts the code out of a much larger frame', () {
      final result = cropToCode(
        frame: _frame(),
        corners: _corners(),
        frameSize: const Size(640, 480),
      );

      expect(result, isNotNull);
      final cropped = img.decodeImage(result!)!;
      // 80px code + 15% quiet zone on each side.
      expect(cropped.width, closeTo(80 * 1.3, 2));
      expect(cropped.width, lessThan(640));
    });

    test(
      'the crop is square, because the backend resizes without letterboxing',
      () {
        // A code seen at an angle produces a rectangular bounding box.
        final result = cropToCode(
          frame: _frame(),
          corners: const [
            Offset(300, 200),
            Offset(420, 210),
            Offset(415, 260),
            Offset(302, 255),
          ],
          frameSize: const Size(640, 480),
        );

        final cropped = img.decodeImage(result!)!;
        expect(cropped.width, cropped.height);
      },
    );

    test('the crop actually contains the code, not the room', () {
      final result = cropToCode(
        frame: _frame(),
        corners: _corners(),
        frameSize: const Size(640, 480),
      );

      final cropped = img.decodeImage(result!)!;
      final centre = cropped.getPixel(cropped.width ~/ 2, cropped.height ~/ 2);
      expect(centre.r, lessThan(50)); // black square, not the grey room
    });

    test(
      'camera colour normalization removes global cast but keeps local chroma',
      () {
        final frame = img.Image(width: 320, height: 240);
        img.fill(frame, color: img.ColorRgb8(245, 235, 215));
        img.fillRect(
          frame,
          x1: 100,
          y1: 60,
          x2: 179,
          y2: 139,
          color: img.ColorRgb8(55, 25, 110),
        );
        final result = cropToCode(
          frame: Uint8List.fromList(img.encodePng(frame)),
          corners: _corners(left: 100, top: 60),
          frameSize: const Size(320, 240),
          normalizeCameraColor: true,
        );

        final cropped = img.decodeImage(result!)!;
        final centre = cropped.getPixel(
          cropped.width ~/ 2,
          cropped.height ~/ 2,
        );
        final paper = cropped.getPixel(4, 4);
        final paperChannels = [paper.r, paper.g, paper.b];
        expect(
          paperChannels.reduce(math.max) - paperChannels.reduce(math.min),
          lessThanOrEqualTo(3),
        );
        expect(
          [centre.r, centre.g, centre.b].reduce(math.max) -
              [centre.r, centre.g, centre.b].reduce(math.min),
          greaterThan(20),
        );
        expect(cropped.width, cropped.height);
      },
    );

    test('scales corners when they are in a different coordinate space', () {
      // Corners reported against a 1280x960 analysis image, frame is 640x480.
      final result = cropToCode(
        frame: _frame(),
        corners: _corners(left: 600, top: 400, side: 160),
        frameSize: const Size(1280, 960),
      );

      final cropped = img.decodeImage(result!)!;
      final centre = cropped.getPixel(cropped.width ~/ 2, cropped.height ~/ 2);
      expect(centre.r, lessThan(50));
    });

    test('no corners means no crop, so the branch abstains', () {
      expect(
        cropToCode(
          frame: _frame(),
          corners: const [],
          frameSize: const Size(640, 480),
        ),
        isNull,
      );
    });

    test('fewer than four corners is not a trustworthy image crop', () {
      expect(
        cropToCode(
          frame: _frame(),
          corners: const [Offset(100, 100), Offset(200, 100)],
          frameSize: const Size(640, 480),
        ),
        isNull,
      );
    });

    test('undecodable bytes mean no crop, never the raw frame', () {
      expect(
        cropToCode(
          frame: Uint8List.fromList([1, 2, 3, 4]),
          corners: _corners(),
          frameSize: const Size(640, 480),
        ),
        isNull,
      );
    });

    test('a code too small to carry detail is refused', () {
      expect(
        cropToCode(
          frame: _frame(),
          corners: _corners(left: 10, top: 10, side: 4),
          frameSize: const Size(640, 480),
        ),
        isNull,
      );
    });

    test('a code at the very edge stays inside the frame', () {
      final result = cropToCode(
        frame: _frame(codeLeft: 0, codeTop: 0, codeSide: 60),
        corners: _corners(left: 0, top: 0, side: 60),
        frameSize: const Size(640, 480),
      );

      expect(result, isNotNull);
      final cropped = img.decodeImage(result!)!;
      expect(cropped.width, greaterThan(0));
      expect(cropped.height, cropped.width);
    });

    test('a code filling the whole frame is clamped, not enlarged', () {
      final result = cropToCode(
        frame: _frame(codeLeft: 0, codeTop: 0, codeSide: 480),
        corners: _corners(left: 0, top: 0, side: 480),
        frameSize: const Size(640, 480),
      );

      final cropped = img.decodeImage(result!)!;
      expect(cropped.width, lessThanOrEqualTo(480));
      expect(cropped.height, lessThanOrEqualTo(480));
    });
  });
}
