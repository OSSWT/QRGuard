/// QRGuard's warm signal-analysis visual language.
library;

import 'package:flutter/material.dart';

import 'models/scan_response.dart';

@immutable
class QRGuardColors extends ThemeExtension<QRGuardColors> {
  const QRGuardColors({
    required this.background,
    required this.surface,
    required this.secondarySurface,
    required this.elevatedSurface,
    required this.primaryText,
    required this.secondaryText,
    required this.border,
    required this.brand,
    required this.brandInk,
    required this.signalLight,
    required this.focal,
    required this.mutedStructure,
    required this.morse,
    required this.morseOpacity,
    required this.safe,
    required this.warning,
    required this.blocked,
    required this.safeSurface,
    required this.warningSurface,
    required this.blockedSurface,
  });

  final Color background;
  final Color surface;
  final Color secondarySurface;
  final Color elevatedSurface;
  final Color primaryText;
  final Color secondaryText;
  final Color border;
  final Color brand;
  final Color brandInk;
  final Color signalLight;
  final Color focal;
  final Color mutedStructure;
  final Color morse;
  final double morseOpacity;
  final Color safe;
  final Color warning;
  final Color blocked;
  final Color safeSurface;
  final Color warningSurface;
  final Color blockedSurface;

  static const dark = QRGuardColors(
    background: Color(0xFF100D0B),
    surface: Color(0xFF1A1613),
    secondarySurface: Color(0xFF211B17),
    elevatedSurface: Color(0xFF2B221C),
    primaryText: Color(0xFFF8EEE7),
    secondaryText: Color(0xFFAE9D91),
    border: Color(0xFF49392E),
    brand: Color(0xFFE59A63),
    brandInk: Color(0xFFE59A63),
    signalLight: Color(0xFFFFD0A8),
    focal: Color(0xFFFFF0DF),
    mutedStructure: Color(0xFF72513A),
    morse: Color(0xFFF0A46E),
    morseOpacity: 0.27,
    safe: Color(0xFF67D38A),
    warning: Color(0xFFF2C94C),
    blocked: Color(0xFFFF6B6B),
    safeSurface: Color(0xFF17231B),
    warningSurface: Color(0xFF2B2414),
    blockedSurface: Color(0xFF2A1715),
  );

  static const light = QRGuardColors(
    background: Color(0xFFF7EFE7),
    surface: Color(0xFFFFFAF5),
    secondarySurface: Color(0xFFF2E5D9),
    elevatedSurface: Color(0xFFE8D6C7),
    primaryText: Color(0xFF2D211A),
    secondaryText: Color(0xFF756156),
    border: Color(0xFFD1B9A7),
    brand: Color(0xFFE59A63),
    brandInk: Color(0xFF9B572D),
    signalLight: Color(0xFFFFD0A8),
    focal: Color(0xFFFFF0DF),
    mutedStructure: Color(0xFF72513A),
    morse: Color(0xFFA95E32),
    morseOpacity: 0.21,
    safe: Color(0xFF1E7A42),
    warning: Color(0xFF8A5A00),
    blocked: Color(0xFFB3261E),
    safeSurface: Color(0xFFE7F4EA),
    warningSurface: Color(0xFFFFF4CD),
    blockedSurface: Color(0xFFFCE8E6),
  );

  @override
  QRGuardColors copyWith({double? morseOpacity}) => QRGuardColors(
    background: background,
    surface: surface,
    secondarySurface: secondarySurface,
    elevatedSurface: elevatedSurface,
    primaryText: primaryText,
    secondaryText: secondaryText,
    border: border,
    brand: brand,
    brandInk: brandInk,
    signalLight: signalLight,
    focal: focal,
    mutedStructure: mutedStructure,
    morse: morse,
    morseOpacity: morseOpacity ?? this.morseOpacity,
    safe: safe,
    warning: warning,
    blocked: blocked,
    safeSurface: safeSurface,
    warningSurface: warningSurface,
    blockedSurface: blockedSurface,
  );

  @override
  QRGuardColors lerp(covariant QRGuardColors? other, double t) {
    if (other == null) return this;
    return QRGuardColors(
      background: Color.lerp(background, other.background, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      secondarySurface: Color.lerp(
        secondarySurface,
        other.secondarySurface,
        t,
      )!,
      elevatedSurface: Color.lerp(elevatedSurface, other.elevatedSurface, t)!,
      primaryText: Color.lerp(primaryText, other.primaryText, t)!,
      secondaryText: Color.lerp(secondaryText, other.secondaryText, t)!,
      border: Color.lerp(border, other.border, t)!,
      brand: Color.lerp(brand, other.brand, t)!,
      brandInk: Color.lerp(brandInk, other.brandInk, t)!,
      signalLight: Color.lerp(signalLight, other.signalLight, t)!,
      focal: Color.lerp(focal, other.focal, t)!,
      mutedStructure: Color.lerp(mutedStructure, other.mutedStructure, t)!,
      morse: Color.lerp(morse, other.morse, t)!,
      morseOpacity: morseOpacity + (other.morseOpacity - morseOpacity) * t,
      safe: Color.lerp(safe, other.safe, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      blocked: Color.lerp(blocked, other.blocked, t)!,
      safeSurface: Color.lerp(safeSurface, other.safeSurface, t)!,
      warningSurface: Color.lerp(warningSurface, other.warningSurface, t)!,
      blockedSurface: Color.lerp(blockedSurface, other.blockedSurface, t)!,
    );
  }
}

extension QRGuardThemeContext on BuildContext {
  QRGuardColors get qrColors => Theme.of(this).extension<QRGuardColors>()!;
}

class VerdictStyle {
  final Color color;
  final Color surface;
  final IconData icon;
  final String label;
  final String headline;

  const VerdictStyle({
    required this.color,
    required this.surface,
    required this.icon,
    required this.label,
    required this.headline,
  });

  static VerdictStyle of(BuildContext context, Verdict verdict) {
    final colors = context.qrColors;
    return switch (verdict) {
      Verdict.safe => VerdictStyle(
        color: colors.safe,
        surface: colors.safeSurface,
        icon: Icons.check_circle_outline_rounded,
        label: 'Safe',
        headline: 'No elevated risk indicators found',
      ),
      Verdict.warning => VerdictStyle(
        color: colors.warning,
        surface: colors.warningSurface,
        icon: Icons.warning_amber_rounded,
        label: 'Warning',
        headline: 'Review this destination carefully',
      ),
      Verdict.blocked => VerdictStyle(
        color: colors.blocked,
        surface: colors.blockedSurface,
        icon: Icons.dangerous_outlined,
        label: 'Blocked',
        headline: 'QRGuard recommends that you do not open this destination',
      ),
    };
  }

  static VerdictStyle partial(BuildContext context) {
    final colors = context.qrColors;
    return VerdictStyle(
      color: colors.warning,
      surface: colors.warningSurface,
      icon: Icons.info_outline_rounded,
      label: 'Partial analysis',
      headline: 'One analysis branch was unavailable',
    );
  }
}

ThemeData buildTheme(Brightness brightness, {bool enhancedContrast = false}) {
  final base = brightness == Brightness.dark
      ? QRGuardColors.dark
      : QRGuardColors.light;
  final colors = enhancedContrast
      ? base.copyWith(morseOpacity: brightness == Brightness.dark ? 0.31 : 0.25)
      : base;
  final scheme =
      ColorScheme.fromSeed(
        seedColor: colors.brand,
        brightness: brightness,
        surface: colors.surface,
        error: colors.blocked,
      ).copyWith(
        primary: colors.brand,
        onPrimary: const Color(0xFF11100F),
        surface: colors.surface,
        onSurface: colors.primaryText,
        outline: colors.border,
        error: colors.blocked,
      );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: Colors.transparent,
    extensions: [colors],
    textTheme: ThemeData(brightness: brightness).textTheme.apply(
      bodyColor: colors.primaryText,
      displayColor: colors.primaryText,
    ),
    appBarTheme: AppBarTheme(
      centerTitle: false,
      elevation: 0,
      scrolledUnderElevation: 0,
      backgroundColor: Colors.transparent,
      foregroundColor: colors.primaryText,
      titleTextStyle: TextStyle(
        color: colors.primaryText,
        fontSize: 18,
        fontWeight: FontWeight.w700,
      ),
    ),
    cardTheme: CardThemeData(
      color: colors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: colors.border,
          width: enhancedContrast ? 1.5 : 1,
        ),
      ),
    ),
    dividerTheme: DividerThemeData(color: colors.border),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        backgroundColor: colors.brand,
        foregroundColor: const Color(0xFF11100F),
        disabledBackgroundColor: colors.mutedStructure,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        foregroundColor: colors.brandInk,
        side: BorderSide(color: colors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: colors.secondarySurface,
      labelStyle: TextStyle(color: colors.secondaryText),
      hintStyle: TextStyle(color: colors.secondaryText),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: colors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: colors.border),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: colors.elevatedSurface,
      contentTextStyle: TextStyle(color: colors.primaryText),
      behavior: SnackBarBehavior.floating,
    ),
  );
}
