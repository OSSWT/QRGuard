/// Persisted local preferences.
///
/// Nothing in this service implies an online account. The profile, appearance and
/// accessibility values stay on this device, alongside the configurable backend URL.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsService {
  static const _backendUrlKey = 'backend_url';
  static const _themeKey = 'theme_mode';
  static const _reduceMotionKey = 'reduce_motion';
  static const _enhancedContrastKey = 'enhanced_contrast';
  static const _saveHistoryKey = 'save_history';
  static const _displayNameKey = 'profile_display_name';
  static const _roleKey = 'profile_role';
  static const _institutionKey = 'profile_institution';

  /// Release builds receive the production HTTPS endpoint with:
  /// `--dart-define=QRGUARD_BACKEND_URL=https://...run.app`.
  /// Development keeps the browser/emulator loopback defaults.
  static const _configuredBackendUrl = String.fromEnvironment(
    'QRGUARD_BACKEND_URL',
  );
  static const defaultBackendUrl = _configuredBackendUrl != ''
      ? _configuredBackendUrl
      : kIsWeb
      ? 'http://127.0.0.1:8001'
      : 'http://10.0.2.2:8001';

  static const _legacyDefaultUrls = {
    'http://127.0.0.1:8000',
    'http://10.0.2.2:8000',
  };

  Future<String> backendUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_backendUrlKey);
    if (stored == null) return defaultBackendUrl;
    // These were QRGuard's old built-in defaults, not LAN addresses entered by
    // the user. Migrate only these exact values so app and run_server.py agree.
    if (_legacyDefaultUrls.contains(stored)) {
      await prefs.setString(_backendUrlKey, defaultBackendUrl);
      return defaultBackendUrl;
    }
    return stored;
  }

  Future<void> setBackendUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_backendUrlKey, normalise(url));
  }

  Future<AppPreferences> preferences() async {
    final prefs = await SharedPreferences.getInstance();
    return AppPreferences(
      theme: prefs.getString(_themeKey) == 'light'
          ? AppThemePreference.light
          : AppThemePreference.dark,
      reduceMotion: prefs.getBool(_reduceMotionKey) ?? false,
      enhancedContrast: prefs.getBool(_enhancedContrastKey) ?? false,
      saveHistory: prefs.getBool(_saveHistoryKey) ?? true,
      profile: LocalProfile(
        displayName: prefs.getString(_displayNameKey) ?? 'QRGuard User',
        role: prefs.getString(_roleKey) ?? 'Student / Researcher',
        institution: prefs.getString(_institutionKey) ?? '',
      ),
    );
  }

  Future<void> setTheme(AppThemePreference value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themeKey, value.name);
  }

  Future<void> setReduceMotion(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_reduceMotionKey, value);
  }

  Future<void> setEnhancedContrast(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_enhancedContrastKey, value);
  }

  Future<void> setSaveHistory(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_saveHistoryKey, value);
  }

  Future<void> setProfile(LocalProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.setString(_displayNameKey, profile.displayName.trim()),
      prefs.setString(_roleKey, profile.role.trim()),
      prefs.setString(_institutionKey, profile.institution.trim()),
    ]);
  }

  /// Accepts "192.168.1.5", "192.168.1.5:8001" or a full URL and returns a usable base.
  static String normalise(String input) {
    return tryNormalise(input) ?? defaultBackendUrl;
  }

  /// Validate without silently replacing bad user input with the development default.
  static String? tryNormalise(String input) {
    var value = input.trim().replaceAll(RegExp(r'/+$'), '');
    if (value.isEmpty) return null;
    if (RegExp(r'\s').hasMatch(value)) return null;
    final suppliedScheme =
        value.startsWith('http://') || value.startsWith('https://');
    if (!suppliedScheme) {
      value = 'http://$value';
    }
    try {
      final uri = Uri.tryParse(value);
      if (uri == null ||
          uri.host.isEmpty ||
          !const {'http', 'https'}.contains(uri.scheme)) {
        return null;
      }
      // A full production HTTPS URL uses its standard port. Bare development
      // hosts retain QRGuard's local backend port for convenience.
      return uri.hasPort || suppliedScheme ? value : '$value:8001';
    } on FormatException {
      return null;
    }
  }
}

enum AppThemePreference { dark, light }

class LocalProfile {
  final String displayName;
  final String role;
  final String institution;

  const LocalProfile({
    required this.displayName,
    required this.role,
    required this.institution,
  });

  String get initials {
    final words = displayName
        .trim()
        .split(RegExp(r'\s+'))
        .where((word) => word.isNotEmpty)
        .take(2);
    final value = words.map((word) => word[0].toUpperCase()).join();
    return value.isEmpty ? 'QG' : value;
  }
}

class AppPreferences {
  final AppThemePreference theme;
  final bool reduceMotion;
  final bool enhancedContrast;
  final bool saveHistory;
  final LocalProfile profile;

  const AppPreferences({
    required this.theme,
    required this.reduceMotion,
    required this.enhancedContrast,
    required this.saveHistory,
    required this.profile,
  });
}
