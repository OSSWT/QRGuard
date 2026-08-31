/// Local multi-frame evidence queue for the live-camera repeatability study.
///
/// The diagnostic build stores rectified QR crops and geometry metadata. The
/// decoded payload is used only long enough to verify the selected reference;
/// exports contain its SHA-256 identifier, never the raw text.
library;

import 'dart:convert';
import 'dart:math';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;
import 'package:sqflite/sqflite.dart';

const bool diagnosticCaptureEnabled = bool.fromEnvironment(
  'QRGUARD_DIAGNOSTIC_CAPTURE',
  defaultValue: false,
);

const _planAsset = 'assets/capture/diagnostic_capture_plan.json';
const _collector = 'qrguard_android_diagnostic_capture';
const _schemaVersion = 1;
const _sha256Pattern = r'^[0-9a-f]{64}$';
const _maxCropBytes = 8 * 1024 * 1024;
const _maxPendingBytes = 160 * 1024 * 1024;

class DiagnosticCaptureException implements Exception {
  const DiagnosticCaptureException(this.message);

  final String message;

  @override
  String toString() => message;
}

class DiagnosticDistance {
  const DiagnosticDistance({
    required this.id,
    required this.label,
    required this.instruction,
  });

  factory DiagnosticDistance.fromJson(Map<String, dynamic> json) =>
      DiagnosticDistance(
        id: json['id'] as String,
        label: json['label'] as String,
        instruction: json['instruction'] as String,
      );

  final String id;
  final String label;
  final String instruction;
}

class DiagnosticCase {
  const DiagnosticCase({
    required this.caseId,
    required this.label,
    required this.groundTruth,
    required this.expectedPayloadSha256,
    required this.instruction,
  });

  factory DiagnosticCase.fromJson(Map<String, dynamic> json) => DiagnosticCase(
    caseId: json['case_id'] as String,
    label: json['label'] as String,
    groundTruth: json['ground_truth'] as String,
    expectedPayloadSha256: json['expected_payload_sha256'] as String,
    instruction: json['instruction'] as String,
  );

  final String caseId;
  final String label;
  final String groundTruth;
  final String expectedPayloadSha256;
  final String instruction;

  bool matchesExpectedPayload(String payload) =>
      sha256.convert(utf8.encode(payload.trim())).toString() ==
      expectedPayloadSha256;
}

class DiagnosticCapturePlan {
  const DiagnosticCapturePlan({
    required this.campaignId,
    required this.framesPerSession,
    required this.repeatsPerDistance,
    required this.distances,
    required this.cases,
  });

  factory DiagnosticCapturePlan.fromJson(Map<String, dynamic> json) {
    if (json['schema_version'] != _schemaVersion) {
      throw const DiagnosticCaptureException(
        'The bundled diagnostic plan has an unsupported schema.',
      );
    }
    final framesPerSession = json['frames_per_session'] as int? ?? 0;
    final repeatsPerDistance = json['repeats_per_distance'] as int? ?? 0;
    final distances = (json['distances'] as List<dynamic>? ?? const [])
        .map(
          (value) => DiagnosticDistance.fromJson(
            Map<String, dynamic>.from(value as Map),
          ),
        )
        .toList(growable: false);
    final cases = (json['cases'] as List<dynamic>? ?? const [])
        .map(
          (value) =>
              DiagnosticCase.fromJson(Map<String, dynamic>.from(value as Map)),
        )
        .toList(growable: false);
    if (framesPerSession < 3 ||
        framesPerSession > 8 ||
        repeatsPerDistance < 1 ||
        distances.isEmpty ||
        cases.isEmpty ||
        distances.map((item) => item.id).toSet().length != distances.length ||
        cases.map((item) => item.caseId).toSet().length != cases.length ||
        cases.any(
          (item) =>
              !RegExp(_sha256Pattern).hasMatch(item.expectedPayloadSha256),
        )) {
      throw const DiagnosticCaptureException(
        'The bundled diagnostic plan is incomplete or invalid.',
      );
    }
    return DiagnosticCapturePlan(
      campaignId: json['campaign_id'] as String,
      framesPerSession: framesPerSession,
      repeatsPerDistance: repeatsPerDistance,
      distances: List.unmodifiable(distances),
      cases: List.unmodifiable(cases),
    );
  }

  final String campaignId;
  final int framesPerSession;
  final int repeatsPerDistance;
  final List<DiagnosticDistance> distances;
  final List<DiagnosticCase> cases;

  int get targetSessions =>
      cases.length * distances.length * repeatsPerDistance;
}

class DiagnosticFrameEvidence {
  const DiagnosticFrameEvidence({
    required this.cropPng,
    required this.capturedAt,
    required this.frameWidth,
    required this.frameHeight,
    required this.cornerCoordinates,
  });

  final Uint8List cropPng;
  final DateTime capturedAt;
  final double frameWidth;
  final double frameHeight;
  final List<double> cornerCoordinates;
}

class DiagnosticProgress {
  const DiagnosticProgress({
    required this.completedSessions,
    required this.pendingSessions,
    required this.exportedSessions,
    required this.counts,
  });

  final int completedSessions;
  final int pendingSessions;
  final int exportedSessions;
  final Map<String, int> counts;

  int countFor(String caseId, String distance) =>
      counts['$caseId::$distance'] ?? 0;
}

class DiagnosticExportBundle {
  const DiagnosticExportBundle({
    required this.filename,
    required this.bytes,
    required this.sessionIds,
  });

  final String filename;
  final Uint8List bytes;
  final List<String> sessionIds;
}

class DiagnosticCaptureService {
  DiagnosticCaptureService._(this.plan, this._database);

  static const MethodChannel _exportChannel = MethodChannel(
    'com.osswt.qrguard/offline_capture',
  );

  final DiagnosticCapturePlan plan;
  final Database _database;

  static Future<DiagnosticCaptureService> open() async {
    final raw = await rootBundle.loadString(_planAsset);
    final plan = DiagnosticCapturePlan.fromJson(
      Map<String, dynamic>.from(jsonDecode(raw) as Map),
    );
    final database = await openDatabase(
      'qrguard_live_diagnostic_r01.db',
      version: 1,
      onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'),
      onCreate: (db, _) async {
        await db.execute('''
          CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            distance TEXT NOT NULL,
            repeat_index INTEGER NOT NULL,
            payload_sha256 TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            exported_at TEXT,
            UNIQUE(case_id, distance, repeat_index)
          )
        ''');
        await db.execute('''
          CREATE TABLE frames (
            session_id TEXT NOT NULL,
            frame_index INTEGER NOT NULL,
            crop_png BLOB NOT NULL,
            crop_sha256 TEXT NOT NULL,
            PRIMARY KEY(session_id, frame_index),
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
              ON DELETE CASCADE
          )
        ''');
        await db.execute(
          'CREATE INDEX diagnostic_exported_idx ON sessions(exported_at)',
        );
      },
    );
    return DiagnosticCaptureService._(plan, database);
  }

  Future<DiagnosticProgress> progress() async {
    final rows = await _database.rawQuery('''
      SELECT case_id, distance, COUNT(*) AS count
      FROM sessions GROUP BY case_id, distance
    ''');
    final summary = await _database.rawQuery('''
      SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN exported_at IS NULL THEN 1 ELSE 0 END) AS pending,
        SUM(CASE WHEN exported_at IS NOT NULL THEN 1 ELSE 0 END) AS exported
      FROM sessions
    ''');
    return DiagnosticProgress(
      completedSessions: (summary.single['total'] as int?) ?? 0,
      pendingSessions: (summary.single['pending'] as int?) ?? 0,
      exportedSessions: (summary.single['exported'] as int?) ?? 0,
      counts: Map.unmodifiable({
        for (final row in rows)
          '${row['case_id']}::${row['distance']}': row['count']! as int,
      }),
    );
  }

  Future<int> nextRepeatIndex({
    required DiagnosticCase captureCase,
    required DiagnosticDistance distance,
  }) async {
    final value = Sqflite.firstIntValue(
      await _database.rawQuery(
        'SELECT COALESCE(MAX(repeat_index), 0) FROM sessions '
        'WHERE case_id = ? AND distance = ?',
        [captureCase.caseId, distance.id],
      ),
    );
    return (value ?? 0) + 1;
  }

  Future<void> saveSession({
    required DiagnosticCase captureCase,
    required DiagnosticDistance distance,
    required String payload,
    required List<DiagnosticFrameEvidence> frames,
  }) async {
    if (!plan.cases.any((item) => item.caseId == captureCase.caseId) ||
        !plan.distances.any((item) => item.id == distance.id)) {
      throw const DiagnosticCaptureException('Unknown case or distance.');
    }
    if (!captureCase.matchesExpectedPayload(payload)) {
      throw DiagnosticCaptureException(
        'Wrong QR for ${captureCase.caseId}. Display the selected reference.',
      );
    }
    if (frames.length != plan.framesPerSession) {
      throw DiagnosticCaptureException(
        'A session requires exactly ${plan.framesPerSession} crops.',
      );
    }

    final decoded = <img.Image>[];
    final hashes = <String>[];
    var sessionBytes = 0;
    for (final frame in frames) {
      if (frame.cropPng.isEmpty || frame.cropPng.length > _maxCropBytes) {
        throw const DiagnosticCaptureException(
          'A crop exceeds the diagnostic queue safety limit.',
        );
      }
      final image = img.decodeImage(frame.cropPng);
      if (image == null || image.width < 24 || image.height < 24) {
        throw const DiagnosticCaptureException(
          'A frame does not contain a usable rectified QR crop.',
        );
      }
      decoded.add(image);
      hashes.add(sha256.convert(frame.cropPng).toString());
      sessionBytes += frame.cropPng.length;
    }
    if (hashes.toSet().length != hashes.length) {
      throw const DiagnosticCaptureException(
        'The burst contains duplicate frames. Capture it again.',
      );
    }

    final payloadHash = sha256.convert(utf8.encode(payload.trim())).toString();
    final capturedAt = frames.first.capturedAt.toUtc();
    final sessionId = _secureSessionId();

    await _database.transaction((transaction) async {
      final repeatIndex =
          Sqflite.firstIntValue(
            await transaction.rawQuery(
              'SELECT COALESCE(MAX(repeat_index), 0) FROM sessions '
              'WHERE case_id = ? AND distance = ?',
              [captureCase.caseId, distance.id],
            ),
          ) ??
          0;
      if (repeatIndex >= plan.repeatsPerDistance) {
        throw DiagnosticCaptureException(
          '${captureCase.caseId} / ${distance.label} already has all '
          '${plan.repeatsPerDistance} sessions.',
        );
      }
      final pendingBytes =
          Sqflite.firstIntValue(
            await transaction.rawQuery('''
              SELECT COALESCE(SUM(LENGTH(crop_png)), 0)
              FROM frames
              WHERE session_id IN (
                SELECT session_id FROM sessions WHERE exported_at IS NULL
              )
            '''),
          ) ??
          0;
      if (pendingBytes + sessionBytes > _maxPendingBytes) {
        throw const DiagnosticCaptureException(
          'The pending queue reached 160 MB. Export it before continuing.',
        );
      }
      final nextIndex = repeatIndex + 1;
      final metadata = <String, dynamic>{
        'diagnostic_capture_schema_version': _schemaVersion,
        'collector': _collector,
        'diagnostic_session_id': sessionId,
        'campaign_id': plan.campaignId,
        'case_id': captureCase.caseId,
        'ground_truth': captureCase.groundTruth,
        'distance': distance.id,
        'repeat_index': nextIndex,
        'captured_at': capturedAt.toIso8601String(),
        'payload_sha256': payloadHash,
        'payload_hash_source': 'on_device_mlkit_decode',
        'raw_payload_stored': false,
        'image_source': 'camera',
        'frames_per_session': frames.length,
        'selection_policy': 'automatic_temporal_burst_no_cherry_pick',
        'analysis_pending': true,
        'frames': [
          for (var index = 0; index < frames.length; index++)
            {
              'frame_index': index,
              'captured_at': frames[index].capturedAt.toUtc().toIso8601String(),
              'frame_size': [
                frames[index].frameWidth,
                frames[index].frameHeight,
              ],
              'corner_coordinates': frames[index].cornerCoordinates,
              'crop_size': [decoded[index].width, decoded[index].height],
              'crop_sha256': hashes[index],
            },
        ],
      };
      await transaction.insert('sessions', {
        'session_id': sessionId,
        'case_id': captureCase.caseId,
        'distance': distance.id,
        'repeat_index': nextIndex,
        'payload_sha256': payloadHash,
        'captured_at': capturedAt.toIso8601String(),
        'metadata_json': const JsonEncoder.withIndent(' ').convert(metadata),
        'exported_at': null,
      });
      for (var index = 0; index < frames.length; index++) {
        await transaction.insert('frames', {
          'session_id': sessionId,
          'frame_index': index,
          'crop_png': frames[index].cropPng,
          'crop_sha256': hashes[index],
        });
      }
    });
  }

  Future<void> discardLastPendingSession({
    required DiagnosticCase captureCase,
    required DiagnosticDistance distance,
  }) async {
    final rows = await _database.query(
      'sessions',
      columns: const ['session_id'],
      where: 'case_id = ? AND distance = ? AND exported_at IS NULL',
      whereArgs: [captureCase.caseId, distance.id],
      orderBy: 'repeat_index DESC',
      limit: 1,
    );
    if (rows.isEmpty) {
      throw const DiagnosticCaptureException(
        'There is no unexported session to discard here.',
      );
    }
    await _database.delete(
      'sessions',
      where: 'session_id = ?',
      whereArgs: [rows.single['session_id']],
    );
  }

  Future<DiagnosticExportBundle> buildExport() async {
    final sessions = await _database.query(
      'sessions',
      where: 'exported_at IS NULL',
      orderBy: 'case_id, distance, repeat_index',
    );
    if (sessions.isEmpty) {
      throw const DiagnosticCaptureException(
        'There are no unexported diagnostic sessions.',
      );
    }
    final archive = Archive();
    final manifestSessions = <Map<String, dynamic>>[];
    final sessionIds = <String>[];
    var totalFrames = 0;
    for (final session in sessions) {
      final sessionId = session['session_id']! as String;
      final caseId = session['case_id']! as String;
      final distance = session['distance']! as String;
      final repeatIndex = session['repeat_index']! as int;
      final base =
          'sessions/$caseId/$distance/'
          'run_${repeatIndex.toString().padLeft(2, '0')}_$sessionId';
      final metadataBytes = Uint8List.fromList(
        utf8.encode(session['metadata_json']! as String),
      );
      archive.addFile(
        ArchiveFile('$base/metadata.json', metadataBytes.length, metadataBytes),
      );
      final frames = await _database.query(
        'frames',
        where: 'session_id = ?',
        whereArgs: [sessionId],
        orderBy: 'frame_index',
      );
      for (final frame in frames) {
        final index = frame['frame_index']! as int;
        final crop = frame['crop_png']! as Uint8List;
        archive.addFile(
          ArchiveFile(
            '$base/crop_${index.toString().padLeft(2, '0')}.png',
            crop.length,
            crop,
          ),
        );
      }
      totalFrames += frames.length;
      manifestSessions.add({
        'diagnostic_session_id': sessionId,
        'case_id': caseId,
        'distance': distance,
        'repeat_index': repeatIndex,
        'base_path': base,
        'frame_count': frames.length,
        'metadata_sha256': sha256.convert(metadataBytes).toString(),
      });
      sessionIds.add(sessionId);
    }
    final exportedAt = DateTime.now().toUtc();
    final manifest = <String, dynamic>{
      'diagnostic_archive_schema_version': _schemaVersion,
      'collector': _collector,
      'campaign_id': plan.campaignId,
      'exported_at': exportedAt.toIso8601String(),
      'session_count': sessions.length,
      'frame_count': totalFrames,
      'raw_payload_stored': false,
      'sessions': manifestSessions,
    };
    final manifestBytes = Uint8List.fromList(
      utf8.encode(const JsonEncoder.withIndent(' ').convert(manifest)),
    );
    archive.addFile(
      ArchiveFile('archive_manifest.json', manifestBytes.length, manifestBytes),
    );
    final stamp = exportedAt
        .toIso8601String()
        .replaceAll(RegExp(r'[-:]'), '')
        .replaceAll(RegExp(r'\..+$'), 'Z');
    return DiagnosticExportBundle(
      filename: 'QRGuard_Diagnostic_${plan.campaignId}_$stamp.zip',
      bytes: ZipEncoder().encodeBytes(archive),
      sessionIds: List.unmodifiable(sessionIds),
    );
  }

  Future<String> exportPendingToDownloads() async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      throw const DiagnosticCaptureException(
        'Diagnostic ZIP export is available only in the Android capture APK.',
      );
    }
    final bundle = await buildExport();
    final location = await _exportChannel.invokeMethod<String>('saveZip', {
      'filename': bundle.filename,
      'bytes': bundle.bytes,
    });
    if (location == null || location.isEmpty) {
      throw const DiagnosticCaptureException('Android did not save the ZIP.');
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
    12,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}
