/// QRGuard — real-time QR code fraud detection.
library;

import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'screens/diagnostic_capture_screen.dart';
import 'screens/home_screen.dart';
import 'screens/offline_capture_screen.dart';
import 'services/diagnostic_capture_service.dart';
import 'services/offline_capture_service.dart';
import 'services/settings_service.dart';
import 'theme.dart';
import 'widgets/morse_signal_background.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController(SettingsService());
  await controller.load();
  final diagnosticCapture = diagnosticCaptureEnabled
      ? await DiagnosticCaptureService.open()
      : null;
  final offlineCapture = !diagnosticCaptureEnabled && offlineCaptureEnabled
      ? await OfflineCaptureService.open()
      : null;
  runApp(
    QRGuardApp(
      controller: controller,
      diagnosticCapture: diagnosticCapture,
      offlineCapture: offlineCapture,
    ),
  );
}

class QRGuardApp extends StatelessWidget {
  const QRGuardApp({
    super.key,
    required this.controller,
    this.diagnosticCapture,
    this.offlineCapture,
  });

  final AppController controller;
  final DiagnosticCaptureService? diagnosticCapture;
  final OfflineCaptureService? offlineCapture;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => MaterialApp(
      title: diagnosticCapture != null
          ? 'QRGuard Diagnostic Capture'
          : offlineCapture != null
          ? 'QRGuard Offline Capture'
          : 'QRGuard',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(
        Brightness.light,
        enhancedContrast: controller.enhancedContrast,
      ),
      darkTheme: buildTheme(
        Brightness.dark,
        enhancedContrast: controller.enhancedContrast,
      ),
      themeMode: controller.theme == AppThemePreference.dark
          ? ThemeMode.dark
          : ThemeMode.light,
      builder: (context, child) => MorseSignalBackground(
        reduceMotion: controller.reduceMotion,
        child: child ?? const SizedBox.shrink(),
      ),
      home: diagnosticCapture != null
          ? DiagnosticCaptureScreen(service: diagnosticCapture!)
          : offlineCapture != null
          ? OfflineCaptureScreen(service: offlineCapture!)
          : HomeScreen(appController: controller),
    ),
  );
}
