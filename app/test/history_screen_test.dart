import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/screens/history_screen.dart';
import 'package:qrguard/services/history_service.dart';
import 'package:qrguard/theme.dart';

void main() {
  final records = [
    ScanRecord(
      id: 1,
      payloadHash: 'a' * 64,
      registeredDomain: 'google.com',
      verdict: 'safe',
      riskScore: 8,
      scannedAt: DateTime(2026, 8, 10, 9, 15),
    ),
    ScanRecord(
      id: 2,
      payloadHash: 'b' * 64,
      registeredDomain: 'xn--pypal-4ve.com',
      verdict: 'warning',
      riskScore: 44,
      scannedAt: DateTime(2026, 8, 10, 9, 20),
    ),
    ScanRecord(
      id: 3,
      payloadHash: 'c' * 64,
      registeredDomain: 'maybank-login.xyz',
      verdict: 'blocked',
      riskScore: 100,
      scannedAt: DateTime(2026, 8, 10, 9, 25),
    ),
  ];

  test('history search and categories filter privacy-safe metadata', () {
    expect(
      filterHistoryRecords(
        records,
        category: HistoryCategory.warning,
      ).single.registeredDomain,
      'xn--pypal-4ve.com',
    );
    expect(
      filterHistoryRecords(records, query: 'maybank').single.riskScore,
      100,
    );
    expect(filterHistoryRecords(records, query: 'bbbb'), hasLength(1));
    expect(filterHistoryRecords(records, query: '44'), hasLength(1));
  });

  test('partial scan is represented as Warning in history', () {
    final scan = ScanResponse(
      verdict: Verdict.safe,
      riskScore: 20,
      reasons: const [],
      payloadType: 'url',
      branchScores: const BranchScores(pStructural: null, pUrl: 0.02),
      partialAnalysis: true,
      deepCheckAvailable: false,
      payload: 'https://example.com',
    );

    expect(effectiveHistoryVerdict(scan), Verdict.warning);
  });

  test('partial scan never downgrades an explicit Blocked verdict', () {
    final scan = ScanResponse(
      verdict: Verdict.blocked,
      riskScore: 55,
      reasons: const ['Executable QR payload is not safe to open'],
      payloadType: 'text',
      branchScores: const BranchScores(pStructural: 0.1, pUrl: null),
      partialAnalysis: true,
      deepCheckAvailable: false,
      payload: 'javascript:alert(1)',
    );

    expect(effectiveHistoryVerdict(scan), Verdict.blocked);
  });

  test(
    'live-camera Structural and Semantic evidence is preserved in history',
    () {
      final scan = ScanResponse(
        verdict: Verdict.blocked,
        riskScore: 83,
        reasons: const ['QR image appears manipulated'],
        payloadType: 'url',
        registeredDomain: 'google.com',
        branchScores: const BranchScores(
          pStructural: 0.85,
          pStructuralRaw: 0.85,
          structuralType: 'adversarial',
          pUrl: 0.01,
          domainUnknown: 0,
          structuralStatus: AnalysisStatus.completed,
          semanticStatus: AnalysisStatus.completed,
          imageSource: 'camera',
        ),
        payload: 'https://www.google.com/maps',
      );
      final snapshot = HistoryService.snapshotForStorage(scan);
      final record = ScanRecord(
        id: 111,
        payloadHash: HistoryService.hashPayload(scan.payload!),
        registeredDomain: scan.registeredDomain,
        verdict: effectiveHistoryVerdict(scan).name,
        riskScore: scan.riskScore,
        scannedAt: DateTime(2026, 8, 24),
        analysisSnapshot: snapshot,
      );

      expect(record.storedAnalysis?.branchScores.pStructural, 0.85);
      expect(record.storedAnalysis?.branchScores.pUrl, 0.01);
      expect(record.storedAnalysis?.riskScore, 83);
      expect(record.storedAnalysis?.reasons, ['QR image appears adversarial']);
    },
  );

  test(
    'history snapshot restores evidence without storing the raw payload',
    () {
      const rawPayload = 'https://example.com/private/path?token=secret';
      final scan = ScanResponse(
        verdict: Verdict.warning,
        riskScore: 48,
        reasons: const ['Free-text reason that must not be stored'],
        payloadType: 'url',
        registeredDomain: 'example.com',
        ruleFlags: const ['non_https'],
        branchScores: const BranchScores(
          pStructural: 0.08,
          pUrl: 0.61,
          structuralStatus: AnalysisStatus.completed,
          semanticStatus: AnalysisStatus.completed,
          structuralType: 'clean',
          imageSource: 'gallery',
        ),
        payload: rawPayload,
        elapsedMs: 74,
      );
      final snapshot = HistoryService.snapshotForStorage(scan);
      final record = ScanRecord(
        id: 8,
        payloadHash: HistoryService.hashPayload(rawPayload),
        registeredDomain: 'example.com',
        verdict: 'warning',
        riskScore: 48,
        scannedAt: DateTime(2026, 8, 23),
        analysisSnapshot: snapshot,
      );

      expect(snapshot, isNot(contains(rawPayload)));
      expect(snapshot, isNot(contains('token=secret')));
      expect(snapshot, isNot(contains('Free-text reason')));
      expect(record.storedAnalysis?.branchScores.pUrl, 0.61);
      expect(
        record.storedAnalysis?.branchScores.semanticStatus,
        AnalysisStatus.completed,
      );
    },
  );

  testWidgets('clicking a history tile opens the stored result summary', (
    tester,
  ) async {
    final record = records[1];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(Brightness.dark),
        home: Scaffold(body: ScanHistoryTile(record: record)),
      ),
    );

    await tester.tap(find.text('xn--pypal-4ve.com'));
    await tester.pumpAndSettle();

    expect(find.text('Recent scan'), findsOneWidget);
    expect(find.text('Warning'), findsOneWidget);
    expect(find.text('Risk score 44 / 100'), findsOneWidget);
    expect(find.text('Why this needs caution'), findsOneWidget);
    expect(
      find.textContaining('saved Structural, Semantic and Risk'),
      findsOneWidget,
    );
    await tester.ensureVisible(find.text('Privacy details'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Privacy details'));
    await tester.pumpAndSettle();
    expect(find.text(record.payloadHash), findsOneWidget);
    expect(find.textContaining('raw URL'), findsOneWidget);
  });

  testWidgets('stored summary wording matches each recorded verdict', (
    tester,
  ) async {
    final expectedTitles = {
      'safe': 'Why this was marked Safe',
      'warning': 'Why this needs caution',
      'blocked': 'Why this was Blocked',
    };

    for (final record in records) {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(Brightness.dark),
          home: HistoryRecordScreen(record: record),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(expectedTitles[record.verdict]!), findsOneWidget);
      expect(find.textContaining('A familiar domain'), findsNothing);
    }
  });

  testWidgets(
    'Recent scan shows saved branch evidence and keeps scan metadata',
    (tester) async {
      tester.view.physicalSize = const Size(900, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final scan = ScanResponse(
        verdict: Verdict.blocked,
        riskScore: 83,
        reasons: const ['QR image appears manipulated'],
        payloadType: 'url',
        registeredDomain: 'google.com',
        branchScores: const BranchScores(
          pStructural: 0.85,
          pStructuralRaw: 0.85,
          structuralType: 'adversarial',
          pUrl: 0.01,
          domainUnknown: 0,
          structuralStatus: AnalysisStatus.completed,
          semanticStatus: AnalysisStatus.completed,
          imageSource: 'camera',
        ),
        payload: 'https://www.google.com/maps',
        elapsedMs: 28,
      );
      final record = ScanRecord(
        id: 111,
        payloadHash: HistoryService.hashPayload(scan.payload!),
        registeredDomain: scan.registeredDomain,
        verdict: 'blocked',
        riskScore: 83,
        scannedAt: DateTime(2026, 8, 24, 1, 8, 2),
        analysisSnapshot: HistoryService.snapshotForStorage(scan),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(Brightness.dark),
          home: HistoryRecordScreen(record: record),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Recent scan'), findsOneWidget);
      expect(find.text('Structural'), findsOneWidget);
      expect(find.text('adversarial'), findsOneWidget);
      expect(find.text('0.85'), findsOneWidget);
      expect(find.text('Semantic'), findsOneWidget);
      expect(find.text('0.01'), findsOneWidget);
      expect(find.text('83'), findsOneWidget);
      expect(find.text('google.com'), findsOneWidget);
      expect(find.text('History record'), findsOneWidget);
      expect(find.text('111'), findsOneWidget);
    },
  );
}
