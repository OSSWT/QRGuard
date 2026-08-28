/// Compact project and privacy summary for an FYP demonstration build.
library;

import 'package:flutter/material.dart';

import '../theme.dart';
import 'settings_screen.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  static const _version = '1.1.1 (8008)';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('About QRGuard')),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
      children: [
        const SettingsBrandHeader(
          title: 'QRGuard',
          body:
              'Real-Time Fraud Detection in QR Code Scanning Using AI '
              'Approach — a UTAR Final Year Project.',
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                const _AboutRow(label: 'Version', value: _version),
                const Divider(height: 24),
                const _AboutRow(
                  label: 'Project',
                  value: 'FYP2 · UTAR · Ooi Sze Shou',
                ),
                const Divider(height: 24),
                _AboutRow(
                  label: 'Architecture',
                  value:
                      'Structural CNN + Semantic URL analysis + trained '
                      'Fusion risk engine',
                  valueColor: context.qrColors.secondaryText,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 18),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Analysis policy',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  'A normal scan combines image structure, URL semantics and '
                  'deterministic security rules. Deep Check is an optional, '
                  'user-initiated second opinion and never runs automatically.',
                  style: TextStyle(
                    color: context.qrColors.secondaryText,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  'Privacy',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  'Scan history never stores a raw URL, QR image or full '
                  'payload. Local Profile is also stored only on this device.',
                  style: TextStyle(
                    color: context.qrColors.secondaryText,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 18),
        Text(
          'Built with Flutter, FastAPI, ONNX Runtime and open-source '
          'machine-learning tooling.',
          textAlign: TextAlign.center,
          style: TextStyle(color: context.qrColors.secondaryText, fontSize: 12),
        ),
      ],
    ),
  );
}

class _AboutRow extends StatelessWidget {
  const _AboutRow({required this.label, required this.value, this.valueColor});

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SizedBox(
        width: 88,
        child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
      ),
      Expanded(
        child: Text(
          value,
          style: TextStyle(
            color: valueColor ?? context.qrColors.primaryText,
            height: 1.35,
          ),
        ),
      ),
    ],
  );
}
