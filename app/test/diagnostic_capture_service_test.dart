import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/screens/diagnostic_capture_screen.dart';
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

  test('SEM-11 plan preserves QR controls in exported metadata', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/sem11_root_cause_capture_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'sem11-root-cause-screen-80-2026-09-r01');
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 3);
    expect(plan.targetSessions, 36);
    expect(plan.distances.single.id, 'screen-80');
    expect(plan.distances.single.metadata['screen_scale_percent'], 80);
    expect(plan.cases, hasLength(12));
    expect(plan.cases.every((item) => item.groundTruth == 'clean'), isTrue);
    expect(
      plan.cases.map((item) => item.metadata['mask_pattern']).toSet(),
      containsAll(<int>{0, 1, 2, 3, 4, 5, 6, 7}),
    );
    expect(
      plan.cases.map((item) => item.metadata['qr_version']).toSet(),
      containsAll(<int>{3, 4}),
    );
    expect(
      diagnosticCaptureDatabaseName(
        plan.campaignId,
        planAsset: 'assets/capture/sem11_root_cause_capture_plan.json',
      ),
      startsWith('qrguard_diagnostic_'),
    );
    expect(
      diagnosticCaptureDatabaseName('legacy'),
      'qrguard_live_diagnostic_r01.db',
    );
  });

  test('coverage development plan is balanced and never a holdout', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/structural_coverage_development_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'structural-coverage-development-2026-09-r01');
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 1);
    expect(plan.targetSessions, 48);
    expect(plan.distances.single.id, 'screen-80');
    expect(plan.distances.single.metadata['screen_scale_percent'], 80);
    for (final label in <String>['clean', 'adversarial', 'tampered']) {
      final cases = plan.cases
          .where((item) => item.groundTruth == label)
          .toList(growable: false);
      expect(cases, hasLength(16));
      expect(
        cases.map((item) => item.metadata['mask_pattern']).toSet(),
        containsAll(<int>{0, 1, 2, 3, 4, 5, 6, 7}),
      );
      expect(
        cases.map((item) => item.metadata['version_band']).toSet(),
        containsAll(<String>{'low_v1_v3', 'medium_v4_v6', 'high_v7_plus'}),
      );
    }
    expect(
      plan.cases.every(
        (item) => item.metadata['deployment_holdout_eligible'] == false,
      ),
      isTrue,
    );
  });

  test('attack calibration plan is balanced development evidence', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/structural_attack_calibration_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'structural-attack-calibration-v1');
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 1);
    expect(plan.targetSessions, 72);
    expect(plan.distances.single.id, 'screen-80');
    expect(
      plan.distances.single.metadata['role'],
      'physical_attack_development_only',
    );
    final clean = plan.cases
        .where((item) => item.groundTruth == 'clean')
        .toList(growable: false);
    final adversarial = plan.cases
        .where((item) => item.groundTruth == 'adversarial')
        .toList(growable: false);
    expect(clean, hasLength(24));
    expect(adversarial, hasLength(48));
    for (final band in <String>[
      'low_v1_v3',
      'medium_v4_v6',
      'high_v7_plus',
    ]) {
      expect(
        clean.where((item) => item.metadata['version_band'] == band),
        hasLength(8),
      );
      expect(
        adversarial.where((item) => item.metadata['version_band'] == band),
        hasLength(16),
      );
    }
    expect(
      plan.cases.every(
        (item) => item.metadata['deployment_holdout_eligible'] == false,
      ),
      isTrue,
    );
    expect(
      adversarial.map((item) => item.metadata['attack_profile']).toSet(),
      <String>{
        'screen_camera_robust_v2_function',
        'screen_camera_robust_v2_alternate',
      },
    );
  });

  test('blind coverage plan is balanced and holdout-only', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/structural_coverage_blind_holdout_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'structural-coverage-blind-holdout-2026-09-r01');
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 1);
    expect(plan.targetSessions, 48);
    expect(plan.distances.single.metadata['role'], 'blind_holdout');
    expect(
      plan.cases.every(
        (item) => item.metadata['deployment_holdout_eligible'] == true,
      ),
      isTrue,
    );
    expect(
      plan.cases.every((item) => !item.label.contains(item.groundTruth)),
      isTrue,
    );
    expect(
      plan.cases.every(
        (item) => diagnosticCaptureCaseDisplayLabel(plan, item) == item.caseId,
      ),
      isTrue,
    );
    for (final label in <String>['clean', 'adversarial', 'tampered']) {
      final cases = plan.cases
          .where((item) => item.groundTruth == label)
          .toList(growable: false);
      expect(cases, hasLength(16));
      expect(
        cases.map((item) => item.metadata['mask_pattern']).toSet(),
        containsAll(<int>{0, 1, 2, 3, 4, 5, 6, 7}),
      );
      expect(
        cases.map((item) => item.metadata['version_band']).toSet(),
        containsAll(<String>{'low_v1_v3', 'medium_v4_v6', 'high_v7_plus'}),
      );
    }
  });

  test('r07 fresh blind plan is candidate-bound and holdout-only', () async {
    final raw = await rootBundle.loadString(
      'assets/capture/structural_r07_fresh_blind_plan.json',
    );
    final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final plan = DiagnosticCapturePlan.fromJson(json);

    expect(plan.campaignId, 'structural-r07-fresh-blind-v1');
    expect(json['candidate_model_sha256'], matches(RegExp(r'^[0-9a-f]{64}$')));
    expect(plan.framesPerSession, 5);
    expect(plan.repeatsPerDistance, 1);
    expect(plan.targetSessions, 48);
    expect(plan.distances.single.id, 'screen-80');
    expect(plan.distances.single.metadata['role'], 'blind_holdout');
    expect(plan.distances.single.metadata['screen_scale_percent'], 80);
    expect(plan.distances.single.instruction, contains('blinded pass'));
    expect(plan.distances.single.instruction, isNot(contains('development')));
    expect(
      plan.cases.every(
        (item) => RegExp(r'^R7B-[0-9]{2}-[0-9A-F]{6}$').hasMatch(item.caseId),
      ),
      isTrue,
    );
    expect(
      plan.cases.every(
        (item) => item.metadata['deployment_holdout_eligible'] == true,
      ),
      isTrue,
    );
    expect(
      plan.cases.every((item) => !item.label.contains(item.groundTruth)),
      isTrue,
    );
    for (final label in <String>['clean', 'adversarial', 'tampered']) {
      final cases = plan.cases
          .where((item) => item.groundTruth == label)
          .toList(growable: false);
      expect(cases, hasLength(16));
      expect(
        cases.map((item) => item.metadata['mask_pattern']).toSet(),
        containsAll(<int>{0, 1, 2, 3, 4, 5, 6, 7}),
      );
      expect(
        cases.map((item) => item.metadata['qr_version']).toSet(),
        containsAll(<int>{3, 6, 10}),
      );
    }
  });

  test(
    'r02 acquisition plan is compact, screen-only and covers sentinels',
    () async {
      final raw = await rootBundle.loadString(
        'assets/capture/acquisition_validation_plan.json',
      );
      final json = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      final plan = DiagnosticCapturePlan.fromJson(json);

      expect(
        plan.campaignId,
        'acquisition-quality-exposure-module-scale-2026-09-r02',
      );
      expect(plan.framesPerSession, 5);
      expect(plan.repeatsPerDistance, 1);
      expect(plan.cases, hasLength(8));
      expect(plan.distances, hasLength(3));
      expect(plan.targetSessions, 24);
      expect(
        plan.distances
            .map((item) => item.metadata['screen_scale_percent'])
            .toSet(),
        <int>{80, 100},
      );
      final byId = {for (final item in plan.cases) item.caseId: item};
      expect(byId['SEM-11-PLAIN-TEXT']!.metadata['module_count'], 29);
      expect(
        byId['SEM-05-USERINFO']!.metadata['semantic_regression_sentinel'],
        isTrue,
      );
      expect(byId['ACQ-CLN-V10-LONG']!.metadata['qr_version'], 10);
      expect(byId['ACQ-CLN-V14-LONG']!.metadata['qr_version'], 14);
    },
  );
}
