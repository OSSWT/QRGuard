import 'dart:typed_data';
import '../models/scan_response.dart';

/// Acquisition feedback, not a scan verdict. Kept in memory, never in history.
class CaptureRetryRequest {
  const CaptureRetryRequest({this.scan, this.frames = const []});
  final ScanResponse? scan;
  final List<Uint8List> frames;
}

bool needsAttendanceCapture(ScanResponse scan) =>
    scan.isHiHiveAttendance &&
    scan.verdict != Verdict.blocked &&
    scan.partialAnalysis &&
    scan.branchScores.structuralStatus == AnalysisStatus.inconclusive;

class CaptureRetryBudget {
  String? _payload;
  DateTime? _started;
  int _retries = 0;
  DateTime? get startedAt => _started;
  bool canContinue(String payload, DateTime now) =>
      _payload == payload &&
      _started != null &&
      now.difference(_started!) < const Duration(seconds: 45);
  void begin(String payload, DateTime now) {
    _payload = payload;
    _started = now;
    _retries = 0;
  }

  bool take(String payload, DateTime now) {
    if (!canContinue(payload, now) || _retries >= 2) {
      return false;
    }
    _retries++;
    return true;
  }
}
