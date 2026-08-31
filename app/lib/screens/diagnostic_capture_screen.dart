/// Dedicated, local-only multi-frame camera collector.
library;

import 'dart:async';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../services/diagnostic_capture_service.dart';
import '../theme.dart';
import 'analysing_screen.dart';

class DiagnosticCaptureScreen extends StatefulWidget {
  const DiagnosticCaptureScreen({super.key, required this.service});

  final DiagnosticCaptureService service;

  @override
  State<DiagnosticCaptureScreen> createState() =>
      _DiagnosticCaptureScreenState();
}

class _DiagnosticCaptureScreenState extends State<DiagnosticCaptureScreen>
    with WidgetsBindingObserver {
  final _scanner = MobileScannerController(
    autoStart: false,
    detectionSpeed: DetectionSpeed.normal,
    detectionTimeoutMs: 180,
    cameraResolution: const Size(1280, 720),
    lensType: CameraLensType.any,
    formats: const [BarcodeFormat.qrCode],
    returnImage: true,
    autoZoom: false,
  );

  late DiagnosticCase _captureCase;
  late DiagnosticDistance _distance;
  DiagnosticProgress? _progress;
  final List<DiagnosticFrameEvidence> _frames = [];
  final Set<String> _frameHashes = {};
  String? _sessionPayload;
  DateTime? _lastAcceptedAt;
  bool _armed = false;
  bool _processingFrame = false;
  bool _busy = true;
  String? _message;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _captureCase = widget.service.plan.cases.first;
    _distance = widget.service.plan.distances.first;
    unawaited(_refresh());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) unawaited(_cancelBurst());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _scanner.dispose();
    unawaited(widget.service.close());
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final progress = await widget.service.progress();
      if (!mounted) return;
      setState(() {
        _progress = progress;
        _busy = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _message = _friendly(error);
      });
    }
  }

  int get _currentCount =>
      _progress?.countFor(_captureCase.caseId, _distance.id) ?? 0;

  bool get _currentComplete =>
      _currentCount >= widget.service.plan.repeatsPerDistance;

  Future<void> _changeSelection({
    DiagnosticCase? captureCase,
    DiagnosticDistance? distance,
  }) async {
    await _cancelBurst();
    if (!mounted) return;
    setState(() {
      _captureCase = captureCase ?? _captureCase;
      _distance = distance ?? _distance;
      _message = null;
    });
  }

  Future<void> _armBurst() async {
    if (_busy || _armed || _currentComplete) return;
    setState(() {
      _armed = true;
      _frames.clear();
      _frameHashes.clear();
      _sessionPayload = null;
      _lastAcceptedAt = null;
      _message =
          'Hold the phone naturally. QRGuard will save '
          '${widget.service.plan.framesPerSession} different temporal crops.';
    });
    try {
      await _scanner.start();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _armed = false;
        _message = 'Could not start the camera: ${_friendly(error)}';
      });
    }
  }

  Future<void> _cancelBurst() async {
    if (_armed) {
      try {
        await _scanner.stop();
      } catch (_) {
        // Stopping an already-paused controller is harmless.
      }
    }
    if (!mounted) return;
    setState(() {
      _armed = false;
      _frames.clear();
      _frameHashes.clear();
      _sessionPayload = null;
      _lastAcceptedAt = null;
    });
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (!_armed || _busy || _processingFrame) return;
    final readable = <String, Barcode>{};
    for (final barcode in capture.barcodes) {
      final payload = (barcode.rawValue ?? '').trim();
      if (payload.isNotEmpty) readable.putIfAbsent(payload, () => barcode);
    }
    if (readable.length != 1 || capture.image == null) {
      if (mounted && readable.length > 1) {
        setState(
          () => _message =
              'Multiple QR codes detected. Keep only the selected reference in view.',
        );
      }
      return;
    }
    final payload = readable.keys.single;
    if (!_captureCase.matchesExpectedPayload(payload)) {
      if (mounted) {
        setState(
          () => _message =
              'Wrong QR. Display ${_captureCase.caseId}.png and keep only it in view.',
        );
      }
      return;
    }
    final now = DateTime.now().toUtc();
    final last = _lastAcceptedAt;
    if (last != null &&
        now.difference(last) < const Duration(milliseconds: 140)) {
      return;
    }

    _processingFrame = true;
    try {
      final barcode = readable.values.single;
      final crop = await compute(prepareFirstUsableCropInBackground, [
        CropRequest(
          frame: capture.image!,
          cornerCoordinates: [
            for (final corner in barcode.corners) ...[corner.dx, corner.dy],
          ],
          frameWidth: capture.size.width,
          frameHeight: capture.size.height,
          normalizeCameraColor: true,
        ),
      ]).timeout(const Duration(seconds: 8));
      if (!_armed || !mounted) return;
      if (crop == null || crop.isEmpty) {
        setState(
          () => _message =
              'A decoded frame could not be rectified. Keep all four corners visible.',
        );
        return;
      }
      final cropHash = sha256.convert(crop).toString();
      if (!_frameHashes.add(cropHash)) {
        setState(
          () => _message =
              'Repeated camera frame skipped; keep holding the phone naturally.',
        );
        return;
      }
      _lastAcceptedAt = now;
      _sessionPayload ??= payload;
      _frames.add(
        DiagnosticFrameEvidence(
          cropPng: crop,
          capturedAt: now,
          frameWidth: capture.size.width,
          frameHeight: capture.size.height,
          cornerCoordinates: [
            for (final corner in barcode.corners) ...[corner.dx, corner.dy],
          ],
        ),
      );
      if (_frames.length >= widget.service.plan.framesPerSession) {
        await _completeBurst();
      } else if (mounted) {
        setState(
          () => _message =
              'Captured ${_frames.length}/${widget.service.plan.framesPerSession}. '
              'Keep the same distance until this burst finishes.',
        );
      }
    } on TimeoutException {
      if (mounted) {
        setState(
          () => _message =
              'Crop preparation timed out. Keep the QR steady and try again.',
        );
      }
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      _processingFrame = false;
    }
  }

  Future<void> _completeBurst() async {
    final payload = _sessionPayload;
    if (payload == null) return;
    _armed = false;
    if (mounted) setState(() => _busy = true);
    try {
      await _scanner.stop();
      await widget.service.saveSession(
        captureCase: _captureCase,
        distance: _distance,
        payload: payload,
        frames: List.unmodifiable(_frames),
      );
      final progress = await widget.service.progress();
      if (!mounted) return;
      final count = progress.countFor(_captureCase.caseId, _distance.id);
      setState(() {
        _progress = progress;
        _frames.clear();
        _frameHashes.clear();
        _sessionPayload = null;
        _lastAcceptedAt = null;
        _message = count >= widget.service.plan.repeatsPerDistance
            ? '${_captureCase.caseId} / ${_distance.label} is complete. '
                  'Select the next distance.'
            : 'Session $count/${widget.service.plan.repeatsPerDistance} saved. '
                  'Keep this distance and arm the next session.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export() async {
    if (_busy || (_progress?.pendingSessions ?? 0) == 0) return;
    await _cancelBurst();
    if (!mounted) return;
    setState(() {
      _busy = true;
      _message = 'Building the diagnostic ZIP…';
    });
    try {
      await widget.service.exportPendingToDownloads();
      final progress = await widget.service.progress();
      if (!mounted) return;
      setState(() {
        _progress = progress;
        _message =
            'ZIP saved in Android Downloads/QRGuard. The local sessions remain available.';
      });
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _discardLast() async {
    if (_busy || _armed || _currentCount == 0) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard last session?'),
        content: Text(
          'This removes the latest unexported ${_captureCase.caseId} / '
          '${_distance.label} burst from this phone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await widget.service.discardLastPendingSession(
        captureCase: _captureCase,
        distance: _distance,
      );
      final progress = await widget.service.progress();
      if (!mounted) return;
      setState(() {
        _progress = progress;
        _message = 'The latest unexported session was discarded.';
      });
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.qrColors;
    final plan = widget.service.plan;
    final progress = _progress;
    final currentSession = (_currentCount + 1).clamp(
      1,
      plan.repeatsPerDistance,
    );
    return Scaffold(
      appBar: AppBar(
        title: const Text('QRGuard Diagnostic Capture'),
        actions: [
          IconButton(
            tooltip: 'Export pending ZIP',
            onPressed: !_busy && (progress?.pendingSessions ?? 0) > 0
                ? _export
                : null,
            icon: const Icon(Icons.archive_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                color: colors.warningSurface,
                child: const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'Research diagnostic only · 5 temporal crops per session · '
                    'local storage · no destination is opened or uploaded.',
                  ),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<DiagnosticCase>(
                initialValue: _captureCase,
                decoration: const InputDecoration(
                  labelText: 'Reference case',
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final item in plan.cases)
                    DropdownMenuItem(
                      value: item,
                      child: Text('${item.caseId} · ${item.groundTruth}'),
                    ),
                ],
                onChanged: _armed || _busy
                    ? null
                    : (value) {
                        if (value != null) {
                          unawaited(_changeSelection(captureCase: value));
                        }
                      },
              ),
              const SizedBox(height: 12),
              SegmentedButton<DiagnosticDistance>(
                segments: [
                  for (final item in plan.distances)
                    ButtonSegment(value: item, label: Text(item.label)),
                ],
                selected: {_distance},
                onSelectionChanged: _armed || _busy
                    ? null
                    : (selection) => unawaited(
                        _changeSelection(distance: selection.single),
                      ),
              ),
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _captureCase.instruction,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      Text(_distance.instruction),
                      const SizedBox(height: 8),
                      Text(
                        'Current target: session $currentSession/'
                        '${plan.repeatsPerDistance}',
                        style: TextStyle(color: colors.secondaryText),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              _ProgressGrid(plan: plan, progress: progress),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(22),
                child: SizedBox(
                  height: 320,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      ColoredBox(
                        color: Colors.black,
                        child: MobileScanner(
                          controller: _scanner,
                          onDetect: _onDetect,
                          fit: BoxFit.cover,
                        ),
                      ),
                      IgnorePointer(
                        child: Center(
                          child: Container(
                            width: 238,
                            height: 238,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(
                                color: _armed
                                    ? colors.signalLight
                                    : Colors.white54,
                                width: 3,
                              ),
                            ),
                          ),
                        ),
                      ),
                      if (!_armed)
                        ColoredBox(
                          color: Colors.black54,
                          child: Center(
                            child: Text(
                              _currentComplete
                                  ? 'Distance complete'
                                  : 'Arm session to start',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                      Positioned(
                        left: 14,
                        right: 14,
                        bottom: 14,
                        child: LinearProgressIndicator(
                          value: _frames.length / plan.framesPerSession,
                          minHeight: 8,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _busy || _armed || _currentComplete
                    ? null
                    : _armBurst,
                icon: Icon(
                  _armed ? Icons.hourglass_top : Icons.camera_alt_outlined,
                ),
                label: Text(
                  _armed
                      ? 'Capturing ${_frames.length}/${plan.framesPerSession}'
                      : _currentComplete
                      ? 'This distance is complete'
                      : 'Arm session $currentSession',
                ),
              ),
              if (_armed) ...[
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: _cancelBurst,
                  child: const Text('Cancel current burst'),
                ),
              ],
              if (!_armed && _currentCount > 0) ...[
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: _busy ? null : _discardLast,
                  icon: const Icon(Icons.undo_rounded),
                  label: const Text('Discard latest unexported session'),
                ),
              ],
              if (_message != null) ...[
                const SizedBox(height: 10),
                Text(_message!, textAlign: TextAlign.center),
              ],
              const SizedBox(height: 14),
              Text(
                '${progress?.completedSessions ?? 0}/${plan.targetSessions} sessions · '
                '${progress?.pendingSessions ?? 0} waiting for ZIP export · '
                '${progress?.exportedSessions ?? 0} exported',
                textAlign: TextAlign.center,
                style: TextStyle(color: colors.secondaryText),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProgressGrid extends StatelessWidget {
  const _ProgressGrid({required this.plan, required this.progress});

  final DiagnosticCapturePlan plan;
  final DiagnosticProgress? progress;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Collection matrix',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          for (final captureCase in plan.cases) ...[
            Text(captureCase.caseId),
            const SizedBox(height: 4),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: [
                for (final distance in plan.distances)
                  Chip(
                    avatar: Icon(
                      (progress?.countFor(captureCase.caseId, distance.id) ??
                                  0) >=
                              plan.repeatsPerDistance
                          ? Icons.check_circle
                          : Icons.radio_button_unchecked,
                      size: 18,
                    ),
                    label: Text(
                      '${distance.label} '
                      '${progress?.countFor(captureCase.caseId, distance.id) ?? 0}/'
                      '${plan.repeatsPerDistance}',
                    ),
                  ),
              ],
            ),
            if (captureCase != plan.cases.last) const SizedBox(height: 10),
          ],
        ],
      ),
    ),
  );
}

String _friendly(Object error) {
  if (error is DiagnosticCaptureException) return error.message;
  return error.toString().replaceFirst(RegExp(r'^Exception: '), '');
}
