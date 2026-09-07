import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/services/attendance_capture_policy.dart';

void main() {
  test('134-byte attendance envelope needs a 397px crop, not 256px', () {
    final minimum = minimumCameraCropSide('Q01:*:${'A' * 128}');
    expect(minimum, 397);
    // The reported 61x61 / 3.8px capture is about 301 pixels with padding.
    expect(61 * 3.8 * 1.3, lessThan(minimum));
  });
  test('larger attendance tokens request more original detail', () {
    expect(minimumCameraCropSide('Q01:*:${'A' * 256}'), greaterThan(397));
  });
  test('unrelated and malformed payloads keep the existing capture gate', () {
    for (final payload in [
      null,
      'https://example.com',
      'Q01:*:short',
      'Q01:*:${'A' * 5000}',
    ]) {
      expect(minimumCameraCropSide(payload), 256);
    }
  });
}
