/// QRGuard — real-time QR code fraud detection.
library;

import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'screens/home_screen.dart';
import 'services/settings_service.dart';
import 'theme.dart';
import 'widgets/morse_signal_background.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController(SettingsService());
  await controller.load();
  runApp(QRGuardApp(controller: controller));
}

class QRGuardApp extends StatelessWidget {
  const QRGuardApp({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => MaterialApp(
      title: 'QRGuard',
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
      home: HomeScreen(appController: controller),
    ),
  );
}
