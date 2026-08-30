/// Offline evidence queue used only by the dedicated Structural capture APK.
///
/// The queue stores the exact app-produced QR crop and SHA-256 identifiers. Raw
/// decoded payload text is deliberately never persisted or placed in an export.
library;

import 'dart:convert';
import 'dart:math';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';

const bool offlineCaptureEnabled = bool.fromEnvironment(
  'QRGUARD_OFFLINE_CAPTURE',
  defaultValue: false,
);

const _planAsset = 'assets/capture/offline_capture_plan.json';
const _collector = 'qrguard_android_offline_capture';
const _schemaVersion = 1;
const _currentCasePreference = 'offline_capture_current_case';
const _sha256Pattern = r'^[0-9a-f]{64}$';
const _sources = {'gallery', 'camera'};
const _maxCropBytes = 8 * 1024 * 1024;
const _maxUnexportedCropBytes = 96 * 1024 * 1024;

class OfflineCaptureException implements Exception {
  const OfflineCaptureException(this.message);

  final String message;

  @override
  String toString() => message;
}

class OfflineCaptureCase {
  const OfflineCaptureCase({
    required this.caseId,
    required this.captureNumber,
    required this.label,
    required this.qualityCondition,
    required this.qualitySeverity,
    required this.conditionOrdinal,
    required this.pairedGroupSha256,
    required this.physicalQrSha256,
    required this.recommendedMedium,
    required this.conditionInstruction,
    required this.groundTruthInstruction,
    required this.attackProvenanceRequired,
    required this.manipulationProvenanceRequired,
    required this.defaultAttackMethod,
    required this.defaultAttackReferenceSha256,
    required this.defaultManipulationMethod,
    required this.expectedPayloadSha256,
    required this.galleryRequiredForTest,
    required this.completedSources,
  });

  factory OfflineCaptureCase.fromJson(Map<String, dynamic> json) =>
      OfflineCaptureCase(
        caseId: json['case_id'] as String,
        captureNumber: json['capture_number'] as int? ?? 0,
        label: json['label'] as String,
        qualityCondition: json['quality_condition'] as String,
        qualitySeverity: json['quality_severity'] as String,
        conditionOrdinal: json['condition_ordinal'] as int,
        pairedGroupSha256: json['paired_group_sha256'] as String,
        physicalQrSha256: json['physical_qr_sha256'] as String,
        recommendedMedium: json['recommended_medium'] as String,
        conditionInstruction: json['condition_instruction'] as String,
        groundTruthInstruction: json['ground_truth_instruction'] as String,
        attackProvenanceRequired:
            json['attack_provenance_required'] as bool? ?? false,
        manipulationProvenanceRequired:
            json['manipulation_provenance_required'] as bool? ?? false,
        defaultAttackMethod: json['default_attack_method'] as String? ?? 'none',
        defaultAttackReferenceSha256:
            json['default_attack_reference_sha256'] as String? ?? '',
        defaultManipulationMethod:
            json['default_manipulation_method'] as String? ?? 'none',
        expectedPayloadSha256: json['expected_payload_sha256'] as String? ?? '',
        galleryRequiredForTest:
            json['gallery_required_for_test'] as bool? ?? false,
        completedSources: Set<String>.unmodifiable(
          (json['completed_sources'] as List<dynamic>? ?? const []).map(
            (value) => value as String,
          ),
        ),
      );

  final String caseId;
  final int captureNumber;
  final String label;
  final String qualityCondition;
  final String qualitySeverity;
  final int conditionOrdinal;
  final String pairedGroupSha256;
  final String physicalQrSha256;
  final String recommendedMedium;
  final String conditionInstruction;
  final String groundTruthInstruction;
  final bool attackProvenanceRequired;
  final bool manipulationProvenanceRequired;
  final String defaultAttackMethod;
  final String defaultAttackReferenceSha256;
  final String defaultManipulationMethod;
  final String expectedPayloadSha256;
  final bool galleryRequiredForTest;
  final Set<String> completedSources;

  bool get completedOnDesktop => completedSources.containsAll(_sources);

  bool matchesExpectedPayload(String payload) {
    final payloadHash = sha256.convert(utf8.encode(payload.trim())).toString();
    return expectedPayloadSha256.isNotEmpty &&
        payloadHash == expectedPayloadSha256;
  }

  String get shortDescription =>
      '${captureNumber > 0 ? '#$captureNumber · ' : ''}'
      '$label / $qualityCondition / $qualitySeverity';
}

class OfflineCapturePlan {
  const OfflineCapturePlan({
    required this.campaignId,
    required this.initialCaseId,
    required this.deviceModel,
    required this.environment,
    required this.maxUnexportedSessions,
    required this.allowedAttackMethods,
    required this.allowedManipulationMethods,
    required this.cases,
  });

  factory OfflineCapturePlan.fromJson(Map<String, dynamic> json) {
    if (json['schema_version'] != _schemaVersion) {
      throw const OfflineCaptureException(
        'The bundled offline capture plan has an unsupported schema.',
      );
    }
    final defaults = json['capture_defaults'] as Map<String, dynamic>;
    final cases = (json['cases'] as List<dynamic>)
        .map(
          (value) => OfflineCaptureCase.fromJson(
            Map<String, dynamic>.from(value as Map),
          ),
        )
        .toList(growable: false);
    if (cases.isEmpty) {
      throw const OfflineCaptureException('The offline capture plan is empty.');
    }
    if (cases.any(
      (item) => !RegExp(_sha256Pattern).hasMatch(item.expectedPayloadSha256),
    )) {
      throw const OfflineCaptureException(
        'The offline capture plan is missing its QR reference lock.',
      );
    }
    return OfflineCapturePlan(
      campaignId: json['campaign_id'] as String,
      initialCaseId: json['initial_case_id'] as String,
      deviceModel: defaults['device_model'] as String,
      environment: defaults['environment'] as String,
      maxUnexportedSessions: defaults['max_unexported_sessions'] as int,
      allowedAttackMethods: List<String>.unmodifiable(
        (json['allowed_attack_methods'] as List<dynamic>).cast<String>(),
      ),
      allowedManipulationMethods: List<String>.unmodifiable(
        (json['allowed_manipulation_methods'] as List<dynamic>).cast<String>(),
      ),
      cases: List<OfflineCaptureCase>.unmodifiable(cases),
    );
  }

  final String campaignId;
  final String initialCaseId;
  final String deviceModel;
  final String environment;
  final int maxUnexportedSessions;
  final List<String> allowedAttackMethods;
  final List<String> allowedManipulationMethods;
  final List<OfflineCaptureCase> cases;

  OfflineCaptureCase caseById(String caseId) => cases.firstWhere(
    (item) => item.caseId == caseId,
    orElse: () => throw OfflineCaptureException('Unknown case: $caseId'),
  );
}

class OfflineCaseState {
  const OfflineCaseState({
    required this.galleryCaptured,
    required this.cameraCaptured,
    required this.galleryRequiredForTest,
    required this.localSources,
  });

  final bool galleryCaptured;
  final bool cameraCaptured;
  final bool galleryRequiredForTest;
  final Set<String> localSources;

  bool get complete =>
      cameraCaptured && (!galleryRequiredForTest || galleryCaptured);
  bool captured(String source) => switch (source) {
    'gallery' => galleryCaptured,
    'camera' => cameraCaptured,
    _ => false,
  };
  bool storedLocally(String source) => localSources.contains(source);
}

class OfflineQueueSummary {
  const OfflineQueueSummary({
    required this.unexportedSessions,
    required this.exportedSessions,
    required this.completeLocalPairs,
  });

  final int unexportedSessions;
  final int exportedSessions;
  final int completeLocalPairs;
}

class OfflineExportBundle {
  const OfflineExportBundle({
    required this.filename,
    required this.bytes,
    required this.sessionIds,
  });

  final String filename;
  final Uint8List bytes;
  final List<String> sessionIds;
}

class OfflineCaptureService {
  OfflineCaptureService._(this.plan, this._database);

  static const MethodChannel _exportChannel = MethodChannel(
    'com.osswt.qrguard/offline_capture',
  );

  final OfflineCapturePlan plan;
  final Database _database;

  static Future<OfflineCaptureService> open() async {
    final raw = await rootBundle.loadString(_planAsset);
    final plan = OfflineCapturePlan.fromJson(
      Map<String, dynamic>.from(jsonDecode(raw) as Map),
    );
    final database = await openDatabase(
      'qrguard_offline_capture_repair_v2.db',
      version: 1,
      onCreate: (db, _) async {
        await db.execute('''
          CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            image_source TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            crop_png BLOB NOT NULL,
            exported_at TEXT,
            UNIQUE(case_id, image_source)
          )
        ''');
        await db.execute(
          'CREATE INDEX sessions_exported_idx ON sessions(exported_at)',
        );
      },
    );
    return OfflineCaptureService._(plan, database);
  }

  Future<OfflineCaptureCase> currentCase() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_currentCasePreference);
    if (saved != null) {
      try {
        return plan.caseById(saved);
      } on OfflineCaptureException {
        // A rebuilt plan may no longer contain a previously selected case.
      }
    }
    return plan.caseById(plan.initialCaseId);
  }

  Future<void> setCurrentCase(String caseId) async {
    plan.caseById(caseId);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_currentCasePreference, caseId);
  }

  Future<OfflineCaseState> stateForCase(OfflineCaptureCase captureCase) async {
    final rows = await _database.query(
      'sessions',
      columns: const ['image_source'],
      where: 'case_id = ?',
      whereArgs: [captureCase.caseId],
    );
    final sources = {
      ...captureCase.completedSources,
      for (final row in rows) row['image_source']! as String,
    };
    final localSources = {
      for (final row in rows) row['image_source']! as String,
    };
    return OfflineCaseState(
      galleryCaptured: sources.contains('gallery'),
      cameraCaptured: sources.contains('camera'),
      galleryRequiredForTest: captureCase.galleryRequiredForTest,
      localSources: Set<String>.unmodifiable(localSources),
    );
  }

  Future<void> discardLocalEvidence({
    required OfflineCaptureCase captureCase,
    required String imageSource,
  }) async {
    if (!_sources.contains(imageSource)) {
      throw const OfflineCaptureException('Invalid capture source.');
    }
    final deleted = await _database.delete(
      'sessions',
      where: 'case_id = ? AND image_source = ?',
      whereArgs: [captureCase.caseId, imageSource],
    );
    if (deleted == 0) {
      throw OfflineCaptureException(
        '${captureCase.caseId} has no local $imageSource evidence to discard.',
      );
    }
  }

  Future<OfflineQueueSummary> summary() async {
    final rows = await _database.rawQuery('''
      SELECT
        SUM(CASE WHEN exported_at IS NULL THEN 1 ELSE 0 END) AS pending,
        SUM(CASE WHEN exported_at IS NOT NULL THEN 1 ELSE 0 END) AS exported
      FROM sessions
    ''');
    final pairRows = await _database.rawQuery('''
      SELECT case_id FROM sessions
      GROUP BY case_id HAVING COUNT(DISTINCT image_source) = 2
    ''');
    return OfflineQueueSummary(
      unexportedSessions: (rows.single['pending'] as int?) ?? 0,
      exportedSessions: (rows.single['exported'] as int?) ?? 0,
      completeLocalPairs: pairRows.length,
    );
  }

  Future<void> saveEvidence({
    required OfflineCaptureCase captureCase,
    required String imageSource,
    required String payload,
    required Uint8List cropPng,
    String attackMethod = 'none',
    String attackReferenceSha256 = '',
    String manipulationMethod = 'none',
    String? medium,
  }) async {
    if (!_sources.contains(imageSource)) {
      throw const OfflineCaptureException('Invalid capture source.');
    }
    final trimmedPayload = payload.trim();
    if (trimmedPayload.isEmpty) {
      throw const OfflineCaptureException('The QR payload is empty.');
    }
    final payloadHash = sha256.convert(utf8.encode(trimmedPayload)).toString();
    if (payloadHash != captureCase.expectedPayloadSha256) {
      throw OfflineCaptureException(
        'Wrong QR for #${captureCase.captureNumber} / ${captureCase.caseId}. '
        'Show the matching numbered repair PNG and scan again.',
      );
    }
    final decoded = img.decodeImage(cropPng);
    if (cropPng.isEmpty || cropPng.length > _maxCropBytes) {
      throw const OfflineCaptureException(
        'The exact QR crop exceeds the safe offline queue size.',
      );
    }
    if (decoded == null || decoded.width < 24 || decoded.height < 24) {
      throw const OfflineCaptureException(
        'The app could not create a usable exact QR crop.',
      );
    }
    final normalizedAttack = attackMethod.trim().toLowerCase();
    final normalizedAttackHash = attackReferenceSha256.trim().toLowerCase();
    final normalizedManipulation = manipulationMethod.trim().toLowerCase();
    if (captureCase.attackProvenanceRequired &&
        (!plan.allowedAttackMethods.contains(normalizedAttack) ||
            !RegExp(_sha256Pattern).hasMatch(normalizedAttackHash))) {
      throw const OfflineCaptureException(
        'This adversarial case needs a verified attack method and SHA-256.',
      );
    }
    if (captureCase.manipulationProvenanceRequired &&
        !plan.allowedManipulationMethods.contains(normalizedManipulation)) {
      throw const OfflineCaptureException(
        'This tampered case needs a documented manipulation method.',
      );
    }

    final capturedAt = DateTime.now().toUtc();
    final cropHash = sha256.convert(cropPng).toString();
    final sessionId = _secureSessionId();
    final metadata = <String, dynamic>{
      'offline_capture_schema_version': _schemaVersion,
      'collector': _collector,
      'offline_session_id': sessionId,
      'captured_at': capturedAt.toIso8601String(),
      'campaign_id': plan.campaignId,
      'campaign_case_id': captureCase.caseId,
      'ground_truth': captureCase.label,
      'payload_sha256': payloadHash,
      'payload_hash_source': 'on_device_mlkit_decode',
      'raw_payload_stored': false,
      'paired_group_sha256': captureCase.pairedGroupSha256,
      'physical_qr_sha256': captureCase.physicalQrSha256,
      'image_source': imageSource,
      'quality_condition': captureCase.qualityCondition,
      'quality_severity': captureCase.qualitySeverity,
      'selected_frame_index': 0,
      'device_model': plan.deviceModel,
      'medium': (medium ?? captureCase.recommendedMedium).trim(),
      'environment': plan.environment,
      'attack_method': captureCase.attackProvenanceRequired
          ? normalizedAttack
          : 'none',
      'attack_reference_sha256': captureCase.attackProvenanceRequired
          ? normalizedAttackHash
          : '',
      'manipulation_method': captureCase.manipulationProvenanceRequired
          ? normalizedManipulation
          : 'none',
      'image_sizes': [
        [decoded.width, decoded.height],
      ],
      'crop_sha256': cropHash,
      'trusted_analysis_pending': true,
    };
    final metadataJson = const JsonEncoder.withIndent('  ').convert(metadata);

    await _database.transaction((transaction) async {
      final pending =
          Sqflite.firstIntValue(
            await transaction.rawQuery(
              'SELECT COUNT(*) FROM sessions WHERE exported_at IS NULL',
            ),
          ) ??
          0;
      if (pending >= plan.maxUnexportedSessions) {
        throw OfflineCaptureException(
          'Export the current $pending queued sessions before collecting more.',
        );
      }
      final pendingBytes =
          Sqflite.firstIntValue(
            await transaction.rawQuery(
              'SELECT COALESCE(SUM(LENGTH(crop_png)), 0) FROM sessions '
              'WHERE exported_at IS NULL',
            ),
          ) ??
          0;
      if (pendingBytes + cropPng.length > _maxUnexportedCropBytes) {
        throw const OfflineCaptureException(
          'The offline queue reached its 96 MB safety limit. Export it before '
          'collecting more.',
        );
      }
      final existing = await transaction.query(
        'sessions',
        columns: const ['image_source', 'payload_sha256', 'metadata_json'],
        where: 'case_id = ?',
        whereArgs: [captureCase.caseId],
      );
      if (captureCase.completedSources.contains(imageSource) ||
          existing.any((row) => row['image_source'] == imageSource)) {
        throw OfflineCaptureException(
          '${captureCase.caseId} already has a $imageSource session.',
        );
      }
      if (existing.any((row) => row['payload_sha256'] != payloadHash)) {
        throw const OfflineCaptureException(
          'Gallery and Camera decoded different payloads. Do not save this pair.',
        );
      }
      for (final row in existing) {
        final other = Map<String, dynamic>.from(
          jsonDecode(row['metadata_json']! as String) as Map,
        );
        for (final key in const [
          'attack_method',
          'attack_reference_sha256',
          'manipulation_method',
        ]) {
          if (other[key] != metadata[key]) {
            throw const OfflineCaptureException(
              'Gallery and Camera provenance differs. Do not save this pair.',
            );
          }
        }
      }
      await transaction.insert('sessions', {
        'session_id': sessionId,
        'case_id': captureCase.caseId,
        'image_source': imageSource,
        'payload_sha256': payloadHash,
        'captured_at': capturedAt.toIso8601String(),
        'metadata_json': metadataJson,
        'crop_png': cropPng,
        'exported_at': null,
      });
    });
  }

  Future<OfflineCaptureCase?> nextIncompleteAfter(String caseId) async {
    final start = plan.cases.indexWhere((item) => item.caseId == caseId);
    for (var offset = 1; offset <= plan.cases.length; offset++) {
      final candidate = plan.cases[(start + offset) % plan.cases.length];
      if (!(await stateForCase(candidate)).complete) return candidate;
    }
    return null;
  }

  Future<OfflineCaptureCase?> nextMissingSourceAfter(
    String caseId,
    String imageSource,
  ) async {
    if (!_sources.contains(imageSource)) {
      throw const OfflineCaptureException('Invalid capture source.');
    }
    final start = plan.cases.indexWhere((item) => item.caseId == caseId);
    for (var offset = 1; offset <= plan.cases.length; offset++) {
      final candidate = plan.cases[(start + offset) % plan.cases.length];
      if (!(await stateForCase(candidate)).captured(imageSource)) {
        return candidate;
      }
    }
    return null;
  }

  Future<OfflineExportBundle> buildExport() async {
    final rows = await _database.query(
      'sessions',
      where: 'exported_at IS NULL',
      orderBy: 'captured_at, case_id, image_source',
    );
    if (rows.isEmpty) {
      throw const OfflineCaptureException('There are no unexported sessions.');
    }

    final archive = Archive();
    final manifestSessions = <Map<String, dynamic>>[];
    final sessionIds = <String>[];
    for (final row in rows) {
      final sessionId = row['session_id']! as String;
      final caseId = row['case_id']! as String;
      final source = row['image_source']! as String;
      final crop = row['crop_png']! as Uint8List;
      final metadataText = row['metadata_json']! as String;
      final metadataBytes = Uint8List.fromList(utf8.encode(metadataText));
      final base = 'sessions/$caseId/$source/$sessionId';
      archive.addFile(ArchiveFile('$base/crop_00.png', crop.length, crop));
      archive.addFile(
        ArchiveFile('$base/metadata.json', metadataBytes.length, metadataBytes),
      );
      manifestSessions.add({
        'offline_session_id': sessionId,
        'case_id': caseId,
        'image_source': source,
        'base_path': base,
        'crop_sha256': sha256.convert(crop).toString(),
        'metadata_sha256': sha256.convert(metadataBytes).toString(),
      });
      sessionIds.add(sessionId);
    }
    final exportedAt = DateTime.now().toUtc();
    final manifest = <String, dynamic>{
      'offline_capture_archive_schema_version': _schemaVersion,
      'collector': _collector,
      'campaign_id': plan.campaignId,
      'exported_at': exportedAt.toIso8601String(),
      'session_count': rows.length,
      'raw_payload_stored': false,
      'sessions': manifestSessions,
    };
    final manifestBytes = Uint8List.fromList(
      utf8.encode(const JsonEncoder.withIndent('  ').convert(manifest)),
    );
    archive.addFile(
      ArchiveFile('archive_manifest.json', manifestBytes.length, manifestBytes),
    );
    final stamp = exportedAt
        .toIso8601String()
        .replaceAll(RegExp(r'[-:]'), '')
        .replaceAll(RegExp(r'\..+$'), 'Z');
    return OfflineExportBundle(
      filename: 'QRGuard_Offline_${plan.campaignId}_$stamp.zip',
      bytes: ZipEncoder().encodeBytes(archive),
      sessionIds: List<String>.unmodifiable(sessionIds),
    );
  }

  Future<String> exportPendingToDownloads() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      throw const OfflineCaptureException(
        'Offline ZIP export is available only in the Android capture APK.',
      );
    }
    final bundle = await buildExport();
    final location = await _exportChannel.invokeMethod<String>('saveZip', {
      'filename': bundle.filename,
      'bytes': bundle.bytes,
    });
    if (location == null || location.isEmpty) {
      throw const OfflineCaptureException('Android did not save the ZIP.');
    }
    final exportedAt = DateTime.now().toUtc().toIso8601String();
    final placeholders = List.filled(bundle.sessionIds.length, '?').join(',');
    await _database.rawUpdate(
      'UPDATE sessions SET exported_at = ? WHERE session_id IN ($placeholders)',
      [exportedAt, ...bundle.sessionIds],
    );
    return location;
  }

  Future<void> close() => _database.close();
}

String _secureSessionId() {
  final random = Random.secure();
  return List.generate(
    16,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}
