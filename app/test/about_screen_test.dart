import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/screens/about_screen.dart';
import 'package:qrguard/theme.dart';

void main() {
  testWidgets('discloses r07 controlled-release safety boundaries', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(900, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(Brightness.dark),
        home: const AboutScreen(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('1.2.0 (8012)'), findsOneWidget);
    expect(find.text('r07 controlled release'), findsOneWidget);
    expect(find.text('Safety boundaries'), findsOneWidget);
    expect(
      find.textContaining('returns Rescan instead of Safe'),
      findsOneWidget,
    );
    expect(
      find.textContaining(
        'fresh independent blind promotion test remains pending',
      ),
      findsOneWidget,
    );
  });
}
