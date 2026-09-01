/// Searchable, privacy-preserving scan history and stored result summaries.
library;

import 'package:flutter/material.dart';

import '../models/scan_response.dart';
import '../services/history_service.dart';
import '../theme.dart';
import '../widgets/reason_card.dart';

enum HistoryCategory { all, safe, warning, blocked }

enum _HistoryMenuAction { selectRecords, clearAll }

List<ScanRecord> filterHistoryRecords(
  List<ScanRecord> records, {
  String query = '',
  HistoryCategory category = HistoryCategory.all,
}) {
  final needle = query.trim().toLowerCase();
  return records
      .where((record) {
        final categoryMatches = switch (category) {
          HistoryCategory.all => true,
          HistoryCategory.safe => record.verdictEnum == Verdict.safe,
          HistoryCategory.warning => record.verdictEnum == Verdict.warning,
          HistoryCategory.blocked => record.verdictEnum == Verdict.blocked,
        };
        if (!categoryMatches) return false;
        if (needle.isEmpty) return true;
        return (record.registeredDomain ?? 'Non-URL QR').toLowerCase().contains(
              needle,
            ) ||
            record.payloadHash.toLowerCase().contains(needle) ||
            record.verdict.toLowerCase().contains(needle) ||
            record.riskScore.toString().contains(needle);
      })
      .toList(growable: false);
}

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key, required this.history});

  final HistoryService history;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late Future<List<ScanRecord>> _records = widget.history.recent(limit: 200);
  final _search = TextEditingController();
  HistoryCategory _category = HistoryCategory.all;
  List<ScanRecord> _loadedRecords = const [];
  final Set<int> _selectedIds = {};
  bool _selectionMode = false;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _enterSelection([int? recordId]) {
    setState(() {
      _selectionMode = true;
      if (recordId != null) _selectedIds.add(recordId);
    });
  }

  void _exitSelection() {
    setState(() {
      _selectionMode = false;
      _selectedIds.clear();
    });
  }

  void _toggleSelection(int recordId) {
    setState(() {
      if (!_selectedIds.remove(recordId)) _selectedIds.add(recordId);
    });
  }

  void _selectAllVisible() {
    final visibleIds = filterHistoryRecords(
      _loadedRecords,
      query: _search.text,
      category: _category,
    ).map((record) => record.id).whereType<int>();
    setState(() => _selectedIds.addAll(visibleIds));
  }

  Future<void> _clear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: Icon(
          Icons.delete_outline_rounded,
          color: context.qrColors.blocked,
        ),
        title: const Text('Clear scan history?'),
        content: const Text(
          'This permanently removes the locally stored history records. It does '
          'not affect the backend.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: context.qrColors.blocked,
            ),
            child: const Text('Clear History'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.history.clear();
    if (mounted) {
      _search.clear();
      setState(() {
        _category = HistoryCategory.all;
        _selectionMode = false;
        _selectedIds.clear();
        _records = widget.history.recent(limit: 200);
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Scan history cleared.')));
    }
  }

  Future<void> _deleteSelected() async {
    if (_selectedIds.isEmpty) return;
    final count = _selectedIds.length;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: Icon(
          Icons.delete_outline_rounded,
          color: context.qrColors.blocked,
        ),
        title: Text('Delete $count selected ${count == 1 ? 'scan' : 'scans'}?'),
        content: const Text(
          'This permanently removes only the selected local history records.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(
              foregroundColor: context.qrColors.blocked,
            ),
            child: const Text('Delete selected'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.history.deleteByIds(_selectedIds);
    if (!mounted) return;
    setState(() {
      _selectionMode = false;
      _selectedIds.clear();
      _records = widget.history.recent(limit: 200);
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$count ${count == 1 ? 'scan' : 'scans'} deleted.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_selectionMode,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop && _selectionMode) _exitSelection();
    },
    child: Scaffold(
      appBar: AppBar(
        leading: _selectionMode
            ? IconButton(
                tooltip: 'Cancel selection',
                onPressed: _exitSelection,
                icon: const Icon(Icons.close_rounded),
              )
            : null,
        title: Text(
          _selectionMode ? '${_selectedIds.length} selected' : 'Recent Scans',
        ),
        actions: _selectionMode
            ? [
                IconButton(
                  tooltip: 'Select all visible',
                  onPressed: _selectAllVisible,
                  icon: const Icon(Icons.select_all_rounded),
                ),
                IconButton(
                  tooltip: 'Delete selected',
                  onPressed: _selectedIds.isEmpty ? null : _deleteSelected,
                  icon: const Icon(Icons.delete_outline_rounded),
                ),
              ]
            : [
                PopupMenuButton<_HistoryMenuAction>(
                  tooltip: 'History actions',
                  icon: const Icon(Icons.more_vert_rounded),
                  onSelected: (action) async {
                    switch (action) {
                      case _HistoryMenuAction.selectRecords:
                        _enterSelection();
                      case _HistoryMenuAction.clearAll:
                        await _clear();
                    }
                  },
                  itemBuilder: (context) => const [
                    PopupMenuItem(
                      value: _HistoryMenuAction.selectRecords,
                      child: ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(Icons.checklist_rounded),
                        title: Text('Select records'),
                      ),
                    ),
                    PopupMenuItem(
                      value: _HistoryMenuAction.clearAll,
                      child: ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(Icons.delete_sweep_outlined),
                        title: Text('Clear all history'),
                      ),
                    ),
                  ],
                ),
              ],
      ),
      body: FutureBuilder<List<ScanRecord>>(
        future: _records,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final records = snapshot.data ?? const [];
          _loadedRecords = records;
          if (records.isEmpty) return const _EmptyHistory();

          final filtered = filterHistoryRecords(
            records,
            query: _search.text,
            category: _category,
          );
          return Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Search domain, verdict or SHA-256 hash',
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: _search.text.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Clear search',
                            onPressed: () {
                              _search.clear();
                              setState(() {});
                            },
                            icon: const Icon(Icons.close_rounded),
                          ),
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  'CATEGORIES',
                  style: TextStyle(
                    color: context.qrColors.brandInk,
                    fontWeight: FontWeight.w800,
                    fontSize: 12,
                    letterSpacing: 1.3,
                  ),
                ),
                const SizedBox(height: 8),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: HistoryCategory.values
                        .map(
                          (category) => Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: FilterChip(
                              selected: _category == category,
                              label: Text(
                                '${_categoryLabel(category)} '
                                '(${_categoryCount(records, category)})',
                              ),
                              onSelected: (_) =>
                                  setState(() => _category = category),
                            ),
                          ),
                        )
                        .toList(growable: false),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '${filtered.length} stored ${filtered.length == 1 ? 'scan' : 'scans'}',
                  style: TextStyle(
                    color: context.qrColors.secondaryText,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: filtered.isEmpty
                      ? const _NoMatches()
                      : ListView.separated(
                          padding: const EdgeInsets.only(bottom: 32),
                          itemCount: filtered.length,
                          separatorBuilder: (_, _) =>
                              const SizedBox(height: 10),
                          itemBuilder: (context, index) {
                            final record = filtered[index];
                            final recordId = record.id;
                            return ScanHistoryTile(
                              record: record,
                              selectionMode: _selectionMode,
                              selected:
                                  recordId != null &&
                                  _selectedIds.contains(recordId),
                              onTap: _selectionMode && recordId != null
                                  ? () => _toggleSelection(recordId)
                                  : null,
                              onLongPress: recordId == null
                                  ? null
                                  : () => _enterSelection(recordId),
                            );
                          },
                        ),
                ),
              ],
            ),
          );
        },
      ),
    ),
  );
}

class ScanHistoryTile extends StatelessWidget {
  const ScanHistoryTile({
    super.key,
    required this.record,
    this.compact = false,
    this.selectionMode = false,
    this.selected = false,
    this.onTap,
    this.onLongPress,
  });

  final ScanRecord record;
  final bool compact;
  final bool selectionMode;
  final bool selected;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final style = VerdictStyle.of(context, record.verdictEnum);
    return Card(
      color: selected
          ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.12)
          : null,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: selectionMode
            ? onTap
            : onTap ??
                  () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => HistoryRecordScreen(record: record),
                    ),
                  ),
        onLongPress: onLongPress,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: 14,
            vertical: compact ? 11 : 14,
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: style.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(style.icon, color: style.color, size: 21),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      record.registeredDomain ?? 'Non-URL QR',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${formatScanTime(record.scannedAt)} · Risk ${record.riskScore}',
                      style: TextStyle(
                        color: context.qrColors.secondaryText,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              if (selectionMode)
                Checkbox(
                  value: selected,
                  onChanged: onTap == null ? null : (_) => onTap!(),
                )
              else
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(style.icon, color: style.color, size: 16),
                        const SizedBox(width: 4),
                        Text(
                          style.label,
                          style: TextStyle(
                            color: style.color,
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Icon(
                      Icons.chevron_right_rounded,
                      color: context.qrColors.secondaryText,
                      size: 18,
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class HistoryRecordScreen extends StatelessWidget {
  const HistoryRecordScreen({super.key, required this.record});

  final ScanRecord record;

  String get _summaryTitle => switch (record.verdictEnum) {
    Verdict.safe => 'Why this was marked Safe',
    Verdict.warning => 'Why this needs caution',
    Verdict.blocked => 'Why this was Blocked',
  };

  String get _summaryText => switch (record.verdictEnum) {
    Verdict.safe =>
      'The saved Structural, Semantic and Risk evidence found no strong risk indicators. '
          'Sites and QR codes can change, so scan again before relying on this older result.',
    Verdict.warning =>
      'The saved Structural, Semantic and Risk evidence contained signals that '
          'required caution. Scan the QR again before acting on this older result.',
    Verdict.blocked =>
      'The saved Structural, Semantic and Risk evidence classified this scan as '
          'high risk. Do not rely on an older result without scanning again.',
  };

  @override
  Widget build(BuildContext context) {
    final style = VerdictStyle.of(context, record.verdictEnum);
    final storedAnalysis = record.storedAnalysis;
    return Scaffold(
      appBar: AppBar(title: const Text('Recent scan')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          Card(
            color: style.surface,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Icon(style.icon, color: style.color, size: 44),
                  const SizedBox(height: 10),
                  Text(
                    style.label,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: style.color,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    'Risk score ${record.riskScore} / 100',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          if (storedAnalysis != null) ...[
            Card(
              child: ExpansionTile(
                initiallyExpanded: true,
                maintainState: true,
                shape: const Border(),
                collapsedShape: const Border(),
                title: const Text(
                  'Details',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: const Text('Structural, Semantic and Risk evidence'),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: [BranchEvidence(scan: storedAnalysis)],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline_rounded, color: style.color),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _summaryTitle,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 7),
                        Text(_summaryText, style: const TextStyle(height: 1.4)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                children: [
                  _DetailRow(
                    icon: Icons.language_rounded,
                    label: 'Registered domain',
                    value: record.registeredDomain ?? 'Non-URL QR',
                  ),
                  const Divider(height: 26),
                  _DetailRow(
                    icon: Icons.schedule_rounded,
                    label: 'Scanned at',
                    value: formatFullScanTime(record.scannedAt),
                  ),
                  const Divider(height: 26),
                  _DetailRow(
                    icon: Icons.tag_rounded,
                    label: 'History record',
                    value: record.id?.toString() ?? 'Local record',
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ExpansionTile(
              initiallyExpanded: false,
              maintainState: true,
              shape: const Border(),
              collapsedShape: const Border(),
              leading: Icon(
                Icons.privacy_tip_outlined,
                color: context.qrColors.brandInk,
              ),
              title: const Text(
                'Privacy details',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: const Text(
                'Stored payload fingerprint and data limits',
              ),
              childrenPadding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
              children: [
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Payload SHA-256',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 10),
                SelectableText(
                  record.payloadHash,
                  style: TextStyle(
                    color: context.qrColors.secondaryText,
                    fontFamily: 'monospace',
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 14),
                const Text(
                  'The raw URL, URL path, query, QR image and free-text reasons '
                  'were never stored. History keeps only the payload fingerprint, '
                  'registered domain, verdict and non-identifying analysis signals.',
                  style: TextStyle(height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, color: context.qrColors.brandInk, size: 22),
      const SizedBox(width: 11),
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
            Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    ],
  );
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.history_rounded,
            size: 44,
            color: context.qrColors.secondaryText,
          ),
          const SizedBox(height: 12),
          const Text(
            'No recent scans',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 5),
          Text(
            'Scanned domains will appear here without their full URLs.',
            textAlign: TextAlign.center,
            style: TextStyle(color: context.qrColors.secondaryText),
          ),
        ],
      ),
    ),
  );
}

class _NoMatches extends StatelessWidget {
  const _NoMatches();

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.search_off_rounded,
            size: 40,
            color: context.qrColors.secondaryText,
          ),
          const SizedBox(height: 10),
          const Text(
            'No matching scans',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            'Try another search or category.',
            style: TextStyle(color: context.qrColors.secondaryText),
          ),
        ],
      ),
    ),
  );
}

String _categoryLabel(HistoryCategory category) => switch (category) {
  HistoryCategory.all => 'All',
  HistoryCategory.safe => 'Safe',
  HistoryCategory.warning => 'Warning',
  HistoryCategory.blocked => 'Blocked',
};

int _categoryCount(List<ScanRecord> records, HistoryCategory category) =>
    filterHistoryRecords(records, category: category).length;

String formatScanTime(DateTime time) {
  final local = time.toLocal();
  final now = DateTime.now();
  final clock =
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
  if (local.year == now.year &&
      local.month == now.month &&
      local.day == now.day) {
    return 'Today · $clock';
  }
  final date =
      '${local.year}-${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
  return '$date · $clock';
}

String formatFullScanTime(DateTime time) {
  final local = time.toLocal();
  return '${local.year}-${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}:'
      '${local.second.toString().padLeft(2, '0')}';
}
