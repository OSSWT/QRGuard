/// Lightweight local identity. QRGuard has no account or cloud profile backend.
library;

import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../services/settings_service.dart';
import '../theme.dart';
import 'settings_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, required this.appController});

  final AppController appController;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final TextEditingController _name;
  late final TextEditingController _institution;
  late String _role;
  bool _saving = false;

  static const _roles = [
    'Student / Researcher',
    'Academic',
    'Security Practitioner',
    'Other',
  ];

  @override
  void initState() {
    super.initState();
    final profile = widget.appController.profile;
    _name = TextEditingController(text: profile.displayName);
    _institution = TextEditingController(text: profile.institution);
    _role = _roles.contains(profile.role) ? profile.role : 'Other';
  }

  @override
  void dispose() {
    _name.dispose();
    _institution.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Enter a display name.')));
      return;
    }
    setState(() => _saving = true);
    await widget.appController.setProfile(
      LocalProfile(
        displayName: name,
        role: _role,
        institution: _institution.text.trim(),
      ),
    );
    if (!mounted) return;
    setState(() => _saving = false);
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Local profile saved.')));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Profile')),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
      children: [
        const SettingsBrandHeader(
          title: 'Local Profile',
          body:
              'This identity stays on this device. QRGuard does not use '
              'online accounts or cloud profile sync.',
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                CircleAvatar(
                  radius: 36,
                  backgroundColor: context.qrColors.secondarySurface,
                  foregroundColor: context.qrColors.brandInk,
                  child: Text(
                    LocalProfile(
                      displayName: _name.text,
                      role: _role,
                      institution: _institution.text,
                    ).initials,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(
                    labelText: 'Display name',
                    prefixIcon: Icon(Icons.person_outline_rounded),
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  initialValue: _role,
                  items: _roles
                      .map(
                        (role) =>
                            DropdownMenuItem(value: role, child: Text(role)),
                      )
                      .toList(),
                  onChanged: (value) {
                    if (value != null) setState(() => _role = value);
                  },
                  decoration: const InputDecoration(
                    labelText: 'Role',
                    prefixIcon: Icon(Icons.badge_outlined),
                  ),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: _institution,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(
                    labelText: 'Institution (optional)',
                    prefixIcon: Icon(Icons.school_outlined),
                  ),
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: _saving
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save_outlined),
                  label: Text(_saving ? 'Saving...' : 'Save Profile'),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}
