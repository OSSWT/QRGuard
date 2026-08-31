/// Destination, server-originated reasons and transparent branch evidence.
library;

import 'package:flutter/material.dart';

import '../models/scan_response.dart';
import '../services/duitnow_qr.dart';
import '../theme.dart';

/// Removes repeated display wording while preserving the backend's strongest,
/// most specific evidence. The fusion engine may return a generic reason and
/// the rule engine may then add a more useful version naming the exact TLD.
List<String> deduplicateAnalysisReasons(Iterable<String> reasons) {
  final cleaned = reasons
      .map((reason) => reason.trim())
      .where((reason) => reason.isNotEmpty)
      .toList();
  final hasSpecificTld = cleaned.any(
    (reason) => reason.toLowerCase().contains('frequently-abused tld'),
  );
  final seen = <String>{};
  return [
    for (final reason in cleaned)
      if (!(hasSpecificTld &&
              reason.toLowerCase() ==
                  'domain uses a frequently-abused extension') &&
          seen.add(reason.toLowerCase()))
        reason,
  ];
}

class VerdictSummaryCard extends StatelessWidget {
  const VerdictSummaryCard({
    super.key,
    required this.summary,
    required this.color,
    required this.title,
  });

  final String summary;
  final Color color;
  final String title;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 3),
                child: Icon(Icons.info_rounded, size: 18, color: color),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(summary, style: const TextStyle(height: 1.5)),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class AnalysisReasonDetails extends StatelessWidget {
  const AnalysisReasonDetails({super.key, required this.reasons});

  final List<String> reasons;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Analysis reasons',
        style: Theme.of(
          context,
        ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      ...reasons.map(
        (reason) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 3),
                child: Icon(
                  Icons.circle,
                  size: 7,
                  color: context.qrColors.brandInk,
                ),
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Text(reason, style: const TextStyle(height: 1.4)),
              ),
            ],
          ),
        ),
      ),
    ],
  );
}

class DestinationCard extends StatelessWidget {
  const DestinationCard({super.key, required this.scan});

  final ScanResponse scan;

  @override
  Widget build(BuildContext context) {
    final colors = context.qrColors;
    final duitNow = DuitNowQr.tryParse(scan.payload);
    final title = duitNow != null
        ? 'DuitNow payment QR'
        : scan.isUrl
        ? 'Destination URL'
        : 'QR content';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  duitNow != null
                      ? Icons.account_balance_wallet_outlined
                      : scan.isUrl
                      ? Icons.link_rounded
                      : Icons.qr_code_2_rounded,
                  size: 18,
                  color: colors.brandInk,
                ),
                const SizedBox(width: 7),
                Text(
                  title,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: colors.secondaryText,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (duitNow != null)
              _DuitNowDetails(payment: duitNow)
            else
              SelectableText(
                scan.displayTarget,
                style: TextStyle(
                  color: colors.primaryText,
                  fontFamily: 'monospace',
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
            if (scan.registeredDomain != null) ...[
              const SizedBox(height: 10),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: colors.secondarySurface,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 9,
                    vertical: 6,
                  ),
                  child: Text(
                    'Registered domain: ${scan.registeredDomain}',
                    style: TextStyle(color: colors.secondaryText, fontSize: 12),
                  ),
                ),
              ),
              const SizedBox(height: 7),
              Text(
                'Extracted from the URL; this does not verify ownership or guarantee safety.',
                style: TextStyle(
                  color: colors.secondaryText,
                  fontSize: 11,
                  height: 1.35,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _DuitNowDetails extends StatelessWidget {
  const _DuitNowDetails({required this.payment});

  final DuitNowQr payment;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _PaymentField(label: 'Recipient', value: payment.recipientName),
      const SizedBox(height: 8),
      _PaymentField(label: 'Amount', value: payment.amountLabel),
      const SizedBox(height: 8),
      _PaymentField(
        label: 'Type',
        value: payment.isPersonToPerson
            ? 'Person-to-person DuitNow QR'
            : 'Merchant DuitNow QR',
      ),
      const SizedBox(height: 12),
      Text(
        'Verify the recipient and amount again inside the payment app before '
        'authorising. QRGuard does not initiate the transfer.',
        style: TextStyle(
          color: context.qrColors.secondaryText,
          fontSize: 12,
          height: 1.4,
        ),
      ),
    ],
  );
}

class _PaymentField extends StatelessWidget {
  const _PaymentField({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SizedBox(
        width: 72,
        child: Text(
          label,
          style: TextStyle(
            color: context.qrColors.secondaryText,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      Expanded(
        child: Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
      ),
    ],
  );
}

class BranchEvidence extends StatelessWidget {
  const BranchEvidence({super.key, required this.scan});

  final ScanResponse scan;

  @override
  Widget build(BuildContext context) {
    final branch = scan.branchScores;
    final reasons = deduplicateAnalysisReasons(scan.reasons);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth >= 420
                ? (constraints.maxWidth - 16) / 3
                : constraints.maxWidth;
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _MetricTile(
                  width: width,
                  label: 'Structural',
                  value: branch.pStructural?.toStringAsFixed(2) ?? '—',
                  detail: _structuralDetail(branch),
                ),
                _MetricTile(
                  width: width,
                  label: 'Semantic',
                  value: branch.pUrl?.toStringAsFixed(2) ?? '—',
                  detail: _semanticDetail(branch, scan.payloadType),
                ),
                _MetricTile(
                  width: width,
                  label: 'Risk',
                  value: '${scan.riskScore}',
                  detail: 'Integer / 100',
                ),
              ],
            );
          },
        ),
        if (branch.llmScore != null) ...[
          const SizedBox(height: 10),
          _EvidenceRow(
            icon: Icons.psychology_outlined,
            label: 'Deep Check signal',
            value: branch.llmScore!.toStringAsFixed(2),
          ),
        ],
        if (branch.domainUnknown != null) ...[
          const SizedBox(height: 10),
          _EvidenceRow(
            icon: Icons.public_rounded,
            label: 'Domain recognition',
            value: branch.domainUnknown == 1
                ? 'Not widely recognised'
                : 'Widely recognised',
          ),
        ],
        if (scan.ruleFlags.isNotEmpty) ...[
          const SizedBox(height: 14),
          Text(
            'Rule signals',
            style: Theme.of(
              context,
            ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: scan.ruleFlags
                .map(
                  (flag) => Chip(
                    label: Text(flag, style: const TextStyle(fontSize: 11)),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                )
                .toList(),
          ),
        ],
        if (reasons.isNotEmpty) ...[
          const SizedBox(height: 14),
          AnalysisReasonDetails(reasons: reasons),
        ],
        const SizedBox(height: 14),
        Text(
          'Analysed in ${scan.elapsedMs} ms',
          style: TextStyle(color: context.qrColors.secondaryText, fontSize: 12),
        ),
      ],
    );
  }

  String _structuralDetail(BranchScores branch) =>
      switch (branch.structuralStatus) {
        AnalysisStatus.completed =>
          branch.structuralFramesAnalyzed >= 3
              ? '${branch.structuralType ?? 'Analysed'} · '
                    '${branch.structuralFramesAnalyzed}-frame consensus'
              : branch.structuralType ?? 'Analysed',
        AnalysisStatus.notApplicable => 'Not applicable',
        AnalysisStatus.unavailable => 'Unavailable',
        AnalysisStatus.inconclusive =>
          branch.structuralRescanReason ?? 'Rescan required',
      };

  String _semanticDetail(BranchScores branch, String payloadType) =>
      switch (branch.semanticStatus) {
        AnalysisStatus.completed => 'URL model',
        AnalysisStatus.notApplicable => switch (payloadType) {
          'wifi' => 'Not applicable · Wi-Fi QR',
          'payment' => 'Not applicable · Payment QR',
          'text' => 'Not applicable · Text QR',
          _ => 'Not applicable · Non-URL QR',
        },
        AnalysisStatus.unavailable => 'Unavailable',
        AnalysisStatus.inconclusive => 'No reliable result',
      };
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.width,
    required this.label,
    required this.value,
    required this.detail,
  });

  final double width;
  final String label;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    child: DecoratedBox(
      decoration: BoxDecoration(
        color: context.qrColors.secondarySurface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: context.qrColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: context.qrColors.secondaryText,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(detail, style: const TextStyle(fontSize: 12)),
                ],
              ),
            ),
            Text(
              value,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _EvidenceRow extends StatelessWidget {
  const _EvidenceRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final labelRow = Row(
        children: [
          Icon(icon, size: 18, color: context.qrColors.brandInk),
          const SizedBox(width: 9),
          Expanded(child: Text(label)),
        ],
      );
      if (constraints.maxWidth < 300) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            labelRow,
            const SizedBox(height: 5),
            Padding(
              padding: const EdgeInsets.only(left: 27),
              child: Text(
                value,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ],
        );
      }
      return Row(
        children: [
          Expanded(flex: 3, child: labelRow),
          const SizedBox(width: 12),
          Flexible(
            flex: 2,
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      );
    },
  );
}
