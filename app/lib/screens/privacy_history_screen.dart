/// Transparent controls for local history retention and deletion.
library;

import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../services/history_service.dart';
import '../theme.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

class PrivacyHistoryScreen extends StatelessWidget {
  const PrivacyHistoryScreen({
    super.key,
    required this.appController,
    required this.history,
  });

  final AppController appController;
  final HistoryService history;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Privacy & History')),
    body: AnimatedBuilder(
      animation: appController,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          const SettingsBrandHeader(
            title: 'Local by Design',
            body:
                'QRGuard keeps only the minimum information required for '
                'Recent Scans. Analysis images and raw URLs are not retained.',
          ),
          const SizedBox(height: 24),
          Card(
            child: Column(
              children: [
                SwitchListTile(
                  value: appController.saveHistory,
                  onChanged: appController.setSaveHistory,
                  secondary: Icon(
                    Icons.history_toggle_off_rounded,
                    color: context.qrColors.brandInk,
                  ),
                  title: const Text(
                    'Save Recent Scans',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  subtitle: const Text(
                    'Turning this off stops future records. Existing records '
                    'remain until cleared.',
                  ),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(
                    Icons.list_alt_rounded,
                    color: context.qrColors.brandInk,
                  ),
                  title: const Text(
                    'View Recent Scans',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => HistoryScreen(history: history),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _StorageLine(
                    icon: Icons.check_circle_outline_rounded,
                    color: context.qrColors.safe,
                    title: 'Stored locally',
                    body:
                        'SHA-256 payload hash, registered domain, verdict, '
                        'integer risk and scan time.',
                  ),
                  const SizedBox(height: 16),
                  _StorageLine(
                    icon: Icons.block_rounded,
                    color: context.qrColors.blocked,
                    title: 'Never stored in history',
                    body:
                        'Raw URL, full payload, URL path or query, and QR image.',
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          OutlinedButton.icon(
            onPressed: () => _confirmClear(context),
            icon: const Icon(Icons.delete_outline_rounded),
            label: const Text('Clear Scan History'),
            style: OutlinedButton.styleFrom(
              foregroundColor: context.qrColors.blocked,
            ),
          ),
        ],
      ),
    ),
  );

  Future<void> _confirmClear(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear scan history?'),
        content: const Text('This permanently removes all local scan records.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: context.qrColors.blocked,
            ),
            child: const Text('Clear History'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await history.clear();
    if (context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Scan history cleared.')));
    }
  }
}

class _StorageLine extends StatelessWidget {
  const _StorageLine({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, color: color, size: 21),
      const SizedBox(width: 10),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 3),
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
