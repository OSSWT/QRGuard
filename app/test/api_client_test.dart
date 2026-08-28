import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:qrguard/services/api_client.dart';

void main() {
  test(
    'multipart timeout covers a response body that never completes',
    () async {
      final client = _StallingBodyClient();
      final api = ApiClient(
        baseUrl: 'http://127.0.0.1:8001',
        client: client,
        timeout: const Duration(milliseconds: 30),
      );

      await expectLater(
        api.scan(payload: 'https://example.com'),
        throwsA(
          isA<ApiException>().having(
            (error) => error.message,
            'message',
            contains('took too long'),
          ),
        ),
      );
      api.dispose();
    },
  );
}

class _StallingBodyClient extends http.BaseClient {
  final StreamController<List<int>> _body = StreamController<List<int>>();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async =>
      http.StreamedResponse(_body.stream, 200);

  @override
  void close() {
    _body.close();
    super.close();
  }
}
