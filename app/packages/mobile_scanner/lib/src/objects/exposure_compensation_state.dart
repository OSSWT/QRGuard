/// Camera exposure-compensation capability reported by CameraX.
class ExposureCompensationState {
  const ExposureCompensationState({
    required this.supported,
    required this.currentIndex,
    required this.minimumIndex,
    required this.maximumIndex,
    required this.stepEv,
  });

  factory ExposureCompensationState.fromMap(Map<Object?, Object?> map) {
    return ExposureCompensationState(
      supported: map['supported'] as bool? ?? false,
      currentIndex: (map['currentIndex'] as num?)?.round() ?? 0,
      minimumIndex: (map['minimumIndex'] as num?)?.round() ?? 0,
      maximumIndex: (map['maximumIndex'] as num?)?.round() ?? 0,
      stepEv: (map['stepEv'] as num?)?.toDouble() ?? 0,
    );
  }

  final bool supported;
  final int currentIndex;
  final int minimumIndex;
  final int maximumIndex;
  final double stepEv;

  double get currentEv => currentIndex * stepEv;

  int clampIndex(int value) => value.clamp(minimumIndex, maximumIndex);
}
