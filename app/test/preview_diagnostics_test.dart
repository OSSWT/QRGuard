import 'dart:convert';
import 'dart:typed_data';
import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/services/preview_diagnostics.dart';

void main() {
  const scan = ScanResponse(
    verdict: Verdict.warning,
    riskScore: 26,
    reasons: [],
    payloadType: 'text',
    payload: 'private-attendance-token',
    branchScores: BranchScores(
      imageSource: 'camera',
      attendanceChecks: [
        {'reason': 'outer_grid_difference', 'outside_mismatches': 3},
      ],
    ),
  );
  test(
    'export preserves submitted pixels and omits plaintext token from metadata',
    () {
      final bytes = Uint8List.fromList([137, 80, 78, 71, 1, 2, 3]);
      final archive = ZipDecoder().decodeBytes(
        buildPreviewDiagnostics(scan, [bytes]),
      );
      expect(archive.findFile('submitted-frame-1.png')!.content, bytes);
      final metadata = utf8.decode(
        archive.findFile('diagnostics.json')!.content,
      );
      expect(metadata, isNot(contains(scan.payload!)));
      expect(
        jsonDecode(metadata)['attendance_checks'][0]['outside_mismatches'],
        3,
      );
    },
  );
  test('normal builds disable preview and excess frames are rejected', () {
    expect(diagnosticPreview, isFalse);
    expect(
      () =>
          buildPreviewDiagnostics(scan, List.generate(6, (_) => Uint8List(1))),
      throwsStateError,
    );
  });
}
