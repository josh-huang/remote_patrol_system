import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';
import '../models.dart';

class ApiException implements Exception {
  ApiException(this.message, [this.statusCode]);

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

/// Thin client over the Django REST API with JWT auth and token refresh.
class ApiClient {
  ApiClient({http.Client? httpClient, String? baseUrl})
      : _http = httpClient ?? http.Client(),
        _base = baseUrl ?? apiBaseUrl;

  final http.Client _http;
  final String _base;
  String? _access;
  String? _refresh;

  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';

  bool get isAuthenticated => _access != null;

  Future<void> restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    _access = prefs.getString(_accessKey);
    _refresh = prefs.getString(_refreshKey);
  }

  Future<void> login(String username, String password) async {
    final res = await _http.post(
      Uri.parse('$_base/auth/token/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    if (res.statusCode != 200) {
      throw ApiException('Invalid username or password.', res.statusCode);
    }
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    await _saveTokens(data['access'] as String, data['refresh'] as String);
  }

  Future<void> logout() async {
    _access = null;
    _refresh = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }

  Future<void> _saveTokens(String access, String? refresh) async {
    _access = access;
    if (refresh != null) _refresh = refresh;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, access);
    if (_refresh != null) await prefs.setString(_refreshKey, _refresh!);
  }

  Future<bool> _tryRefresh() async {
    if (_refresh == null) return false;
    final res = await _http.post(
      Uri.parse('$_base/auth/token/refresh/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': _refresh}),
    );
    if (res.statusCode != 200) return false;
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    await _saveTokens(data['access'] as String, data['refresh'] as String?);
    return true;
  }

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        if (_access != null) 'Authorization': 'Bearer $_access',
      };

  /// Sends a request, refreshing the access token once on HTTP 401.
  Future<dynamic> _send(Future<http.Response> Function() request) async {
    var res = await request();
    if (res.statusCode == 401 && await _tryRefresh()) {
      res = await request();
    }
    if (res.statusCode == 401) {
      await logout();
      throw ApiException('Session expired. Please sign in again.', 401);
    }
    final body = res.body.isEmpty ? null : jsonDecode(utf8.decode(res.bodyBytes));
    if (res.statusCode >= 400) {
      final detail = body is Map && body['detail'] != null ? body['detail'].toString() : 'Request failed (${res.statusCode}).';
      throw ApiException(detail, res.statusCode);
    }
    return body;
  }

  Future<dynamic> get(String path, [Map<String, String>? query]) => _send(
        () => _http.get(Uri.parse('$_base$path').replace(queryParameters: query), headers: _headers),
      );

  Future<dynamic> postJson(String path, Map<String, dynamic> body) => _send(
        () => _http.post(
          Uri.parse('$_base$path'),
          headers: {..._headers, 'Content-Type': 'application/json'},
          body: jsonEncode(body),
        ),
      );

  Future<dynamic> postMultipart(
    String path, {
    Map<String, String> fields = const {},
    String fileField = 'images',
    List<String> filePaths = const [],
  }) =>
      _send(() async {
        final req = http.MultipartRequest('POST', Uri.parse('$_base$path'))
          ..headers.addAll(_headers)
          ..fields.addAll(fields);
        for (final p in filePaths) {
          req.files.add(await http.MultipartFile.fromPath(fileField, p));
        }
        return http.Response.fromStream(await _http.send(req));
      });

  // ---------------------------------------------------------------------------
  // Endpoints used by the duty phone
  // ---------------------------------------------------------------------------
  Future<RouteInfo> myRoute() async =>
      RouteInfo.fromJson(await get('/mobile/route/') as Map<String, dynamic>);

  Future<void> checkIn(int stopId, {String notes = '', List<String> photos = const []}) =>
      postMultipart('/stops/$stopId/check_in/', fields: {'notes': notes}, filePaths: photos);

  Future<IncidentResult> reportIncident({
    required String description,
    int? locationId,
    List<String> photos = const [],
  }) async {
    final data = await postMultipart(
      '/incidents/',
      fields: {
        'description': description,
        if (locationId != null) 'location': '$locationId',
      },
      fileField: 'uploaded_images',
      filePaths: photos,
    );
    return IncidentResult.fromJson(data as Map<String, dynamic>);
  }

  Future<List<ChatMessage>> messages() async => ((await get('/messages/')) as List)
      .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
      .toList();

  Future<void> sendMessage(String body) => postJson('/messages/', {'body': body});

  Future<void> markMessagesRead() => postJson('/messages/mark_read/', {});

  Future<void> ping(double lat, double lng, double speedKmh) =>
      postJson('/pings/', {'latitude': lat, 'longitude': lng, 'speed_kmh': speedKmh});
}
