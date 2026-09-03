/// Home scanner, explicit Scan/Gallery actions and privacy-preserving history.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../app_controller.dart';
import '../services/api_client.dart';
import '../services/camera_exposure_policy.dart';
import '../services/capture_quality.dart';
import '../services/history_service.dart';
import '../services/live_camera_frame.dart';
import '../services/live_qr_stability.dart';
import '../theme.dart';
import '../widgets/pulse_lens.dart';
import 'analysing_screen.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.appController});

  final AppController appController;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  final _scanner = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    // Analyse often enough to feel immediate without running overlapping ML Kit
    // work on older phones. A successful QR decode already includes checksum/
    // error-correction validation, so Home does not need three more sightings.
    detectionTimeoutMs: 100,
    cameraResolution: const Size(1280, 720),
    // Emulator webcams are commonly exposed as an external lens. `normal`
    // filters them out and makes mobile_scanner report "No cameras available".
    // `any` still starts the back camera on phones while keeping webcam-backed
    // development devices usable.
    lensType: CameraLensType.any,
    formats: const [BarcodeFormat.qrCode],
    returnImage: true,
    // Projected/classroom QR codes can occupy only a small part of the frame.
    // ML Kit auto-zoom improves decoding; QRGuard still rectifies the detected
    // code before any image evidence reaches the backend.
    autoZoom: true,
  );
  final _history = HistoryService();
  final _picker = ImagePicker();
  final _stability = LiveQrStabilityGate(
    stableFor: const Duration(milliseconds: 600),
    minimumSightings: 5,
    maximumGap: const Duration(milliseconds: 900),
  );

  ApiClient? _api;
  _Candidate? _candidate;
  final List<_Candidate> _liveCandidates = [];
  bool _capturingWebFrame = false;
  bool _navigating = false;
  bool _confirming = false;
  String? _dismissedPayload;
  Timer? _autoPromptTimer;
  Timer? _candidateExpiryTimer;
  String? _scheduledPromptPayload;
  DateTime? _candidateLastSeen;
  bool _candidateReady = false;
  String? _exposureCheckedPayload;
  String? _exposureCheckingPayload;
  int _exposureCheckToken = 0;
  String? _message;
  List<ScanRecord> _recent = const [];

  static const _autoPromptDelay = Duration(milliseconds: 40);
  static const _candidateLifetime = Duration(milliseconds: 1800);
  // Retain five temporally distinct candidates as a fallback pool. Analysing
  // prepares and uploads the first three geometry-ranked crops that actually
  // meet the 256 px deployment boundary, then the backend forms consensus.
  static const _maximumLiveCandidates = 5;
  static const _minimumStructuralCropSide = 256.0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadApi();
    _loadHistory();
  }

  Future<void> _loadApi() async {
    final url = await widget.appController.settings.backendUrl();
    if (!mounted) return;
    final previous = _api;
    final next = ApiClient(baseUrl: url);
    setState(() => _api = next);
    previous?.dispose();
    // Render may suspend a free service while idle. Wake it while the user is
    // aiming the camera so the first real scan does not pay the cold-start wait.
    unawaited(next.health().then<void>((_) {}, onError: (_) {}));
  }

  Future<void> _loadHistory() async {
    final records = await _history.recent(limit: 3);
    if (mounted) setState(() => _recent = records);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && !_navigating && !_confirming) {
      _safeStart();
    } else if (state != AppLifecycleState.resumed) {
      _safeStop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _autoPromptTimer?.cancel();
    _candidateExpiryTimer?.cancel();
    _scanner.dispose();
    _api?.dispose();
    _history.close();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_navigating || _confirming) return;
    final byPayload = <String, Barcode>{};
    for (final barcode in capture.barcodes) {
      final payload = (barcode.rawValue ?? '').trim();
      if (payload.isNotEmpty) byPayload.putIfAbsent(payload, () => barcode);
    }
    final readable = byPayload.values.toList();
    if (readable.isEmpty) return;
    if (readable.length > 1) {
      _autoPromptTimer?.cancel();
      _scheduledPromptPayload = null;
      _stability.reset();
      _resetExposureCheck();
      if (mounted) {
        setState(() {
          _candidate = null;
          _liveCandidates.clear();
          _candidateReady = false;
          _message =
              'Multiple QR codes detected. Align one code inside the frame.';
        });
      }
      return;
    }

    final barcode = readable.single;
    final payload = barcode.rawValue!.trim();
    final seenAt = DateTime.now();
    final nextCandidate = _Candidate(
      payload: payload,
      frame: capture.image,
      corners: barcode.corners,
      frameSize: capture.size,
      imageSource: 'camera',
    );
    if (nextCandidate.hasUsableGeometry &&
        nextCandidate.estimatedCropSide < _minimumStructuralCropSide) {
      _autoPromptTimer?.cancel();
      _scheduledPromptPayload = null;
      _stability.reset();
      _liveCandidates.clear();
      _candidateLastSeen = seenAt;
      setState(() {
        _candidate = nextCandidate;
        _candidateReady = false;
        _message =
            'QR detected, but it is too small for reliable image-integrity '
            'analysis. Move closer until the code fills the guide.';
      });
      unawaited(_focusOnQr(barcode, capture.size));
      _refreshCandidateExpiry(payload);
      return;
    }
    final observation = _stability.observe(payload, seenAt);
    final previous = _candidate;
    if (observation.startedNewSequence && previous?.payload != payload) {
      _resetExposureCheck();
    }
    final candidate =
        !observation.startedNewSequence &&
            previous?.payload == payload &&
            previous!.quality >= nextCandidate.quality
        ? previous
        : nextCandidate;
    if (observation.startedNewSequence) _liveCandidates.clear();
    if (nextCandidate.hasUsableImage) {
      _liveCandidates.add(nextCandidate);
      if (_liveCandidates.length > _maximumLiveCandidates) {
        _liveCandidates.removeAt(0);
      }
    } else if (kIsWeb && nextCandidate.hasUsableGeometry) {
      unawaited(_retainWebFrame(nextCandidate));
    }
    _candidateLastSeen = seenAt;
    final hasTemporalEvidence = _liveCandidates.length >= 3;
    final exposureReady =
        !_requiresExposureCheck || _exposureCheckedPayload == payload;
    setState(() {
      _message = null;
      _candidate = candidate;
      _candidateReady =
          observation.ready &&
          hasTemporalEvidence &&
          exposureReady &&
          _exposureCheckingPayload == null;
    });
    if (observation.startedNewSequence) {
      unawaited(_focusOnQr(barcode, capture.size));
    }
    if (observation.sightings >= 3 &&
        _exposureCheckedPayload != payload &&
        _exposureCheckingPayload != payload) {
      unawaited(_checkAndAdjustExposure(nextCandidate));
    }
    _refreshCandidateExpiry(payload);
    if (_candidateReady) _scheduleAutoPrompt(payload);
  }

  Future<void> _retainWebFrame(_Candidate candidate) async {
    if (_capturingWebFrame) return;
    _capturingWebFrame = true;
    try {
      final frame = await captureLiveCameraFrame();
      if (!mounted || frame == null || frame.isEmpty) return;
      if (_candidate?.payload != candidate.payload) return;
      final retained = candidate.withFrame(frame);
      _liveCandidates.add(retained);
      if (_liveCandidates.length > _maximumLiveCandidates) {
        _liveCandidates.removeAt(0);
      }
      final ready =
          _liveCandidates.length >= 3 &&
          _stability.isReady(candidate.payload, DateTime.now());
      setState(() {
        if ((_candidate?.quality ?? 0) <= retained.quality) {
          _candidate = retained;
        }
        _candidateReady = ready;
      });
      if (ready) _scheduleAutoPrompt(candidate.payload);
    } finally {
      _capturingWebFrame = false;
    }
  }

  Future<void> _focusOnQr(Barcode barcode, Size frameSize) async {
    if (barcode.corners.length != 4 ||
        frameSize.width <= 0 ||
        frameSize.height <= 0) {
      return;
    }
    final centre = Offset(
      barcode.corners.map((point) => point.dx).reduce((a, b) => a + b) / 4,
      barcode.corners.map((point) => point.dy).reduce((a, b) => a + b) / 4,
    );
    try {
      await _scanner.setFocusPoint(
        Offset(centre.dx / frameSize.width, centre.dy / frameSize.height),
      );
    } catch (_) {
      // Some camera implementations do not expose a focus point. The QR was
      // already decoded and validated, so lack of manual focus is non-fatal.
    }
  }

  bool get _requiresExposureCheck =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  void _resetExposureCheck() {
    _exposureCheckToken++;
    _exposureCheckedPayload = null;
    _exposureCheckingPayload = null;
  }

  Future<void> _checkAndAdjustExposure(_Candidate candidate) async {
    final payload = candidate.payload;
    if (!_requiresExposureCheck || !candidate.hasUsableImage) {
      if (mounted && _candidate?.payload == payload) {
        setState(() => _exposureCheckedPayload = payload);
      }
      return;
    }
    final token = _exposureCheckToken;
    setState(() {
      _exposureCheckingPayload = payload;
      _candidateReady = false;
      _message = 'QR detected · checking camera exposure';
    });
    var adjusted = false;
    try {
      final telemetry = await compute(
        assessFrameCaptureQuality,
        CaptureFrameQualityRequest(
          frame: candidate.frame!,
          cornerCoordinates: [
            for (final corner in candidate.corners) ...[corner.dx, corner.dy],
          ],
          frameWidth: candidate.frameSize.width,
          frameHeight: candidate.frameSize.height,
        ),
      );
      if (!mounted || token != _exposureCheckToken) return;
      final quality = telemetry == null
          ? null
          : CaptureQualityReport.fromTelemetry(telemetry);
      if (quality != null) {
        final exposure = await _scanner.getExposureCompensationState();
        if (!mounted || token != _exposureCheckToken) return;
        final plan = planCaptureExposureAdjustment(
          quality: quality,
          exposure: exposure,
        );
        if (plan != null) {
          await _scanner.setExposureCompensationIndex(plan.targetIndex);
          if (!mounted || token != _exposureCheckToken) return;
          adjusted = true;
        }
      }
    } catch (_) {
      // Exposure compensation is a best-effort Android capability. The final
      // crop quality gate still rejects unusable evidence on unsupported phones.
    } finally {
      if (mounted && token == _exposureCheckToken) {
        _exposureCheckingPayload = null;
        _exposureCheckedPayload = payload;
        if (adjusted) {
          _autoPromptTimer?.cancel();
          _scheduledPromptPayload = null;
          _liveCandidates.clear();
          _stability.reset();
          setState(() {
            _candidateReady = false;
            _message = 'Camera exposure adjusted · hold steady';
          });
        } else {
          final ready =
              _liveCandidates.length >= 3 &&
              _stability.isReady(payload, DateTime.now());
          setState(() {
            _candidateReady = ready;
            _message = null;
          });
          if (ready) _scheduleAutoPrompt(payload);
        }
      }
    }
  }

  void _scheduleAutoPrompt(String payload) {
    if (_dismissedPayload == payload ||
        (_scheduledPromptPayload == payload &&
            _autoPromptTimer?.isActive == true)) {
      return;
    }
    _autoPromptTimer?.cancel();
    _scheduledPromptPayload = payload;
    _autoPromptTimer = Timer(_autoPromptDelay, () {
      _scheduledPromptPayload = null;
      final candidate = _candidate;
      if (!mounted ||
          _confirming ||
          _navigating ||
          candidate?.payload != payload ||
          _dismissedPayload == payload) {
        return;
      }
      unawaited(_confirmDetectedQr(candidate!));
    });
  }

  void _refreshCandidateExpiry(String payload) {
    _candidateExpiryTimer?.cancel();
    _candidateExpiryTimer = Timer(_candidateLifetime, () {
      if (!mounted ||
          _confirming ||
          _navigating ||
          _candidate?.payload != payload) {
        return;
      }
      setState(() {
        _candidate = null;
        _liveCandidates.clear();
        _candidateReady = false;
        _candidateLastSeen = null;
        _dismissedPayload = null;
      });
      _stability.reset();
      _resetExposureCheck();
    });
  }

  Future<void> _confirmDetectedQr(_Candidate candidate) async {
    if (!mounted || _confirming || _navigating) return;
    _autoPromptTimer?.cancel();
    _scheduledPromptPayload = null;
    setState(() => _confirming = true);
    final preparedCandidate = await _withLiveCameraFrame(candidate);
    if (!mounted) return;
    if (preparedCandidate == null) {
      setState(() {
        _confirming = false;
        _message =
            'QR detected, but a camera image was not ready. Keep the code in '
            'view and try again.';
      });
      return;
    }
    await _safeStop();
    if (!mounted) return;

    final proceed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        icon: Icon(
          Icons.qr_code_scanner_rounded,
          color: dialogContext.qrColors.brandInk,
        ),
        title: const Text('Scan this QR code?'),
        content: const Text(
          'One QR code remained clear across five camera frames. Continue to '
          'analyse its image integrity and encoded destination?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Not now'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.security_rounded),
            label: const Text('Analyse QR'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    setState(() => _confirming = false);
    if (proceed == true) {
      _dismissedPayload = null;
      final evidence = _evidenceForPayload(preparedCandidate.payload);
      await _openAnalysis(
        evidence.isEmpty ? preparedCandidate : evidence.first,
        evidence: evidence,
      );
      return;
    }
    _dismissedPayload = candidate.payload;
    await _safeStart();
  }

  Future<void> _scanCandidate() async {
    final candidate = _candidate;
    final lastSeen = _candidateLastSeen;
    if (candidate == null ||
        lastSeen == null ||
        DateTime.now().difference(lastSeen) > _candidateLifetime) {
      setState(() {
        _message =
            'No QR detected yet. Move closer, hold steady and keep one '
            'code inside the frame while the camera searches again.';
      });
      await _safeStop();
      await _safeStart();
      return;
    }
    if (!_candidateReady ||
        !_stability.isReady(candidate.payload, DateTime.now())) {
      setState(() {
        _message =
            'QR detected. Hold the camera steady for a moment while QRGuard '
            'selects a clear frame.';
      });
      return;
    }
    _autoPromptTimer?.cancel();
    _scheduledPromptPayload = null;
    setState(() => _confirming = true);
    final preparedCandidate = await _withLiveCameraFrame(candidate);
    if (!mounted) return;
    if (preparedCandidate == null) {
      setState(() {
        _confirming = false;
        _message =
            'QR detected, but a camera image was not ready. Keep the code in '
            'view and try again.';
      });
      return;
    }
    await _safeStop();
    final evidence = _evidenceForPayload(preparedCandidate.payload);
    if (!mounted) return;
    await _openAnalysis(
      evidence.isEmpty ? preparedCandidate : evidence.first,
      evidence: evidence,
    );
  }

  /// Web barcode events contain corners and payload but never encoded image
  /// bytes. Snapshot the still-running video before the scanner is stopped.
  /// Native captures already contain JPEG bytes and return immediately.
  Future<_Candidate?> _withLiveCameraFrame(_Candidate candidate) async {
    if (candidate.hasUsableImage) return candidate;
    if (!kIsWeb ||
        candidate.corners.length != 4 ||
        candidate.frameSize.width <= 0 ||
        candidate.frameSize.height <= 0) {
      return null;
    }
    final frame = await captureLiveCameraFrame();
    if (frame == null || frame.isEmpty) return null;
    return candidate.withFrame(frame);
  }

  List<_Candidate> _evidenceForPayload(String payload) {
    final candidates = [
      for (final candidate in _liveCandidates)
        if (candidate.payload == payload && candidate.hasUsableImage) candidate,
    ];
    if (candidates.isEmpty) return const [];
    // Full-resolution crop/clarity work is intentionally deferred until the
    // Analysing screen is visible. Sorting by cheap geometry first gives that
    // worker the strongest candidates without freezing this ready state.
    candidates.sort((left, right) => right.quality.compareTo(left.quality));
    return candidates;
  }

  Future<void> _pickGalleryImage() async {
    await _safeStop();
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image == null) {
      await _safeStart();
      return;
    }
    try {
      if (kIsWeb) {
        final bytes = await image.readAsBytes();
        if (bytes.isEmpty) {
          _showMessage('That file is empty. Choose another QR image.');
          await _safeStart();
          return;
        }
        await _openAnalysis(
          _Candidate(
            payload: '',
            frame: bytes,
            corners: const [],
            frameSize: Size.zero,
            imageSource: 'gallery',
          ),
          selectedImageBytes: bytes,
        );
        return;
      }
      final capture = await _scanner.analyzeImage(image.path);
      final byPayload = <String, Barcode>{};
      for (final barcode in capture?.barcodes ?? const <Barcode>[]) {
        final payload = (barcode.rawValue ?? '').trim();
        if (payload.isNotEmpty) byPayload.putIfAbsent(payload, () => barcode);
      }
      final readable = byPayload.values.toList();
      if (readable.isEmpty) {
        _showMessage('No readable QR code was found in that image.');
        await _safeStart();
        return;
      }
      if (readable.length > 1) {
        _showMessage(
          'That image contains multiple QR codes. Choose an image with one.',
        );
        await _safeStart();
        return;
      }
      final barcode = readable.single;
      // Prefer the bytes returned with the detection because its orientation and
      // coordinate space match barcode.corners. The selected file is only a fallback.
      final bytes = capture?.image ?? await image.readAsBytes();
      await _openAnalysis(
        _Candidate(
          payload: barcode.rawValue!.trim(),
          frame: bytes,
          corners: barcode.corners,
          frameSize: capture?.size ?? Size.zero,
          imageSource: 'gallery',
        ),
      );
    } on UnsupportedError {
      _showMessage('Gallery QR analysis is unavailable on this device.');
      await _safeStart();
    } catch (_) {
      _showMessage('Could not read that gallery image. Try another image.');
      await _safeStart();
    }
  }

  Future<void> _openAnalysis(
    _Candidate candidate, {
    List<_Candidate> evidence = const [],
    Uint8List? selectedImageBytes,
  }) async {
    final api = _api;
    if (api == null || _navigating) return;
    setState(() {
      _navigating = true;
      _confirming = false;
      _message = null;
    });
    _autoPromptTimer?.cancel();
    _candidateExpiryTimer?.cancel();
    _scheduledPromptPayload = null;
    await _safeStop();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AnalysingScreen(
          api: api,
          history: _history,
          saveHistory: widget.appController.saveHistory,
          payload: candidate.payload,
          frame: candidate.frame,
          corners: candidate.corners,
          frameSize: candidate.frameSize,
          imageSource: candidate.imageSource,
          selectedImageBytes: selectedImageBytes,
          evidence: [
            for (final sample in evidence)
              QrFrameEvidence(
                frame: sample.frame!,
                corners: sample.corners,
                frameSize: sample.frameSize,
              ),
          ],
        ),
      ),
    );
    if (!mounted) return;
    setState(() {
      _navigating = false;
      _candidate = null;
      _liveCandidates.clear();
      _candidateReady = false;
      _dismissedPayload = null;
      _candidateLastSeen = null;
    });
    _stability.reset();
    _resetExposureCheck();
    await _loadHistory();
    await _safeStart();
  }

  Future<void> _openSettings() async {
    if (_navigating) return;
    setState(() => _navigating = true);
    await _safeStop();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => SettingsScreen(
          appController: widget.appController,
          history: _history,
        ),
      ),
    );
    if (!mounted) return;
    setState(() => _navigating = false);
    await _loadApi();
    await _loadHistory();
    await _safeStart();
  }

  Future<void> _openHistory() async {
    if (_navigating) return;
    setState(() => _navigating = true);
    await _safeStop();
    if (!mounted) return;
    await Navigator.of(
      context,
    ).push(MaterialPageRoute(builder: (_) => HistoryScreen(history: _history)));
    if (!mounted) return;
    setState(() => _navigating = false);
    await _loadHistory();
    await _safeStart();
  }

  Future<void> _safeStart() async {
    try {
      await _scanner.start();
    } catch (_) {
      // The scanner can already be running or waiting for permission.
    }
  }

  Future<void> _safeStop() async {
    try {
      await _scanner.stop();
    } catch (_) {
      // Stopping an already stopped controller is harmless for navigation.
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    setState(() => _message = message);
  }

  ButtonStyle _scannerActionStyle(BuildContext context) {
    final colors = context.qrColors;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(Size.fromHeight(54)),
      animationDuration: const Duration(milliseconds: 130),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      backgroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) {
          return isDark
              ? colors.secondarySurface.withValues(alpha: 0.68)
              : colors.mutedStructure.withValues(alpha: 0.55);
        }
        if (states.contains(WidgetState.pressed)) return colors.brand;
        if (states.contains(WidgetState.hovered) ||
            states.contains(WidgetState.focused)) {
          return isDark
              ? Color.alphaBlend(
                  colors.brand.withValues(alpha: 0.22),
                  colors.elevatedSurface,
                )
              : colors.signalLight;
        }
        return isDark ? colors.elevatedSurface : colors.focal;
      }),
      foregroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.disabled)) {
          return colors.secondaryText;
        }
        if (states.contains(WidgetState.pressed) || !isDark) {
          return const Color(0xFF11100F);
        }
        return colors.signalLight;
      }),
      overlayColor: WidgetStatePropertyAll(
        colors.brand.withValues(alpha: 0.18),
      ),
      side: WidgetStateProperty.resolveWith(
        (states) => BorderSide(
          color: states.contains(WidgetState.pressed)
              ? colors.signalLight
              : isDark
              ? colors.brand.withValues(alpha: 0.78)
              : colors.border,
          width: states.contains(WidgetState.focused) ? 2 : 1,
        ),
      ),
      elevation: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.pressed)) return 0;
        if (states.contains(WidgetState.hovered)) return isDark ? 5 : 3;
        return isDark ? 2 : 1;
      }),
      shadowColor: WidgetStatePropertyAll(
        colors.brand.withValues(alpha: isDark ? 0.30 : 0.16),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final detected = _candidate != null;
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, viewport) {
            final wide = viewport.maxWidth >= 900;
            return CustomScrollView(
              slivers: [
                SliverPadding(
                  padding: EdgeInsets.fromLTRB(
                    wide ? 32 : 20,
                    12,
                    wide ? 32 : 20,
                    32,
                  ),
                  sliver: SliverToBoxAdapter(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 1180),
                        child: Column(
                          children: [
                            _buildHeader(context),
                            const SizedBox(height: 20),
                            if (wide)
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                    flex: 6,
                                    child: _buildScannerPanel(
                                      context,
                                      detected,
                                    ),
                                  ),
                                  const SizedBox(width: 32),
                                  Expanded(
                                    flex: 5,
                                    child: _buildRecentPanel(context),
                                  ),
                                ],
                              )
                            else ...[
                              _buildScannerPanel(context, detected),
                              const SizedBox(height: 28),
                              _buildRecentPanel(context),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) => Row(
    children: [
      const PulseLensMark(size: 46),
      const SizedBox(width: 12),
      Expanded(
        child: Text(
          'QRGuard',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w900,
            letterSpacing: 0.2,
          ),
        ),
      ),
      IconButton.filledTonal(
        tooltip: 'Settings',
        onPressed: _openSettings,
        icon: const Icon(Icons.settings_outlined),
      ),
    ],
  );

  Widget _buildScannerPanel(BuildContext context, bool detected) {
    final colors = context.qrColors;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 580),
        child: Column(
          children: [
            AspectRatio(
              aspectRatio: 1,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: const Color(0xFF11100F),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: colors.border, width: 1.5),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(22),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      ColoredBox(
                        color: const Color(0xFF11100F),
                        child: MobileScanner(
                          controller: _scanner,
                          onDetect: _onDetect,
                          fit: BoxFit.cover,
                          tapToFocus: true,
                        ),
                      ),
                      LiveCameraFrame(detected: detected),
                      Positioned(
                        left: 0,
                        right: 0,
                        top: 14,
                        child: Center(
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: const Color(
                                0xFF11100F,
                              ).withValues(alpha: 0.78),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: const Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: 11,
                                vertical: 7,
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.videocam_outlined,
                                    color: Color(0xFFFFD0A8),
                                    size: 16,
                                  ),
                                  SizedBox(width: 6),
                                  Text(
                                    'Live camera',
                                    style: TextStyle(
                                      color: Color(0xFFF8EEE7),
                                      fontWeight: FontWeight.w700,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                      Positioned(
                        left: 16,
                        right: 16,
                        bottom: 14,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: const Color(
                              0xFF11100F,
                            ).withValues(alpha: 0.82),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 9,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  detected
                                      ? _candidateReady
                                            ? Icons.center_focus_strong_rounded
                                            : Icons.hourglass_top_rounded
                                      : Icons.center_focus_weak_rounded,
                                  color: _candidateReady
                                      ? colors.signalLight
                                      : colors.brand,
                                  size: 18,
                                ),
                                const SizedBox(width: 8),
                                Flexible(
                                  child: Text(
                                    detected
                                        ? _candidateReady
                                              ? 'QR detected · opening confirmation'
                                              : 'QR detected · hold steady'
                                        : 'Align one QR inside the frame',
                                    textAlign: TextAlign.center,
                                    style: TextStyle(
                                      color: _candidateReady
                                          ? colors.signalLight
                                          : const Color(0xFFF8EEE7),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (_message != null) ...[
              const SizedBox(height: 12),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: colors.warningSurface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: colors.warning),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(Icons.info_outline_rounded, color: colors.warning),
                      const SizedBox(width: 9),
                      Expanded(child: Text(_message!)),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    style: _scannerActionStyle(context),
                    onPressed: _api == null || _navigating || _confirming
                        ? null
                        : _scanCandidate,
                    icon: const Icon(Icons.qr_code_scanner_rounded),
                    label: const Text('Scan'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    style: _scannerActionStyle(context),
                    onPressed: _navigating || _confirming
                        ? null
                        : _pickGalleryImage,
                    icon: Icon(
                      kIsWeb
                          ? Icons.upload_file_outlined
                          : Icons.photo_library_outlined,
                    ),
                    label: Text(kIsWeb ? 'Choose file' : 'Gallery'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Auto-detect is on · Scan is the backup action',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.secondaryText, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentPanel(BuildContext context) {
    final colors = context.qrColors;
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Recent Scans',
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            if (_recent.isNotEmpty)
              TextButton(
                onPressed: _openHistory,
                child: const Text('View all'),
              ),
          ],
        ),
        const SizedBox(height: 10),
        if (_recent.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Row(
                children: [
                  Icon(Icons.history_rounded, color: colors.secondaryText),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      widget.appController.saveHistory
                          ? 'Scanned domains will appear here. Full URLs and QR '
                                'images are never stored.'
                          : 'Recent Scans is disabled in Privacy & History.',
                      style: TextStyle(
                        color: colors.secondaryText,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          )
        else
          ..._recent.map(
            (record) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: ScanHistoryTile(record: record, compact: true),
            ),
          ),
      ],
    );
  }
}

class _Candidate {
  const _Candidate({
    required this.payload,
    required this.frame,
    required this.corners,
    required this.frameSize,
    required this.imageSource,
  });

  final String payload;
  final Uint8List? frame;
  final List<Offset> corners;
  final Size frameSize;
  final String imageSource;

  _Candidate withFrame(Uint8List value) => _Candidate(
    payload: payload,
    frame: value,
    corners: corners,
    frameSize: frameSize,
    imageSource: imageSource,
  );

  bool get hasUsableImage => frame != null && hasUsableGeometry;

  bool get hasUsableGeometry =>
      corners.length == 4 && frameSize.width > 0 && frameSize.height > 0;

  double get estimatedCropSide {
    if (!hasUsableGeometry) return 0;
    final edges = <double>[];
    for (var index = 0; index < corners.length; index++) {
      final current = corners[index];
      final next = corners[(index + 1) % corners.length];
      edges.add(
        math.sqrt(
          math.pow(current.dx - next.dx, 2) + math.pow(current.dy - next.dy, 2),
        ),
      );
    }
    return edges.reduce((left, right) => left + right) / edges.length * 1.30;
  }

  double get quality {
    if (frame == null ||
        corners.length != 4 ||
        frameSize.width <= 0 ||
        frameSize.height <= 0) {
      return 0;
    }
    final edges = <double>[];
    for (var index = 0; index < corners.length; index++) {
      final current = corners[index];
      final next = corners[(index + 1) % corners.length];
      edges.add(
        math.sqrt(
          math.pow(current.dx - next.dx, 2) + math.pow(current.dy - next.dy, 2),
        ),
      );
    }
    final shortest = edges.reduce(math.min);
    final longest = edges.reduce(math.max);
    if (shortest <= 0 || longest <= 0) return 0;

    var twiceArea = 0.0;
    for (var index = 0; index < corners.length; index++) {
      final current = corners[index];
      final next = corners[(index + 1) % corners.length];
      twiceArea += current.dx * next.dy - next.dx * current.dy;
    }
    final coverage = twiceArea.abs() / 2 / (frameSize.width * frameSize.height);
    final edgeBalance = shortest / longest;
    final detailDensity = frame!.length / (frameSize.width * frameSize.height);

    // Prefer a larger, less skewed QR. For otherwise similar frames, JPEG byte
    // density is a useful tie-breaker because an in-focus image retains more
    // detail than a blurred one at the plugin's fixed compression quality.
    return coverage.clamp(0, 1) * 4 +
        edgeBalance.clamp(0, 1) +
        (detailDensity / 0.25).clamp(0, 1) * 0.35;
  }
}
