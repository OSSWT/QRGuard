/// Captures the current live-camera frame on platforms where mobile_scanner
/// does not include encoded image bytes in BarcodeCapture.
library;

export 'live_camera_frame_stub.dart'
    if (dart.library.js_interop) 'live_camera_frame_web.dart';
