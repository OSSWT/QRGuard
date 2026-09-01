import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:qrguard/services/api_client.dart';

void main() {
  test('camera scans never degrade into URL-only multipart requests', () async {
    final client = _StallingBodyClient();
    final api = ApiClient(baseUrl: 'http://127.0.0.1:8001', client: client);

    await expectLater(
      api.scan(payload: 'https://example.com', imageSource: 'camera'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          contains('valid QR image'),
        ),
      ),
    );
    expect(client.calls, 0);
    api.dispose();
  });

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

  test('camera consensus uploads the three selected temporal frames', () async {
    final client = _RecordingMultipartClient();
    final api = ApiClient(baseUrl: 'http://127.0.0.1:8001', client: client);

    final scan = await api.scan(
      payload: 'plain text',
      imageSource: 'camera',
      imageBytes: Uint8List.fromList([1]),
      additionalImageBytes: [
        for (var index = 2; index <= 3; index++) Uint8List.fromList([index]),
      ],
    );

    expect(client.fileFields, ['image', 'images', 'images']);
    expect(client.cameraEvidencePolicy, 'temporal_consensus_v1');
    expect(scan.timingsMs, contains('client_upload_response_headers'));
    expect(scan.timingsMs, contains('client_response_body'));
    api.dispose();
  });

  test('camera scan rejects more than three selected crops', () async {
    final client = _RecordingMultipartClient();
    final api = ApiClient(baseUrl: 'http://127.0.0.1:8001', client: client);

    await expectLater(
      api.scan(
        payload: 'plain text',
        imageSource: 'camera',
        imageBytes: Uint8List.fromList([1]),
        additionalImageBytes: [
          Uint8List.fromList([2]),
          Uint8List.fromList([3]),
          Uint8List.fromList([4]),
        ],
      ),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          contains('At most three'),
        ),
      ),
    );
    expect(client.fileFields, isEmpty);
    api.dispose();
  });
}

class _StallingBodyClient extends http.BaseClient {
  final StreamController<List<int>> _body = StreamController<List<int>>();
  int calls = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    calls++;
    return http.StreamedResponse(_body.stream, 200);
  }

  @override
  void close() {
    _body.close();
    super.close();
  }
}

class _RecordingMultipartClient extends http.BaseClient {
  List<String> fileFields = const [];
  String? cameraEvidencePolicy;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final multipart = request as http.MultipartRequest;
    fileFields = multipart.files.map((file) => file.field).toList();
    cameraEvidencePolicy = multipart.fields['camera_evidence_policy'];
    final body = jsonEncode({
      'verdict': 'safe',
      'risk_score': 1,
      'reasons': <String>[],
      'payload_type': 'text',
      'branch_scores': {
        'structural_status': 'completed',
        'semantic_status': 'not_applicable',
        'image_source': 'camera',
      },
      'partial_analysis': false,
      'deep_check_available': false,
      'payload': 'plain text',
      'payload_source': 'provided',
      'elapsed_ms': 1,
    });
    return http.StreamedResponse(Stream.value(utf8.encode(body)), 200);
  }
}
