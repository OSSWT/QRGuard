import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/screens/analysing_screen.dart';
import 'package:qrguard/services/api_client.dart';
import 'package:qrguard/services/capture_retry.dart';
import 'package:qrguard/services/history_service.dart';
import 'package:qrguard/services/preview_diagnostics.dart';
import 'package:qrguard/theme.dart';

class _Api extends ApiClient {
  _Api(this.response) : super(baseUrl: 'https://unused.invalid');
  final ScanResponse response;
  int calls = 0;
  @override
  Future<ScanResponse> scan({
    String? payload,
    Uint8List? imageBytes,
    List<Uint8List> additionalImageBytes = const [],
    String imageSource = 'unknown',
  }) async {
    calls++;
    expect(imageBytes, isNotNull);
    expect(additionalImageBytes, hasLength(2));
    return response;
  }
}

void main() {
  for (final verdict in Verdict.values) {
    testWidgets(
      'preview acquisition routing preserves ${verdict.name} outcome',
      (tester) async {
        tester.view.physicalSize = const Size(900, 1600);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final payload = 'Q01:*:${'A' * 128}';
        final response = ScanResponse(
          verdict: verdict,
          riskScore: verdict == Verdict.safe ? 1 : 26,
          reasons: const [],
          payloadType: 'attendance',
          payload: payload,
          partialAnalysis: verdict != Verdict.safe,
          branchScores: BranchScores(
            structuralStatus: verdict == Verdict.safe
                ? AnalysisStatus.completed
                : AnalysisStatus.inconclusive,
          ),
        );
        final api = _Api(response);
        addTearDown(api.dispose);
        final source = img.Image(width: 500, height: 500);
        for (var y = 0; y < 500; y++) {
          for (var x = 0; x < 500; x++) {
            final v = ((x ~/ 12 + y ~/ 12) % 2) == 0 ? 20 : 235;
            source.setPixelRgb(x, y, v, v, v);
          }
        }
        final bytes = Uint8List.fromList(img.encodePng(source, level: 1));
        CaptureRetryRequest? returned;
        await tester.pumpWidget(
          MaterialApp(
            theme: buildTheme(Brightness.dark),
            home: Builder(
              builder: (context) => Scaffold(
                body: TextButton(
                  onPressed: () async {
                    returned = await Navigator.of(context)
                        .push<CaptureRetryRequest>(
                          MaterialPageRoute(
                            builder: (_) => AnalysingScreen(
                              api: api,
                              history: HistoryService(),
                              saveHistory: false,
                              payload: payload,
                              imageSource: 'camera',
                              evidence: [
                                for (var i = 0; i < 3; i++)
                                  QrFrameEvidence(
                                    frame: bytes,
                                    corners: const [
                                      Offset(70, 70),
                                      Offset(420, 70),
                                      Offset(420, 420),
                                      Offset(70, 420),
                                    ],
                                    frameSize: const Size(500, 500),
                                  ),
                              ],
                            ),
                          ),
                        );
                  },
                  child: const Text('Start capture'),
                ),
              ),
            ),
          ),
        );
        await tester.tap(find.text('Start capture'));
        await tester.pump();
        for (var i = 0; i < 20 && api.calls == 0; i++) {
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 100)),
          );
          await tester.pump();
        }
        await tester.pumpAndSettle();
        expect(api.calls, 1);
        if (verdict == Verdict.warning) {
          expect(returned, isA<CaptureRetryRequest>());
          expect(returned!.frames, hasLength(3));
          expect(find.text('Start capture'), findsOneWidget);
          expect(find.text('Rescan needed'), findsNothing);
        } else {
          expect(returned, isNull);
          expect(
            find.text(verdict == Verdict.safe ? 'Safe' : 'Blocked'),
            findsWidgets,
          );
        }
      },
      skip: !diagnosticPreview,
    );
  }
}
