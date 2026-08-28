import 'package:flutter_test/flutter_test.dart';
import 'package:qrguard/services/duitnow_qr.dart';

void main() {
  const payNetP2pExample =
      '00020201021126410014A000000615000101065016640209123456789'
      '520400005303458540510.005802MY5909AUSERNAME6005BANGI63043A23';

  test('recognises a CRC-valid Malaysian DuitNow P2P QR', () {
    final payment = DuitNowQr.tryParse(payNetP2pExample);

    expect(payment, isNotNull);
    expect(payment!.recipientName, 'AUSERNAME');
    expect(payment.isPersonToPerson, isTrue);
    expect(payment.amountLabel, 'MYR 10.00');
  });

  test('rejects a DuitNow-looking payload with a modified CRC', () {
    expect(
      DuitNowQr.tryParse(
        '${payNetP2pExample.substring(0, payNetP2pExample.length - 1)}4',
      ),
      isNull,
    );
  });

  test('does not mistake an ordinary URL for a payment QR', () {
    expect(DuitNowQr.tryParse('https://www.google.com/maps'), isNull);
  });
}
