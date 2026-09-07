import 'dart:io';
import 'dart:typed_data';
import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:mobile_scanner/src/web/capture_motion.dart';

void main() {
  test(
    'balanced module edges pass; horizontal streaks and flat images do not',
    () {
      final balanced = Uint8List(200 * 200 * 4);
      final streaks = Uint8List(200 * 200 * 4);
      for (var y = 0; y < 200; y++) {
        for (var x = 0; x < 200; x++) {
          final index = (y * 200 + x) * 4;
          for (var c = 0; c < 3; c++) {
            balanced[index + c] = ((x ~/ 8 + y ~/ 8) % 2) * 255;
            streaks[index + c] = (y ~/ 8 % 2) * 255;
          }
        }
      }
      expect(directionalDetailRatio(balanced, 200, 200), greaterThan(.9));
      expect(directionalDetailRatio(streaks, 200, 200), lessThan(.25));
      expect(directionalDetailRatio(Uint8List(1600), 20, 20), 0);
    },
  );
  final privateDirectory =
      Platform.environment['QRGUARD_PRIVATE_DIAGNOSTIC_DIR'];
  test(
    'private regression: reject latest motion frame, retain seven clear frames',
    () {
      for (final id in ['1788780669418', '1788781669727', '1788782740117']) {
        final archive = ZipDecoder().decodeBytes(
          File(
            '$privateDirectory/qrguard-diagnostic-$id.zip',
          ).readAsBytesSync(),
        );
        for (var i = 1; i <= 3; i++) {
          final image = img.decodePng(
            archive.findFile('submitted-frame-$i.png')!.content,
          )!;
          final ratio = directionalDetailRatio(
            image.getBytes(order: img.ChannelOrder.rgba),
            image.width,
            image.height,
          );
          if (id == '1788782740117' && i == 2) {
            expect(ratio, lessThan(.25));
          } else if (!(id == '1788781669727' && i == 2)) {
            expect(ratio, greaterThanOrEqualTo(.25));
          }
        }
      }
    },
    skip: privateDirectory == null
        ? 'Private camera archives are not committed'
        : false,
  );
}
