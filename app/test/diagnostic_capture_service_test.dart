import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/services/diagnostic_capture_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled diagnostic plan locks the repeatability matrix', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/diagnostic_capture_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'live-camera-repeatability-2026-09-r01');
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 5);
    expect(plan.targetSessions, 30);
    expect(
      plan.distances.map((item) => item.id),
      orderedEquals(['near', 'medium', 'far']),
    );
    expect(
      plan.cases.map((item) => item.caseId),
      orderedEquals(['STR-CLN-ANGLE', 'STR-ADV-NORMAL']),
    );
    expect(
      plan.cases.map((item) => item.groundTruth),
      orderedEquals(['clean', 'adversarial']),
    );
    expect(
      plan.cases.every(
        (item) =>
            RegExp(r'^[0-9a-f]{64}$').hasMatch(item.expectedPayloadSha256),
      ),
      isTrue,
    );
    expect(raw, isNot(contains('https://')));
    expect(json['privacy'], containsPair('raw_payload_stored', false));
  });

  test('diagnostic plan rejects unsupported and incomplete schemas', () {
    expect(
      () => DiagnosticCapturePlan.fromJson({'schema_version': 99}),
      throwsA(isA<DiagnosticCaptureException>()),
    );
    expect(
      () => DiagnosticCapturePlan.fromJson({
        'schema_version': 1,
        'campaign_id': 'broken',
        'frames_per_session': 1,
        'repeats_per_distance': 0,
        'distances': <dynamic>[],
        'cases': <dynamic>[],
      }),
      throwsA(isA<DiagnosticCaptureException>()),
    );
  });
}
