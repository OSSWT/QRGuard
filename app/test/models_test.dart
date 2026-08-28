/// Tests for response parsing and settings normalisation.
///
/// The JSON fixtures below are real responses captured from the running backend, so a
/// schema change on the server breaks these tests rather than the app at runtime.
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/models/scan_response.dart';
import 'package:qrguard/services/settings_service.dart';

const _phishingScan = '''
{
  "verdict": "blocked",
  "risk_score": 100,
  "reasons": ["Domain uses a frequently-abused extension",
              "Destination link matches phishing patterns"],
  "payload_type": "url",
  "normalized_url": "http://maybank2u-verify.xyz/login/update.php",
  "registered_domain": "maybank2u-verify.xyz",
  "rule_flags": ["non_https", "suspicious_tld"],
  "branch_scores": {
    "p_structural": 0.00004982948303222656,
    "p_structural_raw": 0.00004982948303222656,
    "structural_type": "clean",
    "p_url": 0.9913274645805359,
    "llm_score": null,
    "domain_unknown": 1,
    "image_source": "gallery"
  },
  "partial_analysis": false,
  "deep_check_available": true,
  "payload": "http://maybank2u-verify.xyz/login/update.php",
  "payload_source": "decoded",
  "elapsed_ms": 287
}''';

const _undecodableScan = '''
{
  "verdict": "blocked",
  "risk_score": 100,
  "reasons": ["QR image appears manipulated"],
  "payload_type": "text",
  "normalized_url": null,
  "registered_domain": null,
  "rule_flags": [],
  "branch_scores": {
    "p_structural": 0.9989,
    "structural_type": "tampered",
    "p_url": null,
    "llm_score": null,
    "domain_unknown": null
  },
  "partial_analysis": true,
  "deep_check_available": false,
  "payload": null,
  "payload_source": "undecodable",
  "elapsed_ms": 42
}''';

void main() {
  group('ScanResponse', () {
    test('parses a real phishing response', () {
      final s = ScanResponse.fromJson(jsonDecode(_phishingScan));
      expect(s.verdict, Verdict.blocked);
      expect(s.riskScore, 100);
      expect(s.registeredDomain, 'maybank2u-verify.xyz');
      expect(s.ruleFlags, contains('suspicious_tld'));
      expect(s.deepCheckAvailable, isTrue);
      expect(s.payloadSource, 'decoded');
    });

    test('keeps both branch scores distinct', () {
      final s = ScanResponse.fromJson(jsonDecode(_phishingScan));
      expect(s.branchScores.pStructural, lessThan(0.01)); // image was clean
      expect(s.branchScores.pStructuralRaw, lessThan(0.01));
      expect(s.branchScores.pUrl, greaterThan(0.9)); // link was not
      expect(s.branchScores.structuralType, 'clean');
      expect(s.branchScores.imageSource, 'gallery');
      expect(s.branchScores.structuralRan, isTrue);
      expect(s.branchScores.semanticRan, isTrue);
    });

    test('camera structural score is authoritative like gallery', () {
      final branch = BranchScores.fromJson({
        'p_structural': 0.85,
        'p_structural_raw': 0.85,
        'structural_type': 'adversarial',
        'structural_status': 'completed',
        'image_source': 'camera',
        // Extra fields from an older server are safely ignored.
        'camera_structural_uncertain': true,
        'p_structural_samples': [0.54, 0.59, 0.63],
        'structural_consensus': 'uncertain',
      });

      expect(branch.pStructural, 0.85);
      expect(branch.structuralType, 'adversarial');
      expect(branch.structuralStatus, AnalysisStatus.completed);
    });

    test('distinguishes not-applicable from an unavailable branch', () {
      final branch = BranchScores.fromJson({
        'structural_status': 'unavailable',
        'semantic_status': 'not_applicable',
      });

      expect(branch.structuralStatus, AnalysisStatus.unavailable);
      expect(branch.semanticStatus, AnalysisStatus.notApplicable);
      expect(branch.contentAnalysisResolved, isTrue);
    });

    test('an abstaining branch stays null, never 0', () {
      // A tampered QR cannot be decoded, so the semantic branch has no input.
      // Rendering that as 0.0 would imply "analysed, and found safe".
      final s = ScanResponse.fromJson(jsonDecode(_undecodableScan));
      expect(s.branchScores.pUrl, isNull);
      expect(s.branchScores.semanticRan, isFalse);
      expect(s.branchScores.structuralRan, isTrue);
      expect(s.partialAnalysis, isTrue);
      expect(s.couldNotDecode, isTrue);
    });

    test('unknown verdict falls back to warning, never safe', () {
      final s = ScanResponse.fromJson({'verdict': 'something_new'});
      expect(s.verdict, Verdict.warning);
    });

    test('missing fields do not throw', () {
      final s = ScanResponse.fromJson({});
      expect(s.riskScore, 0);
      expect(s.reasons, isEmpty);
      expect(s.branchScores.pUrl, isNull);
    });

    test('displayTarget prefers the normalized URL over the raw payload', () {
      final s = ScanResponse.fromJson(jsonDecode(_phishingScan));
      expect(s.displayTarget, 'http://maybank2u-verify.xyz/login/update.php');
    });

    test('undecodable scan still says something to the user', () {
      final s = ScanResponse.fromJson(jsonDecode(_undecodableScan));
      expect(s.displayTarget, isNotEmpty);
    });
  });

  group('DeepCheckResponse', () {
    test('parses an LLM verdict and reports the score change', () {
      final d = DeepCheckResponse.fromJson({
        'llm_verdict': 'phishing',
        'llm_confidence': 0.95,
        'explanation': 'This link pretends to be Maybank.',
        'risk_factors': ['Impersonates Maybank Malaysia domain'],
        'final_url': 'http://maybank2u-verify.xyz/login',
        'redirect_chain': [
          'https://bit.ly/x',
          'http://maybank2u-verify.xyz/login',
        ],
        'verdict': 'blocked',
        'risk_score': 87,
        'previous_risk_score': 48,
        'llm_available': true,
        'elapsed_ms': 1174,
      });
      expect(d.llmVerdict, 'phishing');
      expect(d.changedScore, isTrue);
      expect(d.hadRedirects, isTrue);
      expect(d.riskFactors.first, contains('Maybank'));
    });

    test('degrades cleanly when the LLM is unavailable', () {
      final d = DeepCheckResponse.fromJson({
        'llm_verdict': 'suspicious',
        'llm_confidence': 0.5,
        'explanation': 'Deep analysis is not configured on this server.',
        'verdict': 'warning',
        'risk_score': 48,
        'previous_risk_score': 48,
        'llm_available': false,
        'error': 'No LLM credential configured (set GEMINI_API_KEY).',
      });
      expect(d.llmAvailable, isFalse);
      expect(d.changedScore, isFalse);
      expect(d.error, isNotNull);
    });
  });

  group('HealthResponse', () {
    test('reports capability, not just liveness', () {
      final h = HealthResponse.fromJson({
        'status': 'ok',
        'components': {
          'structural': 'structural_fp32.onnx',
          'method1': 'model_quant.onnx',
          'fusion': 'safe<38 blocked>=55',
          'domain_list': '150000 domains',
          'deep_check': 'configured',
        },
      });
      expect(h.isHealthy, isTrue);
      expect(h.deepCheckConfigured, isTrue);
    });

    test('deep check absent is reported without failing health', () {
      final h = HealthResponse.fromJson({
        'status': 'ok',
        'components': {'deep_check': 'not configured'},
      });
      expect(h.isHealthy, isTrue);
      expect(h.deepCheckConfigured, isFalse);
    });
  });

  group('SettingsService.normalise', () {
    test('bare IP gains scheme and default port', () {
      expect(
        SettingsService.normalise('192.168.1.5'),
        'http://192.168.1.5:8001',
      );
    });
    test('IP with port keeps the port', () {
      expect(
        SettingsService.normalise('192.168.1.5:9000'),
        'http://192.168.1.5:9000',
      );
    });
    test('full URL is preserved', () {
      expect(
        SettingsService.normalise('http://10.1.87.26:8000'),
        'http://10.1.87.26:8000',
      );
    });
    test('production HTTPS URL keeps the standard port', () {
      expect(
        SettingsService.normalise('https://qrguard-api.example.run.app/'),
        'https://qrguard-api.example.run.app',
      );
    });
    test('trailing slashes are stripped', () {
      expect(
        SettingsService.normalise('http://10.1.87.26:8000///'),
        'http://10.1.87.26:8000',
      );
    });
    test('empty input falls back to the default', () {
      expect(
        SettingsService.normalise('   '),
        SettingsService.defaultBackendUrl,
      );
    });
  });
}
