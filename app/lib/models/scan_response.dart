/// Response models mirroring the backend's Pydantic schemas.
///
/// These are the client half of the contract in `backend/app/schemas.py`. Parsing is
/// deliberately defensive: a field the backend adds later must not crash an older app,
/// and a missing optional field must stay null rather than becoming a misleading 0.
library;

enum Verdict { safe, warning, blocked }

Verdict verdictFrom(String? raw) => switch (raw) {
  'safe' => Verdict.safe,
  'warning' => Verdict.warning,
  'blocked' => Verdict.blocked,
  _ => Verdict.warning, // unknown verdict: be cautious, never silently "safe"
};

/// Whether an analysis branch produced an authoritative result.
///
/// `notApplicable` is a normal outcome (for example, the URL model does not
/// apply to Wi-Fi, text, or payment QR payloads). It must not be presented as
/// a failed or partial analysis.
enum AnalysisStatus { completed, notApplicable, unavailable, inconclusive }

AnalysisStatus analysisStatusFrom(
  String? raw, {
  double? score,
  bool inconclusive = false,
}) => switch (raw) {
  'completed' => AnalysisStatus.completed,
  'not_applicable' => AnalysisStatus.notApplicable,
  'unavailable' => AnalysisStatus.unavailable,
  'inconclusive' => AnalysisStatus.inconclusive,
  _ when score != null => AnalysisStatus.completed,
  _ when inconclusive => AnalysisStatus.inconclusive,
  _ => AnalysisStatus.notApplicable,
};

/// Raw per-branch signals. Null means that branch abstained — which is different
/// from it reporting zero risk, and the UI says so.
class BranchScores {
  final double? pStructural;
  final double? pStructuralRaw;
  final String? structuralType; // clean | adversarial | tampered
  final String? structuralQualityStatus; // usable | marginal | unusable
  final List<String> structuralQualityConditions;
  final String? structuralRescanReason;
  final int structuralFramesReceived;
  final int structuralFramesAnalyzed;
  final String? structuralConsensus;
  final double? pUrl;
  final double? llmScore;
  final double? domainUnknown;
  final AnalysisStatus structuralStatus;
  final AnalysisStatus semanticStatus;
  final String imageSource;

  const BranchScores({
    this.pStructural,
    this.pStructuralRaw,
    this.structuralType,
    this.structuralQualityStatus,
    this.structuralQualityConditions = const [],
    this.structuralRescanReason,
    this.structuralFramesReceived = 0,
    this.structuralFramesAnalyzed = 0,
    this.structuralConsensus,
    this.pUrl,
    this.llmScore,
    this.domainUnknown,
    this.structuralStatus = AnalysisStatus.notApplicable,
    this.semanticStatus = AnalysisStatus.notApplicable,
    this.imageSource = 'unknown',
  });

  factory BranchScores.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const BranchScores();
    final pStructural = _toDouble(json['p_structural']);
    final pUrl = _toDouble(json['p_url']);
    return BranchScores(
      pStructural: pStructural,
      pStructuralRaw: _toDouble(json['p_structural_raw']),
      structuralType: json['structural_type'] as String?,
      structuralQualityStatus: json['structural_quality_status'] as String?,
      structuralQualityConditions: _toStringList(
        json['structural_quality_conditions'],
      ),
      structuralRescanReason: json['structural_rescan_reason'] as String?,
      structuralFramesReceived:
          (json['structural_frames_received'] as num?)?.round() ?? 0,
      structuralFramesAnalyzed:
          (json['structural_frames_analyzed'] as num?)?.round() ?? 0,
      structuralConsensus: json['structural_consensus'] as String?,
      pUrl: pUrl,
      llmScore: _toDouble(json['llm_score']),
      domainUnknown: _toDouble(json['domain_unknown']),
      structuralStatus: analysisStatusFrom(
        json['structural_status'] as String?,
        score: pStructural,
      ),
      semanticStatus: analysisStatusFrom(
        json['semantic_status'] as String?,
        score: pUrl,
      ),
      imageSource: json['image_source'] as String? ?? 'unknown',
    );
  }

  bool get structuralRan => structuralStatus == AnalysisStatus.completed;
  bool get semanticRan => semanticStatus == AnalysisStatus.completed;
  bool get contentAnalysisResolved =>
      semanticStatus == AnalysisStatus.completed ||
      semanticStatus == AnalysisStatus.notApplicable;
}

class ScanResponse {
  final Verdict verdict;
  final int riskScore; // 0-100
  final List<String> reasons;
  final String payloadType;
  final String? normalizedUrl;
  final String? registeredDomain;
  final List<String> ruleFlags;
  final BranchScores branchScores;
  final bool partialAnalysis;
  final bool deepCheckAvailable;
  final String? payload;
  final String payloadSource; // provided | decoded | undecodable
  final int elapsedMs;
  final Map<String, int> timingsMs;

  const ScanResponse({
    required this.verdict,
    required this.riskScore,
    required this.reasons,
    required this.payloadType,
    required this.branchScores,
    this.normalizedUrl,
    this.registeredDomain,
    this.ruleFlags = const [],
    this.partialAnalysis = false,
    this.deepCheckAvailable = false,
    this.payload,
    this.payloadSource = 'provided',
    this.elapsedMs = 0,
    this.timingsMs = const {},
  });

  factory ScanResponse.fromJson(Map<String, dynamic> json) => ScanResponse(
    verdict: verdictFrom(json['verdict'] as String?),
    riskScore: (json['risk_score'] as num?)?.round() ?? 0,
    reasons: _toStringList(json['reasons']),
    payloadType: json['payload_type'] as String? ?? 'text',
    normalizedUrl: json['normalized_url'] as String?,
    registeredDomain: json['registered_domain'] as String?,
    ruleFlags: _toStringList(json['rule_flags']),
    branchScores: BranchScores.fromJson(
      json['branch_scores'] as Map<String, dynamic>?,
    ),
    partialAnalysis: json['partial_analysis'] as bool? ?? false,
    deepCheckAvailable: json['deep_check_available'] as bool? ?? false,
    payload: json['payload'] as String?,
    payloadSource: json['payload_source'] as String? ?? 'provided',
    elapsedMs: (json['elapsed_ms'] as num?)?.round() ?? 0,
    timingsMs: _toTimingMap(json['timings_ms']),
  );

  ScanResponse withTimings(Map<String, int> additionalTimings) => ScanResponse(
    verdict: verdict,
    riskScore: riskScore,
    reasons: reasons,
    payloadType: payloadType,
    branchScores: branchScores,
    normalizedUrl: normalizedUrl,
    registeredDomain: registeredDomain,
    ruleFlags: ruleFlags,
    partialAnalysis: partialAnalysis,
    deepCheckAvailable: deepCheckAvailable,
    payload: payload,
    payloadSource: payloadSource,
    elapsedMs: elapsedMs,
    timingsMs: {...timingsMs, ...additionalTimings},
  );

  /// What the user should be shown as the destination. Always the expanded /
  /// normalized form — never a shortened link.
  String get displayTarget => payloadType == 'attendance'
      ? 'hi-hive attendance QR'
      : normalizedUrl ?? payload ?? '(could not read this QR code)';

  bool get isUrl => payloadType == 'url';
  bool get isHiHiveAttendance =>
      payloadType == 'attendance' && (payload ?? '').startsWith('Q01:*:');
  bool get couldNotDecode => payloadSource == 'undecodable';
}

Map<String, int> _toTimingMap(Object? raw) {
  if (raw is! Map) return const {};
  return {
    for (final entry in raw.entries)
      if (entry.key is String && entry.value is num)
        entry.key as String: (entry.value as num).round(),
  };
}

class DeepCheckResponse {
  final String llmVerdict; // benign | suspicious | phishing
  final double llmConfidence;
  final String explanation;
  final List<String> riskFactors;
  final String? finalUrl;
  final List<String> redirectChain;
  final String? redirectBlockedReason;
  final Verdict verdict;
  final int riskScore;
  final int previousRiskScore;
  final List<String> reasons;
  final bool llmAvailable;
  final String? error;
  final int elapsedMs;

  const DeepCheckResponse({
    required this.llmVerdict,
    required this.llmConfidence,
    required this.explanation,
    required this.verdict,
    required this.riskScore,
    required this.previousRiskScore,
    this.riskFactors = const [],
    this.finalUrl,
    this.redirectChain = const [],
    this.redirectBlockedReason,
    this.reasons = const [],
    this.llmAvailable = true,
    this.error,
    this.elapsedMs = 0,
  });

  factory DeepCheckResponse.fromJson(Map<String, dynamic> json) =>
      DeepCheckResponse(
        llmVerdict: json['llm_verdict'] as String? ?? 'suspicious',
        llmConfidence: _toDouble(json['llm_confidence']) ?? 0.5,
        explanation: json['explanation'] as String? ?? '',
        riskFactors: _toStringList(json['risk_factors']),
        finalUrl: json['final_url'] as String?,
        redirectChain: _toStringList(json['redirect_chain']),
        redirectBlockedReason: json['redirect_blocked_reason'] as String?,
        verdict: verdictFrom(json['verdict'] as String?),
        riskScore: (json['risk_score'] as num?)?.round() ?? 0,
        previousRiskScore: (json['previous_risk_score'] as num?)?.round() ?? 0,
        reasons: _toStringList(json['reasons']),
        llmAvailable: json['llm_available'] as bool? ?? false,
        error: json['error'] as String?,
        elapsedMs: (json['elapsed_ms'] as num?)?.round() ?? 0,
      );

  /// True when the deep check actually moved the verdict, so the UI can say so.
  bool get changedScore => riskScore != previousRiskScore;

  /// The link genuinely hid its destination behind redirects.
  bool get hadRedirects => redirectChain.length > 1;
}

/// Backend health, used at startup to read the live thresholds and capabilities.
class HealthResponse {
  final String status;
  final Map<String, String> components;

  const HealthResponse({required this.status, required this.components});

  factory HealthResponse.fromJson(Map<String, dynamic> json) => HealthResponse(
    status: json['status'] as String? ?? 'degraded',
    components: (json['components'] as Map<String, dynamic>? ?? {}).map(
      (k, v) => MapEntry(k, v.toString()),
    ),
  );

  bool get deepCheckConfigured => components['deep_check'] == 'configured';
  bool get isHealthy => status == 'ok';
}

double? _toDouble(dynamic v) => v == null ? null : (v as num).toDouble();

List<String> _toStringList(dynamic v) =>
    (v as List?)?.map((e) => e.toString()).toList() ?? const [];
