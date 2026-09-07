import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/services/capture_retry.dart';

void main() {
  test('automatic capture is bounded and tied to the same payload', () {
    final budget = CaptureRetryBudget();
    final now = DateTime(2026);
    budget.begin('one', now);
    expect(budget.take('different', now), isFalse);
    expect(budget.take('one', now), isTrue);
    expect(budget.take('one', now.add(const Duration(seconds: 20))), isTrue);
    expect(budget.take('one', now.add(const Duration(seconds: 21))), isFalse);
    budget.begin('two', now);
    expect(budget.take('two', now.add(const Duration(seconds: 45))), isFalse);
  });
  test(
    'only incomplete attendance acquisition retries, never Blocked or Safe',
    () {
      for (final verdict in Verdict.values) {
        final scan = ScanResponse(
          verdict: verdict,
          riskScore: 26,
          reasons: const [],
          payloadType: 'attendance',
          payload: 'Q01:*:${'A' * 128}',
          partialAnalysis: true,
          branchScores: const BranchScores(
            structuralStatus: AnalysisStatus.inconclusive,
          ),
        );
        expect(needsAttendanceCapture(scan), verdict != Verdict.blocked);
      }
      const safe = ScanResponse(
        verdict: Verdict.safe,
        riskScore: 1,
        reasons: [],
        payloadType: 'attendance',
        branchScores: BranchScores(),
      );
      expect(needsAttendanceCapture(safe), isFalse);
    },
  );
}
