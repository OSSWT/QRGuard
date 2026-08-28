/// QRGuard settings hub: local profile, appearance and focused app controls.
library;

import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../services/history_service.dart';
import '../services/settings_service.dart';
import '../theme.dart';
import '../widgets/pulse_lens.dart';
import 'about_screen.dart';
import 'accessibility_screen.dart';
import 'backend_connection_screen.dart';
import 'privacy_history_screen.dart';
import 'profile_screen.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
    super.key,
    required this.appController,
    required this.history,
  });

  final AppController appController;
  final HistoryService history;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Settings')),
    body: AnimatedBuilder(
      animation: appController,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          _ProfileCard(
            controller: appController,
            onTap: () =>
                _push(context, ProfileScreen(appController: appController)),
          ),
          const SizedBox(height: 26),
          const _SectionLabel('Appearance'),
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Theme',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: SegmentedButton<AppThemePreference>(
                      segments: const [
                        ButtonSegment(
                          value: AppThemePreference.dark,
                          icon: Icon(Icons.dark_mode_outlined),
                          label: Text('Dark'),
                        ),
                        ButtonSegment(
                          value: AppThemePreference.light,
                          icon: Icon(Icons.light_mode_outlined),
                          label: Text('Light'),
                        ),
                      ],
                      selected: {appController.theme},
                      showSelectedIcon: false,
                      onSelectionChanged: (selection) =>
                          appController.setTheme(selection.first),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 26),
          const _SectionLabel('App Settings'),
          const SizedBox(height: 10),
          Card(
            child: Column(
              children: [
                _SettingsTile(
                  icon: Icons.dns_outlined,
                  title: 'Backend Connection',
                  subtitle: 'Server URL and connection status',
                  onTap: () => _push(
                    context,
                    BackendConnectionScreen(settings: appController.settings),
                  ),
                ),
                const Divider(height: 1),
                _SettingsTile(
                  icon: Icons.shield_outlined,
                  title: 'Privacy & History',
                  subtitle: 'Recent scans and local storage',
                  onTap: () => _push(
                    context,
                    PrivacyHistoryScreen(
                      appController: appController,
                      history: history,
                    ),
                  ),
                ),
                const Divider(height: 1),
                _SettingsTile(
                  icon: Icons.accessibility_new_outlined,
                  title: 'Accessibility',
                  subtitle: 'Motion and contrast preferences',
                  onTap: () => _push(
                    context,
                    AccessibilityScreen(appController: appController),
                  ),
                ),
                const Divider(height: 1),
                _SettingsTile(
                  icon: Icons.info_outline_rounded,
                  title: 'About QRGuard',
                  subtitle: 'Project, architecture and privacy',
                  onTap: () => _push(context, const AboutScreen()),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  Future<void> _push(BuildContext context, Widget screen) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
}

class _ProfileCard extends StatelessWidget {
  const _ProfileCard({required this.controller, required this.onTap});

  final AppController controller;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final profile = controller.profile;
    final colors = context.qrColors;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: colors.secondarySurface,
                foregroundColor: colors.brandInk,
                child: Text(
                  profile.initials,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      profile.displayName,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      profile.institution.isEmpty
                          ? profile.role
                          : '${profile.role} · ${profile.institution}',
                      style: TextStyle(color: colors.secondaryText),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      'Local profile · stored on this device',
                      style: TextStyle(
                        color: colors.secondaryText,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

class SettingsBrandHeader extends StatelessWidget {
  const SettingsBrandHeader({
    super.key,
    required this.title,
    required this.body,
  });

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const PulseLensMark(size: 48),
      const SizedBox(width: 14),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 4),
            Text(
              body,
              style: TextStyle(
                color: context.qrColors.secondaryText,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

class _SettingsTile extends StatelessWidget {
  const _SettingsTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
    leading: Icon(icon, color: context.qrColors.brandInk),
    title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
    subtitle: Text(subtitle),
    trailing: const Icon(Icons.chevron_right_rounded),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    onTap: onTap,
  );
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Text(
    text.toUpperCase(),
    style: TextStyle(
      color: context.qrColors.brandInk,
      fontWeight: FontWeight.w800,
      fontSize: 12,
      letterSpacing: 1.3,
    ),
  );
}
