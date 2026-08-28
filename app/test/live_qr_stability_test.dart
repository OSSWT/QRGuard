import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/services/live_qr_stability.dart';

void main() {
  group('LiveQrStabilityGate', () {
    final start = DateTime(2026, 8, 10, 12);

    test('responsive policy accepts one ML Kit-validated QR sighting', () {
      final gate = LiveQrStabilityGate(
        stableFor: Duration.zero,
        minimumSightings: 1,
        maximumGap: const Duration(milliseconds: 700),
      );

      final first = gate.observe('decoded', start);

      expect(first.startedNewSequence, isTrue);
      expect(first.sightings, 1);
      expect(first.ready, isTrue);
      expect(gate.isReady('decoded', start), isTrue);
    });

    test('requires repeated sightings for the complete stable period', () {
      final gate = LiveQrStabilityGate();

      expect(gate.observe('same', start).ready, isFalse);
      expect(
        gate
            .observe('same', start.add(const Duration(milliseconds: 240)))
            .ready,
        isFalse,
      );
      expect(
        gate
            .observe('same', start.add(const Duration(milliseconds: 480)))
            .ready,
        isFalse,
      );
      expect(
        gate
            .observe('same', start.add(const Duration(milliseconds: 820)))
            .ready,
        isTrue,
      );
    });

    test('a payload change starts a new stability sequence', () {
      final gate = LiveQrStabilityGate();
      gate.observe('first', start);
      gate.observe('first', start.add(const Duration(milliseconds: 250)));
      gate.observe('first', start.add(const Duration(milliseconds: 500)));

      final changed = gate.observe(
        'second',
        start.add(const Duration(milliseconds: 750)),
      );

      expect(changed.startedNewSequence, isTrue);
      expect(changed.sightings, 1);
      expect(changed.ready, isFalse);
    });

    test('a long detection gap prevents stale frames being ready', () {
      final gate = LiveQrStabilityGate();
      gate.observe('same', start);
      gate.observe('same', start.add(const Duration(milliseconds: 240)));
      gate.observe('same', start.add(const Duration(milliseconds: 480)));
      final afterGap = gate.observe(
        'same',
        start.add(const Duration(milliseconds: 1800)),
      );

      expect(afterGap.startedNewSequence, isTrue);
      expect(afterGap.ready, isFalse);
    });

    test('reset clears a previously ready payload', () {
      final gate = LiveQrStabilityGate();
      gate.observe('same', start);
      gate.observe('same', start.add(const Duration(milliseconds: 240)));
      gate.observe('same', start.add(const Duration(milliseconds: 480)));
      gate.observe('same', start.add(const Duration(milliseconds: 820)));
      expect(
        gate.isReady('same', start.add(const Duration(milliseconds: 820))),
        isTrue,
      );

      gate.reset();

      expect(
        gate.isReady('same', start.add(const Duration(milliseconds: 820))),
        isFalse,
      );
    });
  });
}
