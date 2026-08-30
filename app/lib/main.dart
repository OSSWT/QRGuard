/// QRGuard — real-time QR code fraud detection.
library;

import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'screens/home_screen.dart';
import 'screens/offline_capture_screen.dart';
import 'services/offline_capture_service.dart';
import 'services/settings_service.dart';
import 'theme.dart';
import 'widgets/morse_signal_background.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController(SettingsService());
  await controller.load();
  final offlineCapture = offlineCaptureEnabled
      ? await OfflineCaptureService.open()
      : null;
  runApp(QRGuardApp(controller: controller, offlineCapture: offlineCapture));
}

class QRGuardApp extends StatelessWidget {
  const QRGuardApp({super.key, required this.controller, this.offlineCapture});

  final AppController controller;
  final OfflineCaptureService? offlineCapture;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => MaterialApp(
      title: offlineCapture == null ? 'QRGuard' : 'QRGuard Offline Capture',
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
      home: offlineCapture == null
          ? HomeScreen(appController: controller)
          : OfflineCaptureScreen(service: offlineCapture!),
    ),
  );
}
