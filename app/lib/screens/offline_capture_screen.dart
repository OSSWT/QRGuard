/// Dedicated, network-free Structural evidence collector.
///
/// This screen is compiled into the side-by-side capture APK with
/// `--dart-define=QRGUARD_OFFLINE_CAPTURE=true`. It reuses QRGuard's exact
/// camera/gallery decoding and rectification path, then queues small ZIP batches
/// for strict desktop import. It never calls the analysis backend.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../services/offline_capture_service.dart';
import '../theme.dart';
import 'analysing_screen.dart';

class OfflineCaptureScreen extends StatefulWidget {
  const OfflineCaptureScreen({super.key, required this.service});

  final OfflineCaptureService service;

  @override
  State<OfflineCaptureScreen> createState() => _OfflineCaptureScreenState();
}

class _OfflineCaptureScreenState extends State<OfflineCaptureScreen>
    with WidgetsBindingObserver {
  final _scanner = MobileScannerController(
    autoStart: false,
    detectionSpeed: DetectionSpeed.normal,
    detectionTimeoutMs: 150,
    cameraResolution: const Size(1280, 720),
    lensType: CameraLensType.any,
    formats: const [BarcodeFormat.qrCode],
    returnImage: true,
    autoZoom: true,
  );
  final _picker = ImagePicker();
  final _attackHash = TextEditingController();
  final _medium = TextEditingController();

  OfflineCaptureCase? _captureCase;
  OfflineCaseState? _caseState;
  OfflineQueueSummary? _summary;
  String _attackMethod = 'none';
  String _manipulationMethod = 'none';
  String? _pendingSource;
  String? _pendingPayload;
  Uint8List? _pendingCrop;
  bool _cameraArmed = false;
  bool _busy = true;
  String? _message;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_load());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) unawaited(_disarmCamera());
  }

  Future<void> _load() async {
    try {
      final captureCase = await widget.service.currentCase();
      await _select(captureCase, persist: false);
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _refresh() async {
    final captureCase = _captureCase;
    if (captureCase == null) return;
    final values = await Future.wait<Object>([
      widget.service.stateForCase(captureCase),
      widget.service.summary(),
    ]);
    if (!mounted) return;
    setState(() {
      _caseState = values[0] as OfflineCaseState;
      _summary = values[1] as OfflineQueueSummary;
    });
  }

  Future<void> _select(
    OfflineCaptureCase captureCase, {
    bool persist = true,
  }) async {
    await _disarmCamera();
    if (persist) await widget.service.setCurrentCase(captureCase.caseId);
    final state = await widget.service.stateForCase(captureCase);
    final summary = await widget.service.summary();
    if (!mounted) return;
    setState(() {
      _captureCase = captureCase;
      _caseState = state;
      _summary = summary;
      _pendingSource = null;
      _pendingPayload = null;
      _pendingCrop = null;
      _attackMethod = captureCase.attackProvenanceRequired
          ? captureCase.defaultAttackMethod
          : 'none';
      _manipulationMethod = captureCase.manipulationProvenanceRequired
          ? captureCase.defaultManipulationMethod
          : 'none';
      _attackHash.text = captureCase.defaultAttackReferenceSha256;
      _medium.text = captureCase.recommendedMedium;
      _message = null;
    });
  }

  Future<void> _chooseCase() async {
    final selected = await showSearch<OfflineCaptureCase?>(
      context: context,
      delegate: _CaseSearchDelegate(
        cases: widget.service.plan.cases,
        selectedCaseId: _captureCase?.caseId,
      ),
    );
    if (selected != null && mounted) await _select(selected);
  }

  Future<void> _armCamera() async {
    final captureCase = _captureCase;
    final state = _caseState;
    if (captureCase == null || state == null || state.cameraCaptured) return;
    setState(() {
      _cameraArmed = true;
      _message =
          'Aim at exactly one QR code. The first decoded crop is held for review.';
    });
    try {
      await _scanner.start();
    } catch (error) {
      if (mounted) {
        setState(() {
          _cameraArmed = false;
          _message = 'Could not start the camera: ${_friendly(error)}';
        });
      }
    }
  }

  Future<void> _disarmCamera() async {
    if (!_cameraArmed) return;
    try {
      await _scanner.stop();
    } catch (_) {
      // Stopping an already-paused camera is harmless.
    }
    if (mounted) setState(() => _cameraArmed = false);
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (!_cameraArmed || _busy) return;
    final readable = <String, Barcode>{};
    for (final barcode in capture.barcodes) {
      final payload = (barcode.rawValue ?? '').trim();
      if (payload.isNotEmpty) readable.putIfAbsent(payload, () => barcode);
    }
    if (readable.length != 1 || capture.image == null) {
      if (mounted && readable.length > 1) {
        setState(
          () => _message = 'Multiple QR codes detected. Keep only one in view.',
        );
      }
      return;
    }
    final barcode = readable.values.single;
    setState(() => _busy = true);
    await _disarmCamera();
    await _prepareEvidence(
      payload: barcode.rawValue!.trim(),
      frame: capture.image!,
      corners: barcode.corners,
      frameSize: capture.size,
      source: 'camera',
      normalizeCameraColor: true,
    );
  }

  Future<void> _pickGallery() async {
    final state = _caseState;
    if (_busy || state == null || state.galleryCaptured) return;
    if (!state.galleryRequiredForTest) {
      setState(
        () => _message = 'Gallery is not required for this non-Test case.',
      );
      return;
    }
    await _disarmCamera();
    final selected = await _picker.pickImage(source: ImageSource.gallery);
    if (selected == null) return;
    setState(() => _busy = true);
    try {
      final capture = await _scanner.analyzeImage(selected.path);
      final readable = <String, Barcode>{};
      for (final barcode in capture?.barcodes ?? const <Barcode>[]) {
        final payload = (barcode.rawValue ?? '').trim();
        if (payload.isNotEmpty) readable.putIfAbsent(payload, () => barcode);
      }
      if (readable.length != 1) {
        throw OfflineCaptureException(
          readable.isEmpty
              ? 'No readable QR code was found in that image.'
              : 'That image contains multiple QR codes.',
        );
      }
      final barcode = readable.values.single;
      await _prepareEvidence(
        payload: barcode.rawValue!.trim(),
        frame: capture?.image ?? await selected.readAsBytes(),
        corners: barcode.corners,
        frameSize: capture?.size ?? Size.zero,
        source: 'gallery',
        normalizeCameraColor: false,
      );
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _message = _friendly(error);
        });
      }
    }
  }

  Future<void> _prepareEvidence({
    required String payload,
    required Uint8List frame,
    required List<Offset> corners,
    required Size frameSize,
    required String source,
    required bool normalizeCameraColor,
  }) async {
    try {
      final captureCase = _captureCase;
      if (captureCase == null || !captureCase.matchesExpectedPayload(payload)) {
        throw OfflineCaptureException(
          captureCase == null
              ? 'No repair case is selected.'
              : 'Wrong QR for #${captureCase.captureNumber} / '
                    '${captureCase.caseId}. Show the matching numbered repair '
                    'PNG and scan again.',
        );
      }
      final crop = await compute(prepareFirstUsableCropInBackground, [
        CropRequest(
          frame: frame,
          cornerCoordinates: [
            for (final corner in corners) ...[corner.dx, corner.dy],
          ],
          frameWidth: frameSize.width,
          frameHeight: frameSize.height,
          normalizeCameraColor: normalizeCameraColor,
        ),
      ]).timeout(const Duration(seconds: 8));
      if (crop == null || crop.isEmpty) {
        throw const OfflineCaptureException(
          'QRGuard could not create a trustworthy exact crop. Capture it again.',
        );
      }
      if (!mounted) return;
      setState(() {
        _pendingSource = source;
        _pendingPayload = payload;
        _pendingCrop = crop;
        _busy = false;
        _message =
            'Review the exact app crop before saving it to the offline queue.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _message = _friendly(error);
      });
    }
  }

  Future<void> _savePending() async {
    final captureCase = _captureCase;
    final source = _pendingSource;
    final payload = _pendingPayload;
    final crop = _pendingCrop;
    if (_busy ||
        captureCase == null ||
        source == null ||
        payload == null ||
        crop == null) {
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.service.saveEvidence(
        captureCase: captureCase,
        imageSource: source,
        payload: payload,
        cropPng: crop,
        attackMethod: _attackMethod,
        attackReferenceSha256: _attackHash.text,
        manipulationMethod: _manipulationMethod,
        medium: _medium.text,
      );
      final state = await widget.service.stateForCase(captureCase);
      final summary = await widget.service.summary();
      if (!mounted) return;
      setState(() {
        _caseState = state;
        _summary = summary;
        _pendingSource = null;
        _pendingPayload = null;
        _pendingCrop = null;
        _message = '$source evidence saved. Raw payload text was discarded.';
      });
      if (state.complete || source == 'camera') {
        final next = state.complete
            ? await widget.service.nextIncompleteAfter(captureCase.caseId)
            : await widget.service.nextMissingSourceAfter(
                captureCase.caseId,
                'camera',
              );
        if (next != null && mounted) {
          await _select(next);
          if (mounted) {
            setState(() {
              _message = source == 'camera'
                  ? captureCase.galleryRequiredForTest
                        ? '${captureCase.caseId} Camera saved. Next Camera case selected; Test Gallery can be added later.'
                        : '${captureCase.caseId} Camera complete. Gallery is not required; next case selected.'
                  : '${captureCase.caseId} Test pair complete. Next case selected.';
            });
          }
        }
      }
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = 'Building a bounded evidence ZIP…';
    });
    try {
      final location = await widget.service.exportPendingToDownloads();
      await _refresh();
      if (mounted) {
        setState(() {
          _message = 'ZIP saved to Android Downloads/QRGuard. URI: $location';
        });
      }
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _discardStored(String source) async {
    final captureCase = _captureCase;
    if (_busy || captureCase == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Discard local $source evidence?'),
        content: Text(
          'This removes ${captureCase.caseId} / $source from the phone queue. '
          'An already exported ZIP is not deleted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Keep evidence'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Discard local copy'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await widget.service.discardLocalEvidence(
        captureCase: captureCase,
        imageSource: source,
      );
      await _refresh();
      if (mounted) {
        setState(
          () => _message = '$source evidence discarded. Capture it again.',
        );
      }
    } catch (error) {
      if (mounted) setState(() => _message = _friendly(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _discardPreview() {
    setState(() {
      _pendingSource = null;
      _pendingPayload = null;
      _pendingCrop = null;
      _message = 'Preview discarded. Nothing was stored.';
    });
  }

  String _friendly(Object error) => switch (error) {
    OfflineCaptureException() => error.message,
    TimeoutException() => 'Image preparation timed out. Capture it again.',
    PlatformException() =>
      error.message ?? 'Android could not save the export.',
    _ => 'Offline capture could not continue. Try again.',
  };

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _attackHash.dispose();
    _medium.dispose();
    _scanner.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final captureCase = _captureCase;
    final state = _caseState;
    final summary = _summary;
    return Scaffold(
      appBar: AppBar(
        title: const Text('QRGuard Offline Capture'),
        actions: [
          IconButton(
            tooltip: 'Export pending ZIP',
            onPressed: _busy || (summary?.unexportedSessions ?? 0) == 0
                ? null
                : _export,
            icon: const Icon(Icons.archive_outlined),
          ),
        ],
      ),
      body: SafeArea(
        child: captureCase == null || state == null
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 32),
                children: [
                  _OfflineWarning(campaignId: widget.service.plan.campaignId),
                  const SizedBox(height: 12),
                  _CaseCard(
                    captureCase: captureCase,
                    state: state,
                    onChoose: _busy ? null : _chooseCase,
                    onDiscardGallery: !_busy && state.storedLocally('gallery')
                        ? () => _discardStored('gallery')
                        : null,
                    onDiscardCamera: !_busy && state.storedLocally('camera')
                        ? () => _discardStored('camera')
                        : null,
                  ),
                  const SizedBox(height: 12),
                  if (captureCase.attackProvenanceRequired) ...[
                    DropdownButtonFormField<String>(
                      initialValue: _attackMethod,
                      decoration: const InputDecoration(
                        labelText: 'Verified attack method',
                      ),
                      items: [
                        for (final value
                            in widget.service.plan.allowedAttackMethods)
                          DropdownMenuItem(value: value, child: Text(value)),
                      ],
                      onChanged: _busy
                          ? null
                          : (value) => setState(() => _attackMethod = value!),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _attackHash,
                      enabled: !_busy,
                      decoration: const InputDecoration(
                        labelText: 'Attack reference SHA-256',
                        helperText:
                            'Exactly 64 lowercase hexadecimal characters',
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  if (captureCase.manipulationProvenanceRequired) ...[
                    DropdownButtonFormField<String>(
                      initialValue: _manipulationMethod,
                      decoration: const InputDecoration(
                        labelText: 'Manipulation method',
                      ),
                      items: [
                        for (final value
                            in widget.service.plan.allowedManipulationMethods)
                          DropdownMenuItem(value: value, child: Text(value)),
                      ],
                      onChanged: _busy
                          ? null
                          : (value) =>
                                setState(() => _manipulationMethod = value!),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: _medium,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'Physical/display medium',
                    ),
                  ),
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: SizedBox(
                      height: 260,
                      child: _pendingCrop != null
                          ? Image.memory(_pendingCrop!, fit: BoxFit.contain)
                          : MobileScanner(
                              controller: _scanner,
                              onDetect: _onDetect,
                              placeholderBuilder: (context) => ColoredBox(
                                color: context.qrColors.secondarySurface,
                                child: Center(
                                  child: Icon(
                                    _cameraArmed
                                        ? Icons.qr_code_scanner_rounded
                                        : Icons.camera_alt_outlined,
                                    size: 54,
                                    color: context.qrColors.secondaryText,
                                  ),
                                ),
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (_pendingCrop == null)
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed:
                                _busy ||
                                    state.galleryCaptured ||
                                    !captureCase.galleryRequiredForTest
                                ? null
                                : _pickGallery,
                            icon: const Icon(Icons.photo_library_outlined),
                            label: Text(
                              state.galleryCaptured
                                  ? 'Gallery saved'
                                  : captureCase.galleryRequiredForTest
                                  ? 'Capture Test Gallery'
                                  : 'Gallery not required',
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: _busy || state.cameraCaptured
                                ? null
                                : _cameraArmed
                                ? _disarmCamera
                                : _armCamera,
                            icon: Icon(
                              _cameraArmed
                                  ? Icons.stop_rounded
                                  : Icons.camera_alt_rounded,
                            ),
                            label: Text(
                              state.cameraCaptured
                                  ? 'Camera saved'
                                  : _cameraArmed
                                  ? 'Stop Camera'
                                  : 'Capture Camera',
                            ),
                          ),
                        ),
                      ],
                    )
                  else
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: _busy ? null : _discardPreview,
                            child: const Text('Discard'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: _busy ? null : _savePending,
                            icon: const Icon(Icons.save_rounded),
                            label: Text('Save ${_pendingSource ?? ''}'),
                          ),
                        ),
                      ],
                    ),
                  if (_busy) ...[
                    const SizedBox(height: 12),
                    const LinearProgressIndicator(),
                  ],
                  if (_message != null) ...[
                    const SizedBox(height: 12),
                    Text(_message!, style: const TextStyle(height: 1.4)),
                  ],
                  const SizedBox(height: 14),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Offline queue',
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${summary?.unexportedSessions ?? 0} awaiting export · '
                            '${summary?.exportedSessions ?? 0} retained after export · '
                            '${summary?.completeLocalPairs ?? 0} local pairs',
                          ),
                          const SizedBox(height: 10),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.tonalIcon(
                              onPressed:
                                  _busy ||
                                      (summary?.unexportedSessions ?? 0) == 0
                                  ? null
                                  : _export,
                              icon: const Icon(Icons.download_rounded),
                              label: const Text(
                                'Export pending ZIP to Downloads',
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Exported rows remain in the app. The desktop importer never '
                            'deletes the ZIP or existing evidence automatically.',
                            style: TextStyle(fontSize: 12, height: 1.35),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _OfflineWarning extends StatelessWidget {
  const _OfflineWarning({required this.campaignId});

  final String campaignId;

  @override
  Widget build(BuildContext context) => Card(
    color: context.qrColors.warningSurface,
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.science_outlined, color: context.qrColors.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Research capture only · $campaignId. This mode stores exact app '
              'crops locally and never opens or uploads the decoded destination.',
              style: const TextStyle(height: 1.4),
            ),
          ),
        ],
      ),
    ),
  );
}

class _CaseCard extends StatelessWidget {
  const _CaseCard({
    required this.captureCase,
    required this.state,
    required this.onChoose,
    required this.onDiscardGallery,
    required this.onDiscardCamera,
  });

  final OfflineCaptureCase captureCase;
  final OfflineCaseState state;
  final VoidCallback? onChoose;
  final VoidCallback? onDiscardGallery;
  final VoidCallback? onDiscardCamera;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  captureCase.caseId,
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              TextButton.icon(
                onPressed: onChoose,
                icon: const Icon(Icons.search_rounded),
                label: const Text('Choose case'),
              ),
            ],
          ),
          Text(captureCase.shortDescription),
          const SizedBox(height: 10),
          Text(
            captureCase.conditionInstruction,
            style: const TextStyle(height: 1.35),
          ),
          const SizedBox(height: 6),
          Text(
            captureCase.groundTruthInstruction,
            style: TextStyle(
              color: context.qrColors.secondaryText,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _SourceChip(
                label: captureCase.galleryRequiredForTest
                    ? 'Gallery (Test)'
                    : 'Gallery',
                captured: state.galleryCaptured,
                isRequired: captureCase.galleryRequiredForTest,
              ),
              _SourceChip(label: 'Live Camera', captured: state.cameraCaptured),
            ],
          ),
          if (onDiscardGallery != null || onDiscardCamera != null) ...[
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              children: [
                if (onDiscardGallery != null)
                  TextButton(
                    onPressed: onDiscardGallery,
                    child: const Text('Discard local Gallery'),
                  ),
                if (onDiscardCamera != null)
                  TextButton(
                    onPressed: onDiscardCamera,
                    child: const Text('Discard local Camera'),
                  ),
              ],
            ),
          ],
        ],
      ),
    ),
  );
}

class _SourceChip extends StatelessWidget {
  const _SourceChip({
    required this.label,
    required this.captured,
    this.isRequired = true,
  });

  final String label;
  final bool captured;
  final bool isRequired;

  @override
  Widget build(BuildContext context) => Chip(
    avatar: Icon(
      captured
          ? Icons.check_circle_rounded
          : Icons.radio_button_unchecked_rounded,
      size: 18,
      color: captured ? context.qrColors.safe : context.qrColors.secondaryText,
    ),
    label: Text(
      '$label · ${captured
          ? 'done'
          : isRequired
          ? 'pending'
          : 'not required'}',
    ),
  );
}

class _CaseSearchDelegate extends SearchDelegate<OfflineCaptureCase?> {
  _CaseSearchDelegate({required this.cases, required this.selectedCaseId});

  final List<OfflineCaptureCase> cases;
  final String? selectedCaseId;

  @override
  String get searchFieldLabel => 'Case ID, label or condition';

  @override
  List<Widget>? buildActions(BuildContext context) => [
    if (query.isNotEmpty)
      IconButton(
        onPressed: () => query = '',
        icon: const Icon(Icons.clear_rounded),
      ),
  ];

  @override
  Widget? buildLeading(BuildContext context) => IconButton(
    onPressed: () => close(context, null),
    icon: const Icon(Icons.arrow_back_rounded),
  );

  @override
  Widget buildResults(BuildContext context) => _results(context);

  @override
  Widget buildSuggestions(BuildContext context) => _results(context);

  Widget _results(BuildContext context) {
    final needle = query.trim().toLowerCase();
    final matches = cases
        .where((item) {
          if (needle.isEmpty) return !item.completedOnDesktop;
          return item.caseId.toLowerCase().contains(needle) ||
              item.label.toLowerCase().contains(needle) ||
              item.qualityCondition.toLowerCase().contains(needle) ||
              item.qualitySeverity.toLowerCase().contains(needle);
        })
        .toList(growable: false);
    return ListView.builder(
      itemCount: matches.length,
      itemBuilder: (context, index) {
        final item = matches[index];
        return ListTile(
          selected: item.caseId == selectedCaseId,
          leading: Icon(
            item.completedOnDesktop ? Icons.task_alt_rounded : Icons.qr_code_2,
          ),
          title: Text(item.caseId),
          subtitle: Text(item.shortDescription),
          trailing: item.completedOnDesktop
              ? const Text('desktop complete')
              : null,
          onTap: () => close(context, item),
        );
      },
    );
  }
}
