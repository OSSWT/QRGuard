import 'dart:async';
import 'dart:js_interop';
import 'dart:typed_data';
import 'package:web/web.dart' as web;

void downloadPreview(Uint8List bytes) {
  final blob = web.Blob(
    [bytes.toJS].toJS,
    web.BlobPropertyBag(type: 'application/zip'),
  );
  final url = web.URL.createObjectURL(blob);
  final anchor = web.HTMLAnchorElement()
    ..href = url
    ..download =
        'qrguard-diagnostic-${DateTime.now().millisecondsSinceEpoch}.zip';
  web.document.body!.appendChild(anchor);
  anchor.click();
  anchor.remove();
  Timer(const Duration(minutes: 1), () => web.URL.revokeObjectURL(url));
}
