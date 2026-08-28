import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/app_controller.dart';
import 'package:qrguard/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test(
    'defaults to Dark Mode with privacy-preserving history enabled',
    () async {
      final controller = AppController(SettingsService());
      await controller.load();

      expect(controller.theme, AppThemePreference.dark);
      expect(controller.saveHistory, isTrue);
      expect(controller.reduceMotion, isFalse);
      expect(controller.profile.displayName, 'QRGuard User');
    },
  );

  test(
    'persists appearance, accessibility and local profile preferences',
    () async {
      final controller = AppController(SettingsService());
      await controller.load();
      await controller.setTheme(AppThemePreference.light);
      await controller.setReduceMotion(true);
      await controller.setEnhancedContrast(true);
      await controller.setSaveHistory(false);
      await controller.setProfile(
        const LocalProfile(
          displayName: 'Amina Researcher',
          role: 'Academic',
          institution: 'UTAR',
        ),
      );

      final reloaded = AppController(SettingsService());
      await reloaded.load();
      expect(reloaded.theme, AppThemePreference.light);
      expect(reloaded.reduceMotion, isTrue);
      expect(reloaded.enhancedContrast, isTrue);
      expect(reloaded.saveHistory, isFalse);
      expect(reloaded.profile.displayName, 'Amina Researcher');
      expect(reloaded.profile.initials, 'AR');
      expect(reloaded.profile.institution, 'UTAR');
    },
  );

  test('strict URL validation does not silently replace invalid input', () {
    expect(SettingsService.tryNormalise('not a url'), isNull);
    expect(
      SettingsService.tryNormalise('10.0.2.2:8001'),
      'http://10.0.2.2:8001',
    );
  });

  test('migrates only QRGuard legacy backend defaults to port 8001', () async {
    SharedPreferences.setMockInitialValues({
      'backend_url': 'http://10.0.2.2:8000',
    });
    expect(
      await SettingsService().backendUrl(),
      SettingsService.defaultBackendUrl,
    );

    SharedPreferences.setMockInitialValues({
      'backend_url': 'http://192.168.1.44:8000',
    });
    expect(await SettingsService().backendUrl(), 'http://192.168.1.44:8000');
  });
}
