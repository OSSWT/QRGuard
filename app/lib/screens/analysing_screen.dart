/// Honest scan pipeline presentation: crop, analyse content, then compute risk.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/history_service.dart';
import '../services/qr_capture_selector.dart';
import '../services/qr_cropper.dart';
import '../theme.dart';
import '../widgets/pulse_lens.dart';
import 'result_screen.dart';

class CropRequest {
  const CropRequest({
    required this.frame,
    required this.corners,
    required this.frameSize,
    required this.normalizeCameraColor,
  });

  final Uint8List frame;
  final List<Offset> corners;
  final Size frameSize;
  final bool normalizeCameraColor;
}

/// One live-camera frame whose QR corners are expressed in [frameSize].
class QrFrameEvidence {
  const QrFrameEvidence({
    required this.frame,
    required this.corners,
    required this.frameSize,
  });

  final Uint8List frame;
  final List<Offset> corners;
  final Size frameSize;
}

class _CropPreparationTimeout implements Exception {
  const _CropPreparationTimeout();
}

Uint8List? cropInBackground(CropRequest request) => cropToCode(
  frame: request.frame,
  corners: request.corners,
  frameSize: request.frameSize,
  normalizeCameraColor: request.normalizeCameraColor,
);

class AnalysingScreen extends StatefulWidget {
  const AnalysingScreen({
    super.key,
    required this.api,
    required this.history,
    required this.saveHistory,
    required this.payload,
    this.frame,
    this.corners = const [],
    this.frameSize = Size.zero,
    this.imageSource = 'unknown',
    this.evidence = const [],
    this.cropTimeout = const Duration(seconds: 8),
    this.analysisTimeout = const Duration(seconds: 30),
  });

  final ApiClient api;
  final HistoryService history;
  final bool saveHistory;
  final String payload;
  final Uint8List? frame;
  final List<Offset> corners;
  final Size frameSize;
  final String imageSource;
  final List<QrFrameEvidence> evidence;
  final Duration cropTimeout;
  final Duration analysisTimeout;

  @override
  State<AnalysingScreen> createState() => _AnalysingScreenState();
}

class _AnalysingScreenState extends State<AnalysingScreen> {
  int _stage = 0;
  Uint8List? _crop;
  bool _imageUnavailable = false;
  String? _error;
  bool _running = false;
  bool _takingLonger = false;
  Timer? _slowTimer;
  Timer? _requestWatchdog;
  int _runId = 0;

  static const _stages = [
    'Checking image integrity',
    'Analysing QR content',
    'Computing risk',
  ];

  Future<Uint8List?> _prepareBestCrop(List<QrFrameEvidence> evidence) async {
    if (evidence.isEmpty) return null;
    var selected = evidence.first;
    if (evidence.length > 1) {
      try {
        final ranked = await compute(rankQrCaptures, [
          for (final sample in evidence)
            QrCaptureSample(
              frame: sample.frame,
              corners: sample.corners,
              frameSize: sample.frameSize,
            ),
        ]);
        if (ranked.isNotEmpty &&
            ranked.first >= 0 &&
            ranked.first < evidence.length) {
          selected = evidence[ranked.first];
        }
      } catch (_) {
        // The candidates already arrive geometry-ranked; the first is a safe
        // fallback on platforms where background isolate work is unavailable.
      }
    }
    return compute(
      cropInBackground,
      CropRequest(
        frame: selected.frame,
        corners: selected.corners,
        frameSize: selected.frameSize,
        normalizeCameraColor: widget.imageSource == 'camera',
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _run());
  }

  @override
  void dispose() {
    _runId++;
    _slowTimer?.cancel();
    _requestWatchdog?.cancel();
    super.dispose();
  }

  Future<void> _run() async {
    if (_running) return;
    final runId = ++_runId;
    setState(() {
      _running = true;
      _stage = 0;
      _error = null;
      _takingLonger = false;
    });
    try {
      final evidence = widget.evidence.isNotEmpty
          ? widget.evidence
          : widget.frame == null || widget.corners.isEmpty
          ? const <QrFrameEvidence>[]
          : [
              QrFrameEvidence(
                frame: widget.frame!,
                corners: widget.corners,
                frameSize: widget.frameSize,
              ),
            ];
      // Select and rectify on the visible Analysing screen. Previously this
      // work happened while Home still said "stable frame ready", which looked
      // like a frozen scan on physical phones.
      final imageBytes = evidence.isEmpty
          ? null
          : await _prepareBestCrop(evidence).timeout(
              widget.cropTimeout,
              onTimeout: () => throw const _CropPreparationTimeout(),
            );
      if (!mounted) return;
      setState(() {
        _crop = imageBytes;
        _imageUnavailable = imageBytes == null;
        _stage = 1;
      });

      _slowTimer?.cancel();
      _slowTimer = Timer(const Duration(seconds: 6), () {
        if (mounted && _running) setState(() => _takingLonger = true);
      });

      // ApiClient owns the normal HTTP timeout. This independent route-level
      // watchdog makes the recovery UI deterministic even if a platform
      // transport returns a Future that never completes. Incrementing _runId
      // invalidates the stale request so it cannot navigate after a retry.
      _requestWatchdog?.cancel();
      _requestWatchdog = Timer(widget.analysisTimeout, () {
        if (!mounted || !_running || runId != _runId) return;
        _runId++;
        _slowTimer?.cancel();
        setState(() {
          _running = false;
          _takingLonger = false;
          _error = _serverTimeoutMessage;
        });
      });
      final scan = await widget.api.scan(
        payload: widget.payload,
        imageBytes: imageBytes,
        imageSource: widget.imageSource,
      );
      _requestWatchdog?.cancel();
      _slowTimer?.cancel();
      if (!mounted || runId != _runId) return;
      setState(() {
        _stage = 2;
        _takingLonger = false;
      });
      // History is local and privacy-safe, but it must never hold the result
      // screen hostage if storage is temporarily slow or unavailable.
      if (widget.saveHistory) {
        unawaited(widget.history.record(scan).catchError((_) {}));
      }
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ResultScreen(scan: scan, api: widget.api),
        ),
      );
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (error) {
      if (mounted && runId == _runId) {
        setState(() => _error = error.message);
      }
    } on _CropPreparationTimeout {
      if (mounted && runId == _runId) {
        setState(() {
          _error =
              'QR image preparation took too long. Return to the scanner and '
              'hold the code steady before trying again.';
        });
      }
    } on TimeoutException {
      if (mounted && runId == _runId) {
        setState(() => _error = _serverTimeoutMessage);
      }
    } catch (_) {
      if (mounted && runId == _runId) {
        setState(() {
          _error = 'Could not prepare this QR code for analysis. Try again.';
        });
      }
    } finally {
      _requestWatchdog?.cancel();
      _slowTimer?.cancel();
      if (mounted && runId == _runId) {
        setState(() => _running = false);
      }
    }
  }

  String get _serverTimeoutMessage =>
      'The analysis service did not respond in time. It may be waking after an '
      'idle period. Wait a moment, then try again.';

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: true,
    child: Scaffold(
      appBar: AppBar(title: const Text('Analysing')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
          children: [
            Text(
              'Encoded signal acquired',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: context.qrColors.brandInk,
                letterSpacing: 1.1,
              ),
            ),
            const SizedBox(height: 18),
            Center(
              child: AnalysisLens(
                child: _crop == null
                    ? ColoredBox(
                        color: const Color(0xFF11100F),
                        child: Icon(
                          widget.frame == null || widget.corners.isEmpty
                              ? Icons.image_not_supported_outlined
                              : Icons.qr_code_2_rounded,
                          color: context.qrColors.signalLight,
                          size: 54,
                        ),
                      )
                    : Image.memory(_crop!, fit: BoxFit.cover),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Calculating risk score',
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              'QRGuard is inspecting the encoded destination and available '
              'image evidence.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: context.qrColors.secondaryText,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: List.generate(
                    _stages.length,
                    (index) => _StageRow(
                      label: index == 0 && _imageUnavailable
                          ? 'No image evidence — content checks continue'
                          : _stages[index],
                      state: index < _stage
                          ? _StageState.complete
                          : index == _stage
                          ? _StageState.active
                          : _StageState.upcoming,
                      last: index == _stages.length - 1,
                    ),
                  ),
                ),
              ),
            ),
            if (_takingLonger && _error == null) ...[
              const SizedBox(height: 14),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(15),
                  child: Column(
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.schedule_rounded,
                            color: context.qrColors.brandInk,
                          ),
                          const SizedBox(width: 10),
                          const Expanded(
                            child: Text(
                              'This is taking longer than usual. QRGuard will '
                              'keep checking while the analysis service wakes. '
                              'You can cancel and retry at any time.',
                              style: TextStyle(height: 1.4),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Cancel analysis'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 18),
              Card(
                color: context.qrColors.blockedSurface,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Icon(
                        Icons.error_outline_rounded,
                        color: context.qrColors.blocked,
                      ),
                      const SizedBox(height: 8),
                      Text(_error!, textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _running ? null : _run,
                        child: const Text('Try Again'),
                      ),
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Back to Scanner'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    ),
  );
}

enum _StageState { complete, active, upcoming }

class _StageRow extends StatelessWidget {
  const _StageRow({
    required this.label,
    required this.state,
    required this.last,
  });

  final String label;
  final _StageState state;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final colors = context.qrColors;
    final active = state == _StageState.active;
    final complete = state == _StageState.complete;
    final color = active || complete ? colors.brandInk : colors.secondaryText;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: complete ? colors.brand : colors.secondarySurface,
                border: Border.all(color: color, width: active ? 2 : 1),
              ),
              child: complete
                  ? const Icon(
                      Icons.check_rounded,
                      size: 15,
                      color: Color(0xFF11100F),
                    )
                  : active
                  ? Padding(
                      padding: const EdgeInsets.all(6),
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: colors.brandInk,
                      ),
                    )
                  : null,
            ),
            if (!last) Container(width: 1, height: 30, color: colors.border),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              label,
              style: TextStyle(
                color: color,
                fontWeight: active ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
