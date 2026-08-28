/// HTTP client for the QRGuard backend.
///
/// Every network failure is turned into an [ApiException] with a message worth showing
/// a user; the UI must never surface a raw socket error. The base URL is configurable
/// because during development the backend runs on a laptop and the phone reaches it
/// over the LAN.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/scan_response.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  const ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    required this.baseUrl,
    http.Client? client,
    this.timeout = _defaultTimeout,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null;

  static const _defaultTimeout = Duration(seconds: 12);

  /// The deep check calls an LLM, so it needs a longer budget than a normal scan.
  static const _deepCheckTimeout = Duration(seconds: 30);

  final String baseUrl;
  final Duration timeout;
  final bool _ownsClient;
  http.Client _client;
  bool _disposed = false;

  Uri _uri(String path) =>
      Uri.parse('${baseUrl.replaceAll(RegExp(r'/+$'), '')}$path');

  /// Startup check: is the backend reachable, and what can it do?
  Future<HealthResponse> health() async {
    final json = await _get('/health');
    return HealthResponse.fromJson(json);
  }

  /// Full scan: the QR image crop plus the text decoded on-device.
  ///
  /// [payload] may be null — the backend then decodes the image itself. The app
  /// normally supplies it because on-device decoding is faster and works offline.
  Future<ScanResponse> scan({
    String? payload,
    Uint8List? imageBytes,
    String imageSource = 'unknown',
  }) async {
    if ((payload == null || payload.trim().isEmpty) && imageBytes == null) {
      throw const ApiException('Nothing to scan.');
    }

    final request = http.MultipartRequest('POST', _uri('/scan'));
    request.fields['image_source'] = imageSource;
    if (payload != null && payload.trim().isNotEmpty) {
      request.fields['payload'] = payload;
    }
    if (imageBytes != null) {
      request.files.add(
        http.MultipartFile.fromBytes('image', imageBytes, filename: 'qr.png'),
      );
    }

    try {
      // Cover both waiting for response headers and consuming the response
      // body. Timing out only `send()` can leave the UI waiting forever when a
      // connection returns headers but stalls while streaming the JSON body.
      final response =
          await (() async {
            final streamed = await _client.send(request);
            return http.Response.fromStream(streamed);
          })().timeout(
            timeout,
            onTimeout: () {
              // Future.timeout stops waiting but does not cancel the socket. Closing
              // an owned client aborts the upload/body stream so a stalled request
              // cannot keep consuming resources behind the Analysing screen. A new
              // client makes the Try Again action a genuinely fresh connection.
              _resetOwnedClient();
              throw TimeoutException('scan request exceeded $timeout');
            },
          );
      return ScanResponse.fromJson(_decode(response));
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(_friendly(e));
    }
  }

  /// Semantic-only path, for payloads with no usable image.
  Future<ScanResponse> analyzeUrl(String payload) async {
    final json = await _post('/analyze-url', {'payload': payload});
    return ScanResponse.fromJson(json);
  }

  /// User-initiated LLM second opinion. Only called when the user taps for it.
  Future<DeepCheckResponse> deepCheck({
    required String payload,
    double? pStructural,
    bool expandRedirects = true,
  }) async {
    final json = await _post('/deep-check', {
      'payload': payload,
      'p_structural': pStructural,
      'expand_redirects': expandRedirects,
    }, timeout: _deepCheckTimeout);
    return DeepCheckResponse.fromJson(json);
  }

  // -- plumbing ------------------------------------------------------------

  Future<Map<String, dynamic>> _get(String path) async {
    try {
      final response = await _client.get(_uri(path)).timeout(timeout);
      return _decode(response);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(_friendly(e));
    }
  }

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body, {
    Duration? timeout,
  }) async {
    try {
      final response = await _client
          .post(
            _uri(path),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(timeout ?? this.timeout);
      return _decode(response);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException(_friendly(e));
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode >= 400) {
      throw ApiException(switch (response.statusCode) {
        422 => 'The server could not read that request.',
        413 => 'That image is too large to analyse.',
        >= 500 => 'The analysis service is having trouble. Try again shortly.',
        _ => 'Request failed (${response.statusCode}).',
      }, statusCode: response.statusCode);
    }
    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw const ApiException('The server sent an unexpected response.');
    }
  }

  /// Network errors become sentences a user can act on.
  String _friendly(Object error) {
    final message = error.toString();
    if (error is FormatException) {
      return 'The server address looks invalid.';
    }
    if (message.contains('TimeoutException')) {
      return 'The analysis service took too long to respond.';
    }
    if (error is http.ClientException ||
        message.contains('SocketException') ||
        message.contains('XMLHttpRequest error')) {
      return 'Cannot reach the analysis service. Check that the backend is running '
          'and that the address in Settings is correct.';
    }
    return 'Could not complete the analysis. Please try again.';
  }

  void _resetOwnedClient() {
    if (!_ownsClient || _disposed) return;
    _client.close();
    _client = http.Client();
  }

  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _client.close();
  }
}
