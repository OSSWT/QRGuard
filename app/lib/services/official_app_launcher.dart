/// Android hand-off to official applications used by supported QR workflows.
///
/// QRGuard never passes a payment or attendance token across this channel. It
/// only opens the installed official app, where the user remains in control of
/// scanning the original code and confirming the action.
library;

import 'package:flutter/services.dart';

class OfficialAppLauncher {
  static const _channel = MethodChannel('com.osswt.qrguard/external_apps');

  static Future<bool> openTngEWallet() => _open('openTngEWallet');

  static Future<bool> openHiHive() => _open('openHiHive');

  static Future<bool> _open(String method) async {
    try {
      return await _channel.invokeMethod<bool>(method) ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }
}
