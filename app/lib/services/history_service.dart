/// Local scan history.
///
/// Privacy rule from the project's UX contract: the payload is represented only
/// by SHA-256, never by its raw URL, and the image is never stored. The registered
/// domain and non-identifying branch signals are retained so History can reproduce
/// the result evidence without preserving paths, queries or free-text reasons.
library;

import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/scan_response.dart';

/// History preserves the same verdict the result screen presented. An expected
/// branch that was unavailable still fails closed.
Verdict effectiveHistoryVerdict(ScanResponse scan) => scan.partialAnalysis
    ? (scan.verdict == Verdict.blocked ? Verdict.blocked : Verdict.warning)
    : scan.verdict;

class ScanRecord {
  final int? id;
  final String payloadHash; // SHA-256, never the raw payload
  final String? registeredDomain;
  final String verdict;
  final int riskScore;
  final DateTime scannedAt;
  final String? analysisSnapshot;

  const ScanRecord({
    this.id,
    required this.payloadHash,
    required this.verdict,
    required this.riskScore,
    required this.scannedAt,
    this.registeredDomain,
    this.analysisSnapshot,
  });

  Map<String, Object?> toMap() => {
    'payload_hash': payloadHash,
    'registered_domain': registeredDomain,
    'verdict': verdict,
    'risk_score': riskScore,
    'scanned_at': scannedAt.millisecondsSinceEpoch,
    'analysis_snapshot': analysisSnapshot,
  };

  factory ScanRecord.fromMap(Map<String, Object?> m) => ScanRecord(
    id: m['id'] as int?,
    payloadHash: m['payload_hash'] as String,
    registeredDomain: m['registered_domain'] as String?,
    verdict: m['verdict'] as String,
    riskScore: m['risk_score'] as int,
    scannedAt: DateTime.fromMillisecondsSinceEpoch(m['scanned_at'] as int),
    analysisSnapshot: m['analysis_snapshot'] as String?,
  );

  Verdict get verdictEnum => verdictFrom(verdict);

  /// Rebuild the privacy-safe part of the original result so History can use
  /// the same evidence layout. Raw payloads, URLs, images and free-text reasons
  /// are deliberately absent and cannot be reconstructed here.
  ScanResponse? get storedAnalysis {
    final snapshot = analysisSnapshot;
    if (snapshot == null || snapshot.isEmpty) return null;
    try {
      final decoded = jsonDecode(snapshot);
      if (decoded is! Map<String, dynamic>) return null;
      return ScanResponse.fromJson({
        ...decoded,
        'verdict': verdict,
        'risk_score': riskScore,
        'registered_domain': registeredDomain,
      });
    } catch (_) {
      return null;
    }
  }
}

class HistoryService {
  static const _dbName = 'qrguard_history.db';
  static const _table = 'scans';
  static const _maxRecords = 200; // keep the list useful and the file small

  Database? _db;
  final List<ScanRecord> _webRecords = [];

  Future<Database> get _database async => _db ??= await openDatabase(
    p.join(await getDatabasesPath(), _dbName),
    version: 2,
    onCreate: (db, _) => db.execute('''
          CREATE TABLE $_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_hash TEXT NOT NULL,
            registered_domain TEXT,
            verdict TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            scanned_at INTEGER NOT NULL,
            analysis_snapshot TEXT
          )
        '''),
    onUpgrade: (db, oldVersion, _) async {
      if (oldVersion < 2) {
        await db.execute(
          'ALTER TABLE $_table ADD COLUMN analysis_snapshot TEXT',
        );
      }
    },
  );

  /// Hash a payload for storage. Exposed so tests can assert nothing raw is kept.
  static String hashPayload(String payload) =>
      sha256.convert(utf8.encode(payload)).toString();

  /// Serialize only the non-identifying analysis signals needed to reproduce
  /// the result evidence card in History.
  @visibleForTesting
  static String snapshotForStorage(ScanResponse scan) {
    final branch = scan.branchScores;
    return jsonEncode({
      'payload_type': scan.payloadType,
      'rule_flags': scan.ruleFlags,
      'reasons': _privacySafeReasons(scan),
      'branch_scores': {
        'p_structural': branch.pStructural,
        'p_structural_raw': branch.pStructuralRaw,
        'structural_type': branch.structuralType,
        'structural_quality_status': branch.structuralQualityStatus,
        'structural_quality_conditions': branch.structuralQualityConditions,
        'structural_rescan_reason': branch.structuralRescanReason,
        'structural_frames_received': branch.structuralFramesReceived,
        'structural_frames_analyzed': branch.structuralFramesAnalyzed,
        'structural_consensus': branch.structuralConsensus,
        'p_url': branch.pUrl,
        'llm_score': branch.llmScore,
        'domain_unknown': branch.domainUnknown,
        'structural_status': _analysisStatusWire(branch.structuralStatus),
        'semantic_status': _analysisStatusWire(branch.semanticStatus),
        'image_source': branch.imageSource,
      },
      'partial_analysis': scan.partialAnalysis,
      'payload_source': scan.payloadSource,
      'elapsed_ms': scan.elapsedMs,
    });
  }

  Future<void> record(ScanResponse scan) async {
    final record = ScanRecord(
      payloadHash: hashPayload(scan.payload ?? ''),
      registeredDomain: scan.registeredDomain,
      verdict: effectiveHistoryVerdict(scan).name,
      riskScore: scan.riskScore,
      scannedAt: DateTime.now(),
      analysisSnapshot: snapshotForStorage(scan),
    );
    if (kIsWeb) {
      _webRecords.insert(0, record);
      if (_webRecords.length > _maxRecords) {
        _webRecords.removeRange(_maxRecords, _webRecords.length);
      }
      return;
    }
    final db = await _database;
    await db.insert(_table, record.toMap());
    await _trim(db);
  }

  Future<List<ScanRecord>> recent({int limit = 50}) async {
    if (kIsWeb) {
      return List.unmodifiable(_webRecords.take(limit));
    }
    final db = await _database;
    final rows = await db.query(
      _table,
      orderBy: 'scanned_at DESC',
      limit: limit,
    );
    return rows.map(ScanRecord.fromMap).toList();
  }

  Future<void> clear() async {
    if (kIsWeb) {
      _webRecords.clear();
      return;
    }
    await (await _database).delete(_table);
  }

  /// Drop the oldest rows once the table grows past [_maxRecords].
  Future<void> _trim(Database db) async {
    final count =
        Sqflite.firstIntValue(
          await db.rawQuery('SELECT COUNT(*) FROM $_table'),
        ) ??
        0;
    if (count <= _maxRecords) return;
    await db.rawDelete(
      '''
      DELETE FROM $_table WHERE id IN (
        SELECT id FROM $_table ORDER BY scanned_at ASC LIMIT ?
      )
    ''',
      [count - _maxRecords],
    );
  }

  Future<void> close() async {
    if (kIsWeb) return;
    await _db?.close();
    _db = null;
  }
}

/// Rebuild only standard, non-identifying explanations from branch values.
/// Server free text is intentionally excluded because it may contain a URL.
List<String> _privacySafeReasons(ScanResponse scan) {
  final reasons = <String>[];
  final branch = scan.branchScores;
  if (branch.structuralType == 'adversarial') {
    reasons.add('QR image appears adversarial');
  } else if (branch.structuralType == 'tampered') {
    reasons.add('QR image appears manipulated');
  }
  if (branch.pUrl case final score? when score >= 0.5) {
    reasons.add('Destination link matches phishing patterns');
  }
  return reasons;
}

String _analysisStatusWire(AnalysisStatus status) => switch (status) {
  AnalysisStatus.completed => 'completed',
  AnalysisStatus.notApplicable => 'not_applicable',
  AnalysisStatus.unavailable => 'unavailable',
  AnalysisStatus.inconclusive => 'inconclusive',
};
