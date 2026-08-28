import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image/image.dart' as img;
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/screens/analysing_screen.dart';
import 'package:qrguard/services/api_client.dart';
import 'package:qrguard/services/history_service.dart';
import 'package:qrguard/theme.dart';

void main() {
  test('crop preparation falls back to the next valid camera frame', () {
    final frame = img.Image(width: 320, height: 240);
    img.fill(frame, color: img.ColorRgb8(235, 235, 235));
    img.fillRect(
      frame,
      x1: 90,
      y1: 50,
      x2: 209,
      y2: 169,
      color: img.ColorRgb8(20, 20, 20),
    );
    final crop = prepareFirstUsableCropInBackground([
      CropRequest(
        frame: Uint8List.fromList([1, 2, 3]),
        cornerCoordinates: const [90, 50, 210, 50, 210, 170, 90, 170],
        frameWidth: 320,
        frameHeight: 240,
        normalizeCameraColor: true,
      ),
      CropRequest(
        frame: Uint8List.fromList(img.encodeJpg(frame, quality: 85)),
        cornerCoordinates: const [90, 50, 210, 50, 210, 170, 90, 170],
        frameWidth: 320,
        frameHeight: 240,
        normalizeCameraColor: true,
      ),
    ]);

    expect(crop, isNotNull);
    expect(img.decodeImage(crop!), isNotNull);
  });

  testWidgets('camera scan without valid image asks for a rescan', (
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
          imageSource: 'camera',
        ),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));

    expect(api.calls, 0);
    expect(
      find.textContaining('could not prepare a valid camera image'),
      findsOneWidget,
    );
    expect(find.text('Back to Scanner'), findsOneWidget);
    api.dispose();
  });

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
    expect(find.textContaining('waking after an idle period'), findsOneWidget);
    expect(find.textContaining('http://10.0.2.2:8001'), findsNothing);
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
