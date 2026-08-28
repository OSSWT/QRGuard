/// Requires one QR payload to remain continuously visible before analysis.
library;

class LiveQrObservation {
  const LiveQrObservation({
    required this.startedNewSequence,
    required this.ready,
    required this.sightings,
    required this.visibleFor,
  });

  final bool startedNewSequence;
  final bool ready;
  final int sightings;
  final Duration visibleFor;
}

class LiveQrStabilityGate {
  LiveQrStabilityGate({
    this.stableFor = const Duration(milliseconds: 800),
    this.minimumSightings = 3,
    this.maximumGap = const Duration(milliseconds: 1200),
  }) : assert(minimumSightings > 0);

  final Duration stableFor;
  final int minimumSightings;
  final Duration maximumGap;

  String? _payload;
  DateTime? _firstSeen;
  DateTime? _lastSeen;
  int _sightings = 0;

  LiveQrObservation observe(String payload, DateTime seenAt) {
    final gap = _lastSeen == null ? null : seenAt.difference(_lastSeen!);
    final startedNewSequence =
        payload != _payload ||
        gap == null ||
        gap.isNegative ||
        gap > maximumGap;

    if (startedNewSequence) {
      _payload = payload;
      _firstSeen = seenAt;
      _sightings = 1;
    } else {
      _sightings += 1;
    }
    _lastSeen = seenAt;

    final visibleFor = seenAt.difference(_firstSeen!);
    return LiveQrObservation(
      startedNewSequence: startedNewSequence,
      ready: _sightings >= minimumSightings && visibleFor >= stableFor,
      sightings: _sightings,
      visibleFor: visibleFor,
    );
  }

  bool isReady(String payload, DateTime now) {
    final firstSeen = _firstSeen;
    final lastSeen = _lastSeen;
    if (payload != _payload || firstSeen == null || lastSeen == null) {
      return false;
    }
    final gap = now.difference(lastSeen);
    return !gap.isNegative &&
        gap <= maximumGap &&
        _sightings >= minimumSightings &&
        now.difference(firstSeen) >= stableFor;
  }

  void reset() {
    _payload = null;
    _firstSeen = null;
    _lastSeen = null;
    _sightings = 0;
  }
}
