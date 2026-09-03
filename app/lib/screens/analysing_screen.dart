/// Honest scan pipeline presentation: crop, analyse content, then compute risk.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/capture_quality.dart';
import '../services/history_service.dart';
import '../services/qr_cropper.dart';
import '../theme.dart';
import '../widgets/pulse_lens.dart';
import 'result_screen.dart';

class CropRequest {
  const CropRequest({
    required this.frame,
    required this.cornerCoordinates,
    required this.frameWidth,
    required this.frameHeight,
    required this.normalizeCameraColor,
    this.minimumOutputSide = 24,
  });

  final Uint8List frame;

  /// Flat x/y values keep the message passed to `compute` free of dart:ui
  /// objects, which are not reliably transferable on every Android runtime.
  final List<double> cornerCoordinates;
  final double frameWidth;
  final double frameHeight;
  final bool normalizeCameraColor;
  final int minimumOutputSide;
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

class _ImageEvidenceUnavailable implements Exception {
  const _ImageEvidenceUnavailable();
}

class _InsufficientCameraFrames implements Exception {
  const _InsufficientCameraFrames();
}

/// Rectifies the first usable geometry-ranked frame and stops immediately.
///
/// The previous implementation decoded/cropped up to five full frames to rank
/// their sharpness and then decoded the winner again. On physical phones that
/// could exceed the eight-second preparation budget. Home already ranks frames
/// by QR coverage and geometry, so one pass with fallback is both faster and
/// more robust across ordinary, projected, angled and low-light QR codes.
Uint8List? prepareFirstUsableCropInBackground(List<CropRequest> requests) {
  final crops = prepareUsableCropsInBackground(requests);
  return crops.isEmpty ? null : crops.first;
}

/// Rectifies every usable temporal frame in order for backend consensus.
List<Uint8List> prepareUsableCropsInBackground(List<CropRequest> requests) {
  final crops = <Uint8List>[];
  for (final request in requests) {
    final crop = _prepareCrop(request);
    if (crop != null && crop.isNotEmpty) crops.add(crop);
  }
  return crops;
}

/// Keep five temporal candidates as fallback, but stop after the best three
/// deployment-scale crops are prepared. Home geometry-ranks the requests first.
List<Uint8List> prepareBestThreeCropsInBackground(List<CropRequest> requests) {
  final crops = <Uint8List>[];
  for (final request in requests) {
    final crop = _prepareCrop(request);
    if (crop == null || crop.isEmpty) continue;
    crops.add(crop);
    if (crops.length == 3) break;
  }
  return crops;
}

/// Rectify the bounded fallback pool, reject unusable pixels, then select three
/// frames by actual crop contrast/detail with a small exposure-diversity bonus.
/// This runs in the existing isolate so camera callbacks and preview stay fluid.
List<Uint8List> prepareQualityRankedCropsInBackground(
  List<CropRequest> requests,
) {
  final crops = prepareUsableCropsInBackground(requests);
  return [for (final ranked in rankCaptureCrops(crops)) ranked.bytes];
}

Uint8List? _prepareCrop(CropRequest request) {
  if (request.cornerCoordinates.length != 8) return null;
  final corners = <Offset>[
    for (var index = 0; index < 8; index += 2)
      Offset(
        request.cornerCoordinates[index],
        request.cornerCoordinates[index + 1],
      ),
  ];
  return cropToCode(
    frame: request.frame,
    corners: corners,
    frameSize: Size(request.frameWidth, request.frameHeight),
    normalizeCameraColor: request.normalizeCameraColor,
    minimumOutputSide: request.minimumOutputSide,
  );
}

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
    this.selectedImageBytes,
    this.cropTimeout = const Duration(seconds: 8),
    this.analysisTimeout = const Duration(seconds: 30),
  });

  final ApiClient api;
  final HistoryService history;
  final bool saveHistory;
  final String? payload;
  final Uint8List? frame;
  final List<Offset> corners;
  final Size frameSize;
  final String imageSource;
  final List<QrFrameEvidence> evidence;

  /// A browser-selected Gallery file. Web cannot call mobile_scanner's
  /// analyzeImage API, so the backend decodes and rectifies this image before
  /// Structural inference. Native camera/gallery flows continue to crop here.
  final Uint8List? selectedImageBytes;
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

  Future<List<Uint8List>> _prepareCrops(List<QrFrameEvidence> evidence) async {
    if (evidence.isEmpty) return const [];
    return compute(prepareQualityRankedCropsInBackground, [
      for (final sample in evidence.take(5))
        CropRequest(
          frame: sample.frame,
          cornerCoordinates: [
            for (final corner in sample.corners) ...[corner.dx, corner.dy],
          ],
          frameWidth: sample.frameSize.width,
          frameHeight: sample.frameSize.height,
          normalizeCameraColor: widget.imageSource == 'camera',
          minimumOutputSide: widget.imageSource == 'camera' ? 256 : 24,
        ),
    ]);
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
    final visibleTimer = Stopwatch()..start();
    final runId = ++_runId;
    setState(() {
      _running = true;
      _stage = 0;
      _error = null;
      _takingLonger = false;
      _crop = null;
      _imageUnavailable = false;
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
      final cropTimer = Stopwatch()..start();
      final imageFrames = widget.selectedImageBytes != null
          ? [widget.selectedImageBytes!]
          : evidence.isEmpty
          ? const <Uint8List>[]
          : await _prepareCrops(evidence).timeout(
              widget.cropTimeout,
              onTimeout: () => throw const _CropPreparationTimeout(),
            );
      cropTimer.stop();
      if (imageFrames.isEmpty &&
          (widget.imageSource == 'camera' || widget.imageSource == 'gallery')) {
        throw const _ImageEvidenceUnavailable();
      }
      if (widget.imageSource == 'camera' && imageFrames.length < 3) {
        throw const _InsufficientCameraFrames();
      }
      if (!mounted) return;
      setState(() {
        _crop = imageFrames.isEmpty ? null : imageFrames.first;
        _imageUnavailable = imageFrames.isEmpty;
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
      final requestTimer = Stopwatch()..start();
      final response = await widget.api.scan(
        payload: widget.payload,
        imageBytes: imageFrames.isEmpty ? null : imageFrames.first,
        additionalImageBytes: imageFrames.skip(1).toList(growable: false),
        imageSource: widget.imageSource,
      );
      requestTimer.stop();
      visibleTimer.stop();
      final scan = response.withTimings({
        'client_crop_png_encode': cropTimer.elapsedMilliseconds,
        'client_http_round_trip': requestTimer.elapsedMilliseconds,
        'client_visible_total': visibleTimer.elapsedMilliseconds,
      });
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
    } on _ImageEvidenceUnavailable {
      if (mounted && runId == _runId) {
        setState(() {
          _error =
              'QRGuard could not prepare a valid camera image. Return to the '
              'scanner, keep the whole code in view and try again.';
        });
      }
    } on _InsufficientCameraFrames {
      if (mounted && runId == _runId) {
        setState(() {
          _error =
              'QRGuard needs at least three clear camera frames. Return to the '
              'scanner, move closer and hold the whole code steady.';
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
