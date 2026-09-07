import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:crypto/crypto.dart';

import '../models/scan_response.dart';

const diagnosticPreview = bool.fromEnvironment('QRGUARD_DIAGNOSTIC_PREVIEW');

/// Exact HTTP image inputs, retained only in the active preview result route.
/// Images contain recoverable QR tokens: never upload this archive publicly.
Uint8List buildPreviewDiagnostics(ScanResponse scan, List<Uint8List> frames) {
  if (frames.length > 5 ||
      frames.fold<int>(0, (sum, frame) => sum + frame.length) >
          25 * 1024 * 1024) {
    throw StateError('Diagnostic images exceed the export limit.');
  }
  final archive = Archive();
  final files = <Map<String, Object>>[];
  for (var i = 0; i < frames.length; i++) {
    final frame = frames[i];
    final extension = frame.length >= 2 && frame[0] == 0xff && frame[1] == 0xd8
        ? 'jpg'
        : 'png';
    final name = 'submitted-frame-${i + 1}.$extension';
    archive.addFile(ArchiveFile(name, frame.length, frame));
    files.add({
      'file': name,
      'bytes': frame.length,
      'sha256': sha256.convert(frame).toString(),
    });
  }
  final scores = scan.branchScores;
  final metadata = utf8.encode(
    const JsonEncoder.withIndent('  ').convert({
      'schema': 'qrguard-attendance-preview-v1',
      'build': '8014-preview',
    'capture_pipeline': 'synchronized_decoded_frame_motion_gate_v3',
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'privacy': 'Images contain recoverable QR content. Share privately only.',
      'image_kind': 'exact_http_inputs_not_server_intermediate_crops',
      'payload_sha256': scan.payload == null
          ? null
          : sha256.convert(utf8.encode(scan.payload!)).toString(),
      'payload_type': scan.payloadType,
      'image_source': scores.imageSource,
      'verdict': scan.verdict.name,
      'risk_score': scan.riskScore,
      'partial_analysis': scan.partialAnalysis,
      'structural_status': scores.structuralStatus.name,
      'structural_raw_type': scores.structuralRawType,
      'p_structural_raw': scores.pStructuralRaw,
      'structural_method': scores.structuralMethod,
      'module_count': scores.structuralModuleCount,
      'min_module_pixels': scores.structuralMinModulePixels,
      'attendance_checks': scores.attendanceChecks,
      'timings_ms': scan.timingsMs,
      'files': files,
    }),
  );
  archive.addFile(ArchiveFile('diagnostics.json', metadata.length, metadata));
  return Uint8List.fromList(ZipEncoder().encode(archive));
}
