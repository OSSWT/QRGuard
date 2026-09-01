/// Safe, Warning, Blocked and fail-closed Partial result presentations.
library;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/scan_response.dart';
import '../services/api_client.dart';
import '../services/duitnow_qr.dart';
import '../services/official_app_launcher.dart';
import '../theme.dart';
import '../widgets/reason_card.dart';

class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, required this.scan, required this.api});

  final ScanResponse scan;
  final ApiClient api;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  late ScanResponse _scan = widget.scan;
  DeepCheckResponse? _deep;
  bool _checking = false;
  String? _deepError;

  DuitNowQr? get _duitNow => DuitNowQr.tryParse(_scan.payload);
  bool get _isHiHive => _scan.isHiHiveAttendance;
  bool get _canProceed => _scan.isUrl || _duitNow != null || _isHiHive;
  String get _proceedLabel => _isHiHive
      ? 'Open hi-hive'
      : _duitNow == null
      ? 'Proceed to URL'
      : 'Open TNG eWallet';
  String get _destinationDescription => _isHiHive
      ? 'Official hi-hive app (scan the original attendance QR again)'
      : _duitNow == null
      ? _scan.displayTarget
      : 'DuitNow recipient: ${_duitNow!.recipientName}';

  _ResultKind get _kind {
    // A missing branch may raise Safe to the fail-closed Partial/Warning state,
    // but it must never downgrade an explicit backend Blocked verdict.
    if (_scan.verdict == Verdict.blocked) return _ResultKind.blocked;
    if (_scan.partialAnalysis) return _ResultKind.partial;
    return switch (_scan.verdict) {
      Verdict.safe => _ResultKind.safe,
      Verdict.warning => _ResultKind.warning,
      Verdict.blocked => _ResultKind.blocked,
    };
  }

  VerdictStyle _style(BuildContext context) => _kind == _ResultKind.partial
      ? VerdictStyle.partial(context)
      : VerdictStyle.of(context, _scan.verdict);

  @override
  Widget build(BuildContext context) {
    final style = _style(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan result'),
        leading: IconButton(
          tooltip: 'Close result',
          icon: const Icon(Icons.close_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            _VerdictHeader(style: style),
            if (_deep?.changedScore == true) ...[
              const SizedBox(height: 10),
              _UpdatedBanner(
                previous: _deep!.previousRiskScore,
                current: _deep!.riskScore,
              ),
            ],
            const SizedBox(height: 18),
            DestinationCard(scan: _scan),
            const SizedBox(height: 14),
            VerdictSummaryCard(
              summary: _summaryText,
              color: style.color,
              title: _summaryTitle,
            ),
            const SizedBox(height: 14),
            Card(
              child: ExpansionTile(
                initiallyExpanded: false,
                maintainState: true,
                shape: const Border(),
                collapsedShape: const Border(),
                title: const Text(
                  'Details',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: const Text('Structural, Semantic and Risk evidence'),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: [BranchEvidence(scan: _scan)],
              ),
            ),
            if (_scan.partialAnalysis) ...[
              const SizedBox(height: 14),
              _PartialNotice(scan: _scan),
            ],
            if (_deep != null) ...[
              const SizedBox(height: 14),
              _DeepCheckCard(response: _deep!),
            ],
            const SizedBox(height: 22),
            ..._actions(context, style),
          ],
        ),
      ),
    );
  }

  List<String> get _displayReasons {
    final reasons = deduplicateAnalysisReasons(_scan.reasons);
    if (reasons.isNotEmpty) return reasons;
    if (_kind == _ResultKind.safe) {
      return const [
        'No elevated risk indicators were returned by the completed analysis branches.',
      ];
    }
    return const [
      'The server returned a cautious result without a detailed explanation.',
    ];
  }

  String get _summaryTitle => switch (_kind) {
    _ResultKind.safe => 'Why this looks safe',
    _ResultKind.warning => 'Why caution is needed',
    _ResultKind.blocked => 'Why this was blocked',
    _ResultKind.partial => 'Why this result needs caution',
  };

  String get _summaryText {
    final evidence = _summaryEvidence;
    return switch (_kind) {
      _ResultKind.safe =>
        _scan.isUrl
            ? 'QRGuard found no strong risk indicators in the completed URL, rule, '
                  'and QR-image checks. This is a risk assessment, not a guarantee '
                  'that the destination is trustworthy.'
            : 'QRGuard recognised this non-URL QR and found no strong risk '
                  'indicators in the applicable checks. A URL-specific Semantic '
                  'score is not required for this payload type.',
      _ResultKind.warning =>
        'QRGuard found signals that require caution. $evidence '
            'The evidence is not conclusive enough for a Blocked result, so verify '
            'the domain and full URL before continuing.',
      _ResultKind.blocked =>
        'QRGuard found strong risk indicators. $evidence The URL or QR image '
            'strongly matches malicious or manipulated patterns, so you '
            'should not open this destination.',
      _ResultKind.partial =>
        'QRGuard could not complete every analysis branch. $evidence '
            'Treat this result with '
            'caution and verify the destination independently.',
    };
  }

  String get _summaryEvidence {
    final maximum = _kind == _ResultKind.blocked ? 3 : 2;
    final selected = _primaryEvidence.take(maximum).toList();
    if (selected.isEmpty) {
      return 'The available evidence could not be summarised more specifically.';
    }
    return selected.map(_asSentence).join(' ');
  }

  List<String> get _primaryEvidence {
    final flags = _scan.ruleFlags.toSet();
    final evidence = <String>[];
    final target = _scan.normalizedUrl ?? _scan.payload;
    final uri = target == null ? null : Uri.tryParse(target);
    final domain = _scan.registeredDomain ?? uri?.host;

    if (flags.contains('js_or_data_uri')) {
      evidence.add(
        'The payload contains executable content instead of a normal web address',
      );
    }
    if (flags.contains('userinfo_in_url')) {
      final userInfo = uri?.userInfo.split(':').first.trim();
      if (userInfo != null && userInfo.isNotEmpty && domain != null) {
        evidence.add(
          'The text “$userInfo” before “@” is a decoy; the actual domain is “$domain”',
        );
      } else {
        evidence.add(
          'The link uses “@” to disguise its actual destination domain',
        );
      }
    }
    if (flags.contains('ip_literal_host')) {
      evidence.add('The destination uses a raw IP address instead of a domain');
    }
    if (flags.contains('punycode_host')) {
      evidence.add('The domain uses encoded look-alike characters');
    }
    if (flags.contains('brand_in_subdomain')) {
      evidence.add('A trusted brand name appears outside the actual domain');
    }
    if (flags.contains('shortened_url')) {
      evidence.add('A shortened link hides the final destination');
    }

    final structural = _scan.branchScores;
    if (structural.structuralType != null &&
        structural.structuralType != 'clean') {
      evidence.add(
        'The QR image appears ${structural.structuralType}, rather than clean',
      );
    }

    final pUrl = _scan.branchScores.pUrl;
    if (pUrl != null && pUrl >= 0.5) {
      final level = pUrl >= 0.75 ? 'very high' : 'elevated';
      evidence.add(
        'The URL model returned a $level phishing score (${pUrl.toStringAsFixed(2)})',
      );
    }
    if (flags.contains('suspicious_tld')) {
      final tld = domain?.contains('.') == true
          ? domain!.split('.').last
          : null;
      evidence.add(
        tld == null
            ? 'The destination uses a frequently abused domain extension'
            : 'The destination uses the frequently abused .$tld extension',
      );
    }
    if (flags.contains('excessive_subdomains')) {
      evidence.add('The link uses unusually deep subdomain nesting');
    }
    if (flags.contains('long_url')) {
      evidence.add('The link is unusually long');
    }
    if (flags.contains('non_https')) {
      evidence.add('The destination does not use HTTPS encryption');
    }
    if (_scan.branchScores.domainUnknown == 1) {
      evidence.add('The destination is not widely recognised');
    }

    if (evidence.isEmpty) {
      evidence.addAll(
        _displayReasons.map(
          (reason) => reason.replaceFirst(RegExp(r'[.!?]+$'), ''),
        ),
      );
    }
    return evidence;
  }

  String _asSentence(String value) => RegExp(r'[.!?]$').hasMatch(value.trim())
      ? value.trim()
      : '${value.trim()}.';

  List<Widget> _actions(BuildContext context, VerdictStyle style) {
    final widgets = <Widget>[];
    if (_deepError != null) {
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            _deepError!,
            style: TextStyle(color: context.qrColors.blocked, fontSize: 13),
          ),
        ),
      );
    }

    switch (_kind) {
      case _ResultKind.safe:
        widgets.add(
          FilledButton.icon(
            onPressed: _canProceed
                ? _openDestination
                : () => Navigator.of(context).pop(),
            icon: Icon(
              _canProceed
                  ? (_isHiHive
                        ? Icons.school_outlined
                        : _duitNow == null
                        ? Icons.open_in_new_rounded
                        : Icons.account_balance_wallet_outlined)
                  : Icons.qr_code_scanner,
            ),
            label: Text(_canProceed ? _proceedLabel : 'Scan Another'),
          ),
        );
        break;
      case _ResultKind.warning:
      case _ResultKind.partial:
        widgets.add(
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.arrow_back_rounded),
            label: const Text('Go Back'),
          ),
        );
        break;
      case _ResultKind.blocked:
        widgets.add(
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.qr_code_scanner_rounded),
            label: const Text('Scan Another'),
          ),
        );
        break;
    }

    if (_scan.isUrl && _deep == null) {
      widgets.add(const SizedBox(height: 10));
      widgets.add(
        OutlinedButton.icon(
          onPressed: _checking ? null : _runDeepCheck,
          icon: _checking
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.psychology_outlined),
          label: Text(
            _checking
                ? 'Checking this link in depth...'
                : 'Check this link in depth',
          ),
        ),
      );
    }

    if (_canProceed &&
        (_kind == _ResultKind.warning || _kind == _ResultKind.partial)) {
      widgets.add(const SizedBox(height: 6));
      widgets.add(
        TextButton(
          onPressed: _confirmWarningProceed,
          child: Text(
            _isHiHive
                ? 'Open hi-hive to scan again'
                : _duitNow == null
                ? 'Proceed anyway'
                : 'Open payment app anyway',
            style: TextStyle(color: style.color),
          ),
        ),
      );
    }
    if (_canProceed && _kind == _ResultKind.blocked) {
      widgets.add(const SizedBox(height: 6));
      widgets.add(
        TextButton.icon(
          key: const ValueKey('blocked_override'),
          onPressed: _confirmBlockedOverride,
          icon: Icon(Icons.warning_amber_rounded, color: style.color, size: 18),
          label: Text(
            _duitNow == null
                ? 'Override blocked URL'
                : 'Override blocked payment QR',
            style: TextStyle(color: style.color),
          ),
        ),
      );
    }
    return widgets;
  }

  Future<void> _runDeepCheck() async {
    final payload = _scan.payload;
    if (payload == null || payload.isEmpty) return;
    setState(() {
      _checking = true;
      _deepError = null;
    });
    try {
      final result = await widget.api.deepCheck(
        payload: payload,
        pStructural: _scan.branchScores.pStructural,
      );
      if (!mounted) return;
      final baseReasons = result.reasons
          .where((reason) => reason != result.explanation)
          .toList();
      setState(() {
        _deep = result;
        _scan = ScanResponse(
          verdict: result.verdict,
          riskScore: result.riskScore,
          reasons: baseReasons.isEmpty ? _scan.reasons : baseReasons,
          payloadType: _scan.payloadType,
          branchScores: BranchScores(
            pStructural: _scan.branchScores.pStructural,
            pStructuralRaw: _scan.branchScores.pStructuralRaw,
            structuralType: _scan.branchScores.structuralType,
            structuralQualityStatus: _scan.branchScores.structuralQualityStatus,
            structuralQualityConditions:
                _scan.branchScores.structuralQualityConditions,
            structuralRescanReason: _scan.branchScores.structuralRescanReason,
            structuralFramesReceived:
                _scan.branchScores.structuralFramesReceived,
            structuralFramesAnalyzed:
                _scan.branchScores.structuralFramesAnalyzed,
            structuralConsensus: _scan.branchScores.structuralConsensus,
            pUrl: _scan.branchScores.pUrl,
            llmScore: result.llmAvailable ? result.llmConfidence : null,
            domainUnknown: _scan.branchScores.domainUnknown,
            structuralStatus: _scan.branchScores.structuralStatus,
            semanticStatus: _scan.branchScores.semanticStatus,
            imageSource: _scan.branchScores.imageSource,
          ),
          normalizedUrl: result.finalUrl ?? _scan.normalizedUrl,
          registeredDomain: _scan.registeredDomain,
          ruleFlags: _scan.ruleFlags,
          partialAnalysis: _scan.partialAnalysis,
          deepCheckAvailable: false,
          payload: _scan.payload,
          payloadSource: _scan.payloadSource,
          elapsedMs: _scan.elapsedMs,
          timingsMs: _scan.timingsMs,
        );
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _deepError = error.message);
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _confirmWarningProceed() async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        icon: Icon(
          Icons.warning_amber_rounded,
          color: context.qrColors.warning,
        ),
        title: Text(
          _isHiHive
              ? 'Open the official hi-hive app?'
              : _duitNow == null
              ? 'Proceed to this destination?'
              : 'Open this payment in TNG?',
        ),
        content: Text(
          _isHiHive
              ? 'QRGuard recognises the attendance format but cannot verify or '
                    'submit the token. Open hi-hive, then scan the original QR '
                    'again inside the official app.'
              : 'QRGuard found signals that require caution. You are responsible '
                    'for the consequences if you continue.\n\n'
                    '$_destinationDescription',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Do not proceed'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Proceed anyway'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _openDestination();
    } else if (confirmed == false && mounted) {
      Navigator.of(context).pop();
    }
  }

  Future<void> _confirmBlockedOverride() async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        icon: Icon(
          Icons.dangerous_outlined,
          color: context.qrColors.blocked,
          size: 34,
        ),
        title: const Text('This destination is blocked'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'QRGuard strongly recommends that you do not open this destination. '
              'Opening it may expose you to phishing or malicious content.',
            ),
            const SizedBox(height: 14),
            DecoratedBox(
              decoration: BoxDecoration(
                color: context.qrColors.secondarySurface,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: SelectableText(
                  _destinationDescription,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
              ),
            ),
          ],
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Do not proceed'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: context.qrColors.blocked,
            ),
            child: const Text('I understand — proceed anyway'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _openDestination();
    } else if (confirmed == false && mounted) {
      Navigator.of(context).pop();
    }
  }

  Future<void> _openDestination() async {
    if (_isHiHive) {
      await _openHiHive();
      return;
    }
    if (_duitNow != null) {
      await _openTngEWallet();
      return;
    }
    await _openUrl();
  }

  Future<void> _openTngEWallet() async {
    final opened = await OfficialAppLauncher.openTngEWallet();
    if (!mounted || opened) return;

    final openStore = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.account_balance_wallet_outlined),
        title: const Text('TNG eWallet is not installed'),
        content: const Text(
          'Install the official app, then use Scan/Pay and select the original '
          'DuitNow QR from Gallery. QRGuard never passes an amount or initiates '
          'a transfer automatically.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Open Google Play'),
          ),
        ],
      ),
    );
    if (openStore != true) return;
    final storeUri = Uri.https('play.google.com', '/store/apps/details', {
      'id': 'my.com.tngdigital.ewallet',
    });
    final launched = await launchUrl(
      storeUri,
      mode: LaunchMode.externalApplication,
    );
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open Google Play.')),
      );
    }
  }

  Future<void> _openHiHive() async {
    final opened = await OfficialAppLauncher.openHiHive();
    if (!mounted || opened) return;

    final openStore = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.school_outlined),
        title: const Text('hi-hive is not installed'),
        content: const Text(
          'Install the official hi-hive Community app, then use its scanner on '
          'the original attendance QR. QRGuard does not pass or submit the token.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Open Google Play'),
          ),
        ],
      ),
    );
    if (openStore != true) return;
    final storeUri = Uri.https('play.google.com', '/store/apps/details', {
      'id': 'com.slc.hihive.community',
    });
    final launched = await launchUrl(
      storeUri,
      mode: LaunchMode.externalApplication,
    );
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open Google Play.')),
      );
    }
  }

  Future<void> _openUrl() async {
    final target = _scan.normalizedUrl ?? _scan.payload;
    final uri = target == null ? null : Uri.tryParse(target);
    if (uri == null || !const {'http', 'https'}.contains(uri.scheme)) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('This destination cannot be opened as a web URL.'),
          ),
        );
      }
      return;
    }
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Could not open that URL.')));
    }
  }
}

enum _ResultKind { safe, warning, blocked, partial }

class _VerdictHeader extends StatelessWidget {
  const _VerdictHeader({required this.style});

  final VerdictStyle style;

  @override
  Widget build(BuildContext context) => Card(
    color: style.surface,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 20),
      child: Row(
        children: [
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: style.color, width: 2),
            ),
            child: Icon(style.icon, color: style.color, size: 34),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  style.label,
                  style: TextStyle(
                    color: style.color,
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(style.headline, style: const TextStyle(height: 1.35)),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _UpdatedBanner extends StatelessWidget {
  const _UpdatedBanner({required this.previous, required this.current});

  final int previous;
  final int current;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: context.qrColors.secondarySurface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: context.qrColors.border),
    ),
    child: Padding(
      padding: const EdgeInsets.all(11),
      child: Row(
        children: [
          Icon(Icons.psychology_outlined, color: context.qrColors.brandInk),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              'Updated after Deep Check · risk $previous → $current',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    ),
  );
}

class _PartialNotice extends StatelessWidget {
  const _PartialNotice({required this.scan});

  final ScanResponse scan;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: context.qrColors.warningSurface,
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.warning_amber_rounded, color: context.qrColors.warning),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                scan.couldNotDecode
                    ? 'Partial analysis — the QR payload could not be decoded, so '
                          'the Semantic branch was unavailable.'
                    : 'Partial analysis — one analysis branch was unavailable. '
                          'Unavailable evidence has not been replaced with a score.',
                style: const TextStyle(height: 1.4),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DeepCheckCard extends StatelessWidget {
  const _DeepCheckCard({required this.response});

  final DeepCheckResponse response;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.psychology_outlined, color: context.qrColors.brandInk),
              const SizedBox(width: 8),
              Text(
                'Deep Check — second opinion',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            response.explanation.isEmpty
                ? 'Deep Check did not return an explanation.'
                : response.explanation,
            style: const TextStyle(height: 1.45),
          ),
          if (response.riskFactors.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...response.riskFactors.map(
              (factor) => Padding(
                padding: const EdgeInsets.only(bottom: 7),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '• ',
                      style: TextStyle(color: context.qrColors.brandInk),
                    ),
                    Expanded(child: Text(factor)),
                  ],
                ),
              ),
            ),
          ],
          if (response.redirectChain.length > 1) ...[
            const SizedBox(height: 12),
            const Text(
              'Redirect chain',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            ...response.redirectChain.map(
              (url) => SelectableText(
                '→ $url',
                style: TextStyle(
                  color: context.qrColors.secondaryText,
                  fontFamily: 'monospace',
                  fontSize: 11,
                  height: 1.5,
                ),
              ),
            ),
          ],
          if (!response.llmAvailable) ...[
            const SizedBox(height: 12),
            Text(
              'The original scan result has been preserved.',
              style: TextStyle(color: context.qrColors.warning),
            ),
          ],
        ],
      ),
    ),
  );
}
