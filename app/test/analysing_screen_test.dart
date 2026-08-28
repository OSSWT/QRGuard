import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/screens/analysing_screen.dart';
import 'package:qrguard/services/api_client.dart';
import 'package:qrguard/services/history_service.dart';
import 'package:qrguard/theme.dart';

void main() {
  testWidgets('screen timeout replaces the spinner with recovery UI', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(900, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = _TimesOutApi();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(Brightness.dark),
        home: AnalysingScreen(
          api: api,
          history: HistoryService(),
          saveHistory: false,
          payload: 'https://example.com',
        ),
      ),
    );

    await tester.pump();
    expect(api.calls, 1);
    await tester.pump();

    expect(find.textContaining('did not respond in time'), findsOneWidget);
    expect(find.textContaining('http://10.0.2.2:8001'), findsOneWidget);
    expect(find.text('Try Again'), findsOneWidget);
    expect(find.text('Back to Scanner'), findsOneWidget);
    api.dispose();
  });
}

class _TimesOutApi extends ApiClient {
  _TimesOutApi()
    : super(
        baseUrl: 'http://10.0.2.2:8001',
        client: MockClient((_) async => http.Response('{}', 200)),
      );

  int calls = 0;

  @override
  Future<ScanResponse> scan({
    String? payload,
    Uint8List? imageBytes,
    String imageSource = 'unknown',
  }) {
    calls++;
    return Future<ScanResponse>.error(TimeoutException('test timeout'));
  }
}
