/// App-wide local state with no external state-management dependency.
library;

import 'package:flutter/foundation.dart';

import 'services/settings_service.dart';

class AppController extends ChangeNotifier {
  AppController(this.settings);

  final SettingsService settings;

  AppThemePreference theme = AppThemePreference.dark;
  bool reduceMotion = false;
  bool enhancedContrast = false;
  bool saveHistory = true;
  LocalProfile profile = const LocalProfile(
    displayName: 'QRGuard User',
    role: 'Student / Researcher',
    institution: '',
  );

  Future<void> load() async {
    final preferences = await settings.preferences();
    theme = preferences.theme;
    reduceMotion = preferences.reduceMotion;
    enhancedContrast = preferences.enhancedContrast;
    saveHistory = preferences.saveHistory;
    profile = preferences.profile;
    notifyListeners();
  }

  Future<void> setTheme(AppThemePreference value) async {
    if (theme == value) return;
    theme = value;
    notifyListeners();
    await settings.setTheme(value);
  }

  Future<void> setReduceMotion(bool value) async {
    if (reduceMotion == value) return;
    reduceMotion = value;
    notifyListeners();
    await settings.setReduceMotion(value);
  }

  Future<void> setEnhancedContrast(bool value) async {
    if (enhancedContrast == value) return;
    enhancedContrast = value;
    notifyListeners();
    await settings.setEnhancedContrast(value);
  }

  Future<void> setSaveHistory(bool value) async {
    if (saveHistory == value) return;
    saveHistory = value;
    notifyListeners();
    await settings.setSaveHistory(value);
  }

  Future<void> setProfile(LocalProfile value) async {
    profile = value;
    notifyListeners();
    await settings.setProfile(value);
  }
}
