/// Strict, local recognition of a DuitNow merchant-presented QR payload.
///
/// This parser is deliberately UI-only. It does not change the frozen backend
/// verdict or risk score, and it never initiates a payment. A valid payload must
/// contain the Malaysian DuitNow AID and pass its EMV CRC before QRGuard offers
/// a hand-off to a payment app.
library;

import 'dart:convert';

class DuitNowQr {
  const DuitNowQr({
    required this.recipientName,
    required this.merchantCategoryCode,
    required this.isPersonToPerson,
    this.amount,
  });

  static const malaysiaAid = 'A0000006150001';

  final String recipientName;
  final String merchantCategoryCode;
  final bool isPersonToPerson;
  final String? amount;

  String get amountLabel =>
      amount == null ? 'Enter in payment app' : 'MYR $amount';

  static DuitNowQr? tryParse(String? payload) {
    if (payload == null || payload.length < 20 || !_hasValidCrc(payload)) {
      return null;
    }
    final root = _parseTlv(payload);
    if (root == null ||
        root['00'] != '02' ||
        root['53'] != '458' ||
        root['58'] != 'MY') {
      return null;
    }

    var hasDuitNowAid = false;
    for (var tag = 26; tag <= 51; tag++) {
      final template = root[tag.toString().padLeft(2, '0')];
      if (template == null) continue;
      final merchantAccount = _parseTlv(template);
      if (merchantAccount?['00'] == malaysiaAid) {
        hasDuitNowAid = true;
        break;
      }
    }
    if (!hasDuitNowAid) return null;

    final category = root['52'];
    final recipient = root['59']?.trim();
    if (category == null ||
        category.length != 4 ||
        recipient == null ||
        recipient.isEmpty) {
      return null;
    }
    final amount = root['54'];
    if (amount != null &&
        !RegExp(r'^\d{1,10}(?:\.\d{1,2})?$').hasMatch(amount)) {
      return null;
    }

    return DuitNowQr(
      recipientName: recipient,
      merchantCategoryCode: category,
      isPersonToPerson: category == '0000',
      amount: amount,
    );
  }
}

Map<String, String>? _parseTlv(String value) {
  final fields = <String, String>{};
  var offset = 0;
  while (offset < value.length) {
    if (offset + 4 > value.length) return null;
    final tag = value.substring(offset, offset + 2);
    final length = int.tryParse(value.substring(offset + 2, offset + 4));
    if (length == null) return null;
    final start = offset + 4;
    final end = start + length;
    if (end > value.length) return null;
    fields[tag] = value.substring(start, end);
    offset = end;
  }
  return fields;
}

bool _hasValidCrc(String payload) {
  if (payload.length < 8 ||
      payload.substring(payload.length - 8, payload.length - 4) != '6304') {
    return false;
  }
  final expected = int.tryParse(
    payload.substring(payload.length - 4),
    radix: 16,
  );
  if (expected == null) return false;

  var crc = 0xFFFF;
  for (final byte in utf8.encode(payload.substring(0, payload.length - 4))) {
    crc ^= byte << 8;
    for (var bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000) != 0
          ? ((crc << 1) ^ 0x1021) & 0xFFFF
          : (crc << 1) & 0xFFFF;
    }
  }
  return crc == expected;
}
