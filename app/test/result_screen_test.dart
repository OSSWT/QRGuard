import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/screens/result_screen.dart';
import 'package:qrguard/services/api_client.dart';
import 'package:qrguard/theme.dart';

void main() {
  late ApiClient api;

  setUp(() => api = ApiClient(baseUrl: 'http://127.0.0.1:8001'));
  tearDown(() => api.dispose());

  Future<void> pumpResult(WidgetTester tester, ScanResponse scan) async {
    tester.view.physicalSize = const Size(900, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(Brightness.dark),
        home: ResultScreen(scan: scan, api: api),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Safe exposes explicit URL proceed and user-initiated Deep Check',
    (tester) async {
      await pumpResult(tester, _scan(verdict: Verdict.safe, risk: 12));

      expect(find.text('Safe'), findsOneWidget);
      expect(find.text('Proceed to URL'), findsOneWidget);
      expect(find.text('Check this link in depth'), findsOneWidget);
      expect(find.text('Registered domain: example.com'), findsOneWidget);
      expect(find.text('Why this looks safe'), findsOneWidget);
      expect(
        find.textContaining('found no strong risk indicators'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Warning summarises the strongest signal without a long list', (
    tester,
  ) async {
    await pumpResult(tester, _scan(verdict: Verdict.warning, risk: 43));

    expect(find.text('Why caution is needed'), findsOneWidget);
    expect(
      find.textContaining('Destination link matches phishing patterns'),
      findsOneWidget,
    );
    expect(find.text('Go Back'), findsOneWidget);
    expect(find.text('Details'), findsOneWidget);
  });

  testWidgets('live-camera adversarial score is used without consensus UI', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.blocked,
        risk: 83,
        pStructural: 0.85,
        pStructuralRaw: 0.85,
        structuralType: 'adversarial',
        imageSource: 'camera',
        pUrl: 0.01,
        reasons: const ['QR image appears adversarial'],
      ),
    );

    expect(find.text('Blocked'), findsOneWidget);
    expect(find.textContaining('QR image appears adversarial'), findsOneWidget);

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(find.text('0.85'), findsOneWidget);
    expect(find.text('adversarial'), findsOneWidget);
    expect(find.text('Camera frames'), findsNothing);
    expect(find.textContaining('inconclusive'), findsNothing);
  });

  testWidgets('Partial analysis fails closed visually and functionally', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(verdict: Verdict.safe, risk: 8, partial: true),
    );

    expect(find.text('Partial analysis'), findsOneWidget);
    expect(find.text('Go Back'), findsOneWidget);
    expect(find.text('Proceed to URL'), findsNothing);

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(find.text('Unavailable'), findsOneWidget);
  });

  testWidgets('live-camera clean QR remains Safe without consensus UI', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.safe,
        risk: 2,
        pStructural: 0.01,
        pStructuralRaw: 0.01,
        structuralType: 'clean',
        imageSource: 'camera',
        pUrl: 0.01,
      ),
    );

    expect(find.text('Safe'), findsOneWidget);
    expect(find.text('Partial analysis'), findsNothing);
    expect(find.text('Proceed to URL'), findsOneWidget);
    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(find.text('clean'), findsOneWidget);
    expect(find.text('Camera frames'), findsNothing);
    expect(find.textContaining('inconclusive'), findsNothing);
  });

  testWidgets('live-camera details disclose the five-frame consensus', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.safe,
        risk: 3,
        pStructural: 0.02,
        structuralType: 'clean',
        imageSource: 'camera',
        structuralFramesReceived: 5,
        structuralFramesAnalyzed: 5,
        structuralConsensus: 'median_score_majority_class',
      ),
    );

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(find.text('clean · 5-frame consensus'), findsOneWidget);
  });

  testWidgets('Blocked URL requires the separate acknowledgement step', (
    tester,
  ) async {
    await pumpResult(tester, _scan(verdict: Verdict.blocked, risk: 91));

    expect(find.text('Why this was blocked'), findsOneWidget);
    expect(find.textContaining('strong risk indicators'), findsOneWidget);

    final overrideElement = find
        .byKey(const ValueKey('blocked_override'))
        .evaluate()
        .first;
    await Scrollable.ensureVisible(overrideElement);
    await tester.pumpAndSettle();
    await tester.tap(find.byWidget(overrideElement.widget));
    await tester.pumpAndSettle();

    expect(find.text('This destination is blocked'), findsOneWidget);
    expect(find.text('Do not proceed'), findsOneWidget);
    expect(find.text('I understand — proceed anyway'), findsOneWidget);
  });

  testWidgets('Blocked summary names the decoy, actual domain and top risks', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.blocked,
        risk: 100,
        payload: 'http://www.paypal.com@evil-site.tk/login',
        registeredDomain: 'evil-site.tk',
        pUrl: 0.99,
        ruleFlags: const ['non_https', 'suspicious_tld', 'userinfo_in_url'],
        reasons: const [
          'Domain uses a frequently-abused extension',
          'Destination link matches phishing patterns',
          'Destination is not a widely-recognised website',
          'Destination does not use HTTPS encryption',
          'Domain uses frequently-abused TLD (.tk)',
          "URL contains '@' before the host — the part before it is a decoy",
        ],
      ),
    );

    expect(find.textContaining('“www.paypal.com”'), findsOneWidget);
    expect(
      find.textContaining('actual domain is “evil-site.tk”'),
      findsOneWidget,
    );
    expect(find.textContaining('phishing score (0.99)'), findsOneWidget);
    expect(
      find.textContaining('frequently abused .tk extension'),
      findsOneWidget,
    );

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(
      find.text('Domain uses a frequently-abused extension'),
      findsNothing,
    );
    expect(
      find.text('Domain uses frequently-abused TLD (.tk)'),
      findsOneWidget,
    );
  });

  testWidgets('Partial evidence never downgrades a Blocked verdict', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(verdict: Verdict.blocked, risk: 55, partial: true),
    );

    expect(find.text('Blocked'), findsOneWidget);
    expect(find.text('Partial analysis'), findsNothing);
    expect(find.byKey(const ValueKey('blocked_override')), findsOneWidget);
  });

  testWidgets('valid DuitNow QR shows recipient details and TNG hand-off', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.safe,
        risk: 12,
        payloadType: 'text',
        payload:
            '00020201021126410014A000000615000101065016640209123456789'
            '520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23',
      ),
    );

    expect(find.text('DuitNow payment QR'), findsOneWidget);
    expect(find.text('AUSERNAME'), findsOneWidget);
    expect(find.text('MYR 10.00'), findsOneWidget);
    expect(find.text('Open TNG eWallet'), findsOneWidget);
  });

  testWidgets('hi-hive attendance QR offers official-app hand-off', (
    tester,
  ) async {
    const token =
        'Q01:*:PACkNWVoPGvQQJ0Htc32cjZdTi+na5wHs0CB9rCOeg34g41pKQdYzMgrwZOV'
        'qjZeYyQ4SLPlONzsyH+m6fku+yLQK1V/jFB4cQJp85G0JgI=';
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.warning,
        risk: 45,
        payloadType: 'attendance',
        payload: token,
        reasons: const [
          'Recognised hi-hive attendance format; verify it in the official app',
        ],
      ),
    );

    expect(find.text('hi-hive attendance QR'), findsOneWidget);
    expect(find.text('Open hi-hive to scan again'), findsOneWidget);
    expect(find.textContaining('PACkNWVo'), findsNothing);
  });

  testWidgets('Wi-Fi QR is a complete non-URL result, not Partial', (
    tester,
  ) async {
    await pumpResult(
      tester,
      _scan(
        verdict: Verdict.safe,
        risk: 4,
        payloadType: 'wifi',
        payload: 'WIFI:T:WPA;S:QRGuard Lab;P:example123;;',
      ),
    );

    expect(find.text('Safe'), findsOneWidget);
    expect(find.textContaining('Partial analysis'), findsNothing);
    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();
    expect(find.text('Not applicable · Wi-Fi QR'), findsOneWidget);
    expect(find.text('Unavailable'), findsNothing);
  });
}

ScanResponse _scan({
  required Verdict verdict,
  required int risk,
  bool partial = false,
  String payloadType = 'url',
  String payload = 'https://example.com/expanded/path',
  String? registeredDomain,
  double pUrl = 0.11,
  List<String>? reasons,
  List<String> ruleFlags = const [],
  double? pStructural,
  double? pStructuralRaw,
  String? structuralType,
  String imageSource = 'unknown',
  int structuralFramesReceived = 0,
  int structuralFramesAnalyzed = 0,
  String? structuralConsensus,
}) => ScanResponse(
  verdict: verdict,
  riskScore: risk,
  reasons:
      reasons ??
      (verdict == Verdict.safe
          ? const []
          : const ['Destination link matches phishing patterns']),
  payloadType: payloadType,
  normalizedUrl: payloadType == 'url' ? payload : null,
  registeredDomain: payloadType == 'url'
      ? (registeredDomain ?? 'example.com')
      : null,
  ruleFlags: ruleFlags,
  branchScores: BranchScores(
    pStructural: partial ? null : (pStructural ?? 0.08),
    pStructuralRaw: partial ? null : pStructuralRaw,
    structuralType: partial ? null : (structuralType ?? 'clean'),
    pUrl: payloadType == 'url' ? pUrl : null,
    domainUnknown: 0,
    structuralStatus: partial
        ? AnalysisStatus.unavailable
        : AnalysisStatus.completed,
    semanticStatus: payloadType == 'url'
        ? AnalysisStatus.completed
        : AnalysisStatus.notApplicable,
    imageSource: imageSource,
    structuralFramesReceived: structuralFramesReceived,
    structuralFramesAnalyzed: structuralFramesAnalyzed,
    structuralConsensus: structuralConsensus,
  ),
  partialAnalysis: partial,
  deepCheckAvailable: false,
  payload: payload,
  elapsedMs: 333,
);
