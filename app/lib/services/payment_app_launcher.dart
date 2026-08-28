/// Android hand-off to the official Touch 'n Go eWallet application.
///
/// No QR payload, amount or recipient data is passed across this channel. TNG
/// does not publish a supported deep link that accepts a raw DuitNow payload,
/// so the user remains in control of scanning/selecting the QR and confirming
/// the recipient, amount and PIN inside the payment app.
library;

import 'package:flutter/services.dart';

class PaymentAppLauncher {
  static const _channel = MethodChannel(
    'com.osswt.qrguard/external_payment_apps',
  );

  static Future<bool> openTngEWallet() async {
    try {
      return await _channel.invokeMethod<bool>('openTngEWallet') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }
}
