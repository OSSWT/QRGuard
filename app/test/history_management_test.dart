import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/screens/history_screen.dart';
import 'package:qrguard/services/history_service.dart';
import 'package:qrguard/theme.dart';
import 'package:sqflite/sqflite.dart';

void main() {
  final records = [
    ScanRecord(
      id: 1,
      payloadHash: 'a' * 64,
      registeredDomain: 'google.com',
      verdict: 'safe',
      riskScore: 8,
      scannedAt: DateTime(2026, 9, 1, 9),
    ),
    ScanRecord(
      id: 2,
      payloadHash: 'b' * 64,
      registeredDomain: 'warning.example',
      verdict: 'warning',
      riskScore: 48,
      scannedAt: DateTime(2026, 9, 1, 9, 1),
    ),
    ScanRecord(
      id: 3,
      payloadHash: 'c' * 64,
      registeredDomain: 'blocked.example',
      verdict: 'blocked',
      riskScore: 92,
      scannedAt: DateTime(2026, 9, 1, 9, 2),
    ),
  ];

  test(
    'Clear All deletes rows and resets the AUTOINCREMENT sequence',
    () async {
      final database = _RecordingDatabase();
      final history = HistoryService.withDatabase(database);

      await history.clear();

      expect(database.transactionCount, 1);
      expect(database.transactionLog.deletes, [
        const _DeleteCall('scans'),
        const _DeleteCall(
          'sqlite_sequence',
          where: 'name = ?',
          whereArgs: ['scans'],
        ),
      ]);
    },
  );

  test('selective deletion removes only unique positive record ids', () async {
    final database = _RecordingDatabase();
    final history = HistoryService.withDatabase(database);

    await history.deleteByIds([3, 3, -1, 7]);

    expect(database.rawDeletes, hasLength(1));
    expect(
      database.rawDeletes.single.sql,
      'DELETE FROM scans WHERE id IN (?, ?)',
    );
    expect(database.rawDeletes.single.arguments, [3, 7]);
  });

  testWidgets('long press selects records and deletes only the selection', (
    tester,
  ) async {
    final history = _FakeHistoryService(records);
    await _pumpHistory(tester, history);

    await tester.longPress(find.text('google.com'));
    await tester.pumpAndSettle();
    expect(find.text('1 selected'), findsOneWidget);

    await tester.tap(find.text('warning.example'));
    await tester.pumpAndSettle();
    expect(find.text('2 selected'), findsOneWidget);

    await tester.tap(find.byTooltip('Delete selected'));
    await tester.pumpAndSettle();
    expect(find.text('Delete 2 selected scans?'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, 'Delete selected'));
    await tester.pumpAndSettle();

    expect(history.deletedIds, {1, 2});
    expect(find.text('blocked.example'), findsOneWidget);
    expect(find.text('google.com'), findsNothing);
    expect(find.text('warning.example'), findsNothing);
  });

  testWidgets('Select all visible respects the active category filter', (
    tester,
  ) async {
    final history = _FakeHistoryService(records);
    await _pumpHistory(tester, history);

    await tester.tap(find.text('Warning (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('History actions'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Select records'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Select all visible'));
    await tester.pumpAndSettle();

    expect(find.text('1 selected'), findsOneWidget);
    await tester.tap(find.byTooltip('Delete selected'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete selected'));
    await tester.pumpAndSettle();

    expect(history.deletedIds, {2});
    expect(history.stored.map((record) => record.id), [1, 3]);
  });

  testWidgets('system Back cancels selection without deleting records', (
    tester,
  ) async {
    final history = _FakeHistoryService(records);
    await _pumpHistory(tester, history);

    await tester.longPress(find.text('google.com'));
    await tester.pumpAndSettle();
    expect(find.text('1 selected'), findsOneWidget);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    expect(find.text('Recent Scans'), findsOneWidget);
    expect(find.text('google.com'), findsOneWidget);
    expect(history.deletedIds, isEmpty);
  });

  testWidgets('Clear all history is kept in the overflow menu', (tester) async {
    final history = _FakeHistoryService(records);
    await _pumpHistory(tester, history);

    expect(find.byTooltip('Clear history'), findsNothing);
    await tester.tap(find.byTooltip('History actions'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Clear all history'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Clear History'));
    await tester.pumpAndSettle();

    expect(history.clearCount, 1);
    expect(find.text('No recent scans'), findsOneWidget);
  });
}

Future<void> _pumpHistory(
  WidgetTester tester,
  _FakeHistoryService history,
) async {
  tester.view.physicalSize = const Size(900, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: buildTheme(Brightness.dark),
      home: HistoryScreen(history: history),
    ),
  );
  await tester.pumpAndSettle();
}

class _FakeHistoryService extends HistoryService {
  _FakeHistoryService(Iterable<ScanRecord> records) : stored = List.of(records);

  final List<ScanRecord> stored;
  final Set<int> deletedIds = {};
  int clearCount = 0;

  @override
  Future<List<ScanRecord>> recent({int limit = 50}) async =>
      List.unmodifiable(stored.take(limit));

  @override
  Future<void> deleteByIds(Iterable<int> recordIds) async {
    deletedIds.addAll(recordIds);
    stored.removeWhere((record) => deletedIds.contains(record.id));
  }

  @override
  Future<void> clear() async {
    clearCount++;
    stored.clear();
  }
}

class _RecordingDatabase implements Database {
  final _RecordingTransaction transactionLog = _RecordingTransaction();
  final List<_RawDeleteCall> rawDeletes = [];
  int transactionCount = 0;

  @override
  Future<T> transaction<T>(
    Future<T> Function(Transaction txn) action, {
    bool? exclusive,
  }) async {
    transactionCount++;
    return action(transactionLog);
  }

  @override
  Future<int> rawDelete(String sql, [List<Object?>? arguments]) async {
    rawDeletes.add(_RawDeleteCall(sql, arguments ?? const []));
    return 0;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _RecordingTransaction implements Transaction {
  final List<_DeleteCall> deletes = [];

  @override
  Future<int> delete(
    String table, {
    String? where,
    List<Object?>? whereArgs,
  }) async {
    deletes.add(_DeleteCall(table, where: where, whereArgs: whereArgs));
    return 0;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _DeleteCall {
  const _DeleteCall(this.table, {this.where, this.whereArgs});

  final String table;
  final String? where;
  final List<Object?>? whereArgs;

  @override
  bool operator ==(Object other) =>
      other is _DeleteCall &&
      other.table == table &&
      other.where == where &&
      _listEquals(other.whereArgs, whereArgs);

  @override
  int get hashCode =>
      Object.hash(table, where, Object.hashAll(whereArgs ?? []));
}

class _RawDeleteCall {
  const _RawDeleteCall(this.sql, this.arguments);

  final String sql;
  final List<Object?> arguments;
}

bool _listEquals(List<Object?>? left, List<Object?>? right) {
  if (identical(left, right)) {
    return true;
  }
  if (left == null || right == null || left.length != right.length) {
    return false;
  }
  for (var index = 0; index < left.length; index++) {
    if (left[index] != right[index]) {
      return false;
    }
  }
  return true;
}
