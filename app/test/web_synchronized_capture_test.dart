@TestOn('browser')
library;

import 'dart:async';
import 'dart:js_interop';
import 'dart:ui';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:mobile_scanner/src/web/polling_barcode_reader.dart';
import 'package:web/web.dart' as web;

extension type _CanvasStream(JSObject _) implements JSObject {
  external web.MediaStream captureStream(double framesPerSecond);
}

final class _DelayedReader extends PollingBarcodeReader {
  _DelayedReader(this.source);
  final web.HTMLCanvasElement source;
  bool changed = false;
  final snapshot = web.HTMLCanvasElement()
    ..width = 120
    ..height = 120;
  @override
  web.HTMLCanvasElement get decodedCanvas => snapshot;
  @override
  Future<void> prepareDecoder(StartOptions options) async {}
  @override
  void disposeDecoder() {}
  @override
  Future<List<Barcode>> decodeFrame(web.HTMLVideoElement video) async {
    snapshot.context2D.drawImage(video, 0, 0);
    changed = true;
    // The scene changes while the decoder is busy. Evidence must stay red.
    source.context2D
      ..fillStyle = 'blue'.toJS
      ..fillRect(0, 0, 120, 120);
    await Future<void>.delayed(const Duration(milliseconds: 100));
    return [
      const Barcode(
        rawValue: 'https://example.test',
        corners: [
          Offset(10, 10),
          Offset(110, 10),
          Offset(110, 110),
          Offset(10, 110),
        ],
      ),
    ];
  }
}

void main() {
  test(
    'emitted evidence is the decoded canvas, not the later video frame',
    () async {
      const preview = bool.fromEnvironment('QRGUARD_DIAGNOSTIC_PREVIEW');
      if (!preview) return;
      final source = web.HTMLCanvasElement()
        ..width = 120
        ..height = 120;
      source.context2D
        ..fillStyle = 'red'.toJS
        ..fillRect(0, 0, 120, 120);
      final stream = _CanvasStream(source).captureStream(30);
      final video = web.HTMLVideoElement()
        ..muted = true
        ..autoplay = true;
      final reader = _DelayedReader(source);
      web.document.body!.appendChild(video);
      final draw = Timer.periodic(const Duration(milliseconds: 30), (_) {
        source.context2D
          ..fillStyle = (reader.changed ? 'blue' : 'red').toJS
          ..fillRect(0, 0, 120, 120);
      });
      try {
        await reader
            .start(
              const StartOptions(
                cameraDirection: CameraFacing.back,
                cameraLensType: CameraLensType.any,
                cameraResolution: Size(120, 120),
                detectionSpeed: DetectionSpeed.normal,
                detectionTimeoutMs: 100,
                formats: [BarcodeFormat.qrCode],
                returnImage: true,
                torchEnabled: false,
                invertImage: false,
                autoZoom: false,
                initialZoom: null,
              ),
              videoElement: video,
              videoStream: stream,
            )
            .timeout(const Duration(seconds: 10));
        final capture = await reader.detectBarcodes().first.timeout(
          const Duration(seconds: 10),
        );
        expect(capture.image, isNotNull);
        final pixel = img.decodePng(capture.image!)!.getPixel(60, 60);
        expect(pixel.r, greaterThan(200));
        expect(pixel.b, lessThan(30));
      } finally {
        draw.cancel();
        await reader.stop();
        for (final track in stream.getTracks().toDart) {
          track.stop();
        }
        video.remove();
      }
    },
  );
}
