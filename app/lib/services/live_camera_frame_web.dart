import 'dart:convert';
import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

/// mobile_scanner 7.x deliberately emits no `BarcodeCapture.image` on Web.
/// Snapshot its active video element before the scanner is stopped so the
/// Structural branch receives the same frame whose QR corners were detected.
Future<Uint8List?> captureLiveCameraFrame() async {
  try {
    final element = web.document.querySelector('video');
    if (element == null) return null;
    final video = element as web.HTMLVideoElement;
    final width = video.videoWidth;
    final height = video.videoHeight;
    if (video.paused || width <= 0 || height <= 0) return null;

    final canvas = web.HTMLCanvasElement()
      ..width = width
      ..height = height;
    canvas.context2D.drawImage(video, 0, 0);
    // JPEG mirrors the native Android capture and keeps a 1080p webcam frame
    // comfortably below the API's upload limit. Cropping re-encodes the small
    // QR region as lossless PNG before Structural inference.
    final dataUrl = canvas.toDataURL('image/jpeg', 0.90.toJS);
    final separator = dataUrl.indexOf(',');
    if (separator < 0 || separator == dataUrl.length - 1) return null;
    final bytes = base64Decode(dataUrl.substring(separator + 1));
    return bytes.isEmpty ? null : bytes;
  } catch (_) {
    return null;
  }
}
