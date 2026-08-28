/// User-configurable backend address with an explicit, non-mutating health test.
library;

import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/settings_service.dart';
import '../theme.dart';
import 'settings_screen.dart';

class BackendConnectionScreen extends StatefulWidget {
  const BackendConnectionScreen({super.key, required this.settings});

  final SettingsService settings;

  @override
  State<BackendConnectionScreen> createState() =>
      _BackendConnectionScreenState();
}

class _BackendConnectionScreenState extends State<BackendConnectionScreen> {
  final _controller = TextEditingController();
  bool _saving = false;
  bool _testing = false;
  _ConnectionStatus _status = _ConnectionStatus.notTested;
  String? _message;

  @override
  void initState() {
    super.initState();
    widget.settings.backendUrl().then((url) {
      if (mounted) _controller.text = url;
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String? _validatedUrl() {
    final value = SettingsService.tryNormalise(_controller.text);
    if (value == null) {
      setState(() {
        _status = _ConnectionStatus.unreachable;
        _message = 'Enter a valid http:// or https:// backend address.';
      });
    }
    return value;
  }

  Future<void> _save() async {
    final url = _validatedUrl();
    if (url == null) return;
    setState(() => _saving = true);
    await widget.settings.setBackendUrl(url);
    if (!mounted) return;
    _controller.text = url;
    setState(() {
      _saving = false;
      _message =
          'Backend URL saved. Test the connection when the server is running.';
      _status = _ConnectionStatus.notTested;
    });
  }

  Future<void> _test() async {
    final url = _validatedUrl();
    if (url == null) return;
    setState(() {
      _testing = true;
      _message = null;
      _status = _ConnectionStatus.notTested;
    });
    final api = ApiClient(baseUrl: url, timeout: const Duration(seconds: 8));
    try {
      final health = await api.health();
      if (!mounted) return;
      setState(() {
        _status = health.isHealthy
            ? _ConnectionStatus.connected
            : _ConnectionStatus.degraded;
        final deep = health.deepCheckConfigured
            ? 'available'
            : 'not configured';
        _message = health.isHealthy
            ? 'Connected. Deep Check is $deep.'
            : 'The server is reachable but reports status: ${health.status}.';
      });
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _status = _ConnectionStatus.unreachable;
          _message = error.message;
        });
      }
    } finally {
      api.dispose();
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Backend Connection')),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
      children: [
        const SettingsBrandHeader(
          title: 'Analysis Server',
          body:
              'The backend may run on an emulator host, a laptop on the '
              'local network, or another configured address.',
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _controller,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: const InputDecoration(
                    labelText: 'Backend URL',
                    hintText: 'http://10.0.2.2:8001',
                    prefixIcon: Icon(Icons.dns_outlined),
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _saving ? null : _save,
                        icon: _saving
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.save_outlined),
                        label: const Text('Save'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _testing ? null : _test,
                        icon: _testing
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.wifi_tethering_rounded),
                        label: const Text('Test Connection'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _StatusCard(status: _status, message: _message),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Connection notes',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  'Use the address printed by scripts\\run_server.py. QRGuard '
                  'prefers port 8001 but may select another free port. A physical '
                  'phone and the computer must be on the same network.',
                  style: TextStyle(
                    color: context.qrColors.secondaryText,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

enum _ConnectionStatus { notTested, connected, degraded, unreachable }

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.status, required this.message});

  final _ConnectionStatus status;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final colors = context.qrColors;
    final (icon, label, color) = switch (status) {
      _ConnectionStatus.connected => (
        Icons.check_circle_outline_rounded,
        'Connected',
        colors.safe,
      ),
      _ConnectionStatus.degraded => (
        Icons.warning_amber_rounded,
        'Degraded',
        colors.warning,
      ),
      _ConnectionStatus.unreachable => (
        Icons.error_outline_rounded,
        'Unreachable',
        colors.blocked,
      ),
      _ConnectionStatus.notTested => (
        Icons.circle_outlined,
        'Not tested',
        colors.secondaryText,
      ),
    };
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.secondarySurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 21),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  if (message != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      message!,
                      style: TextStyle(
                        color: colors.secondaryText,
                        height: 1.35,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
