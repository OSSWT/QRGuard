/// A conservative acquisition estimate, not a decoded QR version or safety result.
library;

import 'dart:convert';
import 'dart:math' as math;

final _attendanceEnvelope = RegExp(r'^Q01:\*:[A-Za-z0-9+/_-]{32,}={0,2}$');

// QR byte-mode capacity at H error correction, versions 1..40. Central-logo
// attendance checks require H. An issuer may select a larger version; backend
// measurement remains authoritative and can still request more detail.
const _highCorrectionBytes = [
  7,
  14,
  24,
  34,
  44,
  58,
  64,
  84,
  98,
  119,
  137,
  155,
  177,
  194,
  220,
  250,
  280,
  310,
  338,
  382,
  403,
  439,
  461,
  511,
  535,
  593,
  625,
  658,
  698,
  742,
  790,
  842,
  898,
  958,
  983,
  1051,
  1093,
  1139,
  1219,
  1273,
];

int minimumCameraCropSide(String? payload) {
  final value = payload?.trim() ?? '';
  if (value.length > 4096 || !_attendanceEnvelope.hasMatch(value)) return 256;
  final bytes = utf8.encode(value).length;
  final index = _highCorrectionBytes.indexWhere(
    (capacity) => capacity >= bytes,
  );
  final modules = index < 0 ? 177 : 21 + 4 * index;
  return math.max(256, (modules * 5.0 * 1.30).ceil());
}

/// Bound close-up camera crops before rectification and lossless PNG encoding.
/// The backend ultimately measures and infers at 224 px, while attendance grid
/// checks need the payload-dependent minimum above. Keeping up to 512 px avoids
/// multi-second work on near-full-frame 1080p QR codes without discarding pixels
/// required by larger attendance symbols.
int maximumCameraCropSide(String? payload) =>
    math.max(512, minimumCameraCropSide(payload));
