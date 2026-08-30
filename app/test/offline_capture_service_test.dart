import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/services/offline_capture_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'bundled offline plan matches the hash-locked Camera repair campaign',
    () async {
      final raw = await rootBundle.loadString(
        'assets/capture/offline_capture_plan.json',
      );
      final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      final plan = OfflineCapturePlan.fromJson(json);

      expect(plan.campaignId, 'structural-v3-real-2026.03-r01');
      expect(plan.cases, hasLength(119));
      expect(plan.initialCaseId, plan.cases.first.caseId);
      expect(plan.maxUnexportedSessions, 40);
      expect(
        plan.cases.map((item) => item.captureNumber),
        orderedEquals(List<int>.generate(119, (index) => index + 1)),
      );
      expect(plan.cases.every((item) => item.completedSources.isEmpty), isTrue);
      expect(plan.cases.where((item) => item.label == 'clean'), hasLength(40));
      expect(
        plan.cases.where((item) => item.label == 'adversarial'),
        hasLength(40),
      );
      expect(
        plan.cases.where((item) => item.label == 'tampered'),
        hasLength(39),
      );
      expect(plan.cases.every((item) => !item.galleryRequiredForTest), isTrue);
      expect(
        plan.cases.every(
          (item) =>
              RegExp(r'^[0-9a-f]{64}$').hasMatch(item.expectedPayloadSha256),
        ),
        isTrue,
      );
      expect(
        plan.cases.first.matchesExpectedPayload('wrong QR payload'),
        isFalse,
      );
      final adversarial = plan.cases.where(
        (item) => item.label == 'adversarial',
      );
      expect(
        adversarial.every((item) => item.defaultAttackMethod == 'eot_fgsm'),
        isTrue,
      );
      expect(
        adversarial.every(
          (item) => item.defaultAttackReferenceSha256.length == 64,
        ),
        isTrue,
      );
      final tampered = plan.cases.where((item) => item.label == 'tampered');
      expect(
        tampered.every(
          (item) => item.defaultManipulationMethod == 'sticker_overlay',
        ),
        isTrue,
      );
      expect(raw, isNot(contains('pair_token')));
      expect(raw, isNot(contains('physical_qr_token')));
      expect(raw, isNot(contains('https://')));
    },
  );

  test('offline plan rejects an unsupported schema', () {
    expect(
      () => OfflineCapturePlan.fromJson({'schema_version': 99}),
      throwsA(isA<OfflineCaptureException>()),
    );
  });
}
