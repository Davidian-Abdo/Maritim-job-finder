import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/foundation.dart'; // Add this for kIsWeb
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;

class ApiClient extends ChangeNotifier {
  // Use localhost for Web/Desktop and 10.0.2.2 for Android Emulator
  static String get _baseUrl {
    if (kIsWeb) {
      if (kDebugMode) {
      // When running locally in debug mode, use your local backend
      return 'http://localhost:8000';
      }

      return const String.fromEnvironment(
        'API_URL',
        defaultValue: 'https://maritimjobsapi.duckdns.org',
      );
    }

    return 'http://10.0.2.2:8000'; // Android emulator
  }

  // Web doesn't support the default "encrypted" storage of this plugin 
  // without extra config. For dev, use the web-friendly options:
  final _storage = const FlutterSecureStorage(
    webOptions: WebOptions(dbName: 'my_app_db', publicKey: 'my_app_key'),
  );
  String? _token;

  bool _initialized = false;
  bool get isInitialized => _initialized;

  bool get isLoggedIn => _token != null;

  ApiClient();

  // ================= LOAD TOKEN =================

  Future<void> loadToken() async {
    _token = await _storage.read(key: 'access_token');
    _initialized = true;
    notifyListeners();
  }

  Future<void> saveToken(String token) async {
    _token = token;
    await _storage.write(key: 'access_token', value: token);
    notifyListeners();
  }

  Future<void> logout() async {
    _token = null;
    await _storage.delete(key: 'access_token');
    notifyListeners();
  }

  // ================= HEADERS =================

  Map<String, String> _headers({bool auth = true}) {
    final headers = {
      'Content-Type': 'application/json',
    };

    if (auth && _token != null) {
      headers['Authorization'] = 'Bearer $_token';
    }

    return headers;
  }

  // ================= AUTH =================

  Future<void> login(String email, String password) async {
    print("URL: $_baseUrl/auth/login");
    print("Payload: username=$email, password=$password");
    final res = await http.post(
      Uri.parse('$_baseUrl/auth/login'),
      // 1. Change headers to use form-urlencoded
      headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
      },
      // 2. Send as a Map, NOT jsonEncode
      body: {'username': email, 'password': password},
    );

    if (res.statusCode != 200) { 
      throw Exception('Login failed: ${res.body}');
    }

    final data = jsonDecode(res.body);
    await saveToken(data['access_token']);
  }

  Future<void> register(
    String email,
    String password,
    String? fullName,
  ) async {
    final res = await http.post(
      Uri.parse('$_baseUrl/auth/register'),
      headers: _headers(auth: false),
      body: jsonEncode({
        'email': email,
        'password': password,
        'full_name': fullName,
      }),
    );

    if (res.statusCode != 200) {
      throw Exception('Register failed: ${res.body}');
    }
  }
  
  // ================= SCRAPING =================

  Future<void> triggerScrape() async {
    final res = await http.post(
      Uri.parse('$_baseUrl/scrape/trigger'),
      headers: _headers(),
    );
    if (res.statusCode != 202) {
      throw Exception('Failed to trigger scrape: ${res.body}');
    }
  }

  Future<Map<String, dynamic>> getScrapeStatus() async {
    final res = await http.get(
      Uri.parse('$_baseUrl/scrape/status'),
      headers: _headers(),
    );
    if (res.statusCode != 200) {
      throw Exception('Failed to get scrape status: ${res.body}');
    }
    return jsonDecode(res.body);
  }

  Future<void> setSchedule(bool isActive, String? cron) async {
    final res = await http.put(
      Uri.parse('$_baseUrl/scrape/schedule'),
      headers: _headers(),
      body: jsonEncode({
        'is_active': isActive,
        'cron_expression': cron,
      }),
    );
    if (res.statusCode != 200) {
      throw Exception('Failed to set schedule: ${res.body}');
    }
  }

  Future<Map<String, dynamic>> getSchedule() async {
    final res = await http.get(
      Uri.parse('$_baseUrl/scrape/schedule'),
      headers: _headers(),
    );
    if (res.statusCode != 200) {
      throw Exception('Failed to get schedule: ${res.body}');
    }
    return jsonDecode(res.body);
  }

  // ================= JOBS =================

  Future<List<Job>> getJobs({
    String? rank,
    String? location,
    String? vesselType,
    String? title,
    String? company,
    int limit = 20,
    int offset = 0,
  }) async {
    final uri = Uri.parse('$_baseUrl/jobs/').replace(
      queryParameters: {
        if (rank != null) 'rank': rank,
        if (location != null) 'location': location,
        if (vesselType != null) 'vessel_type': vesselType,
        if (title != null) 'title': title,
        if (company != null) 'company': company,
        'limit': limit.toString(),
        'offset': offset.toString(),
      },
    );

    final res = await http.get(uri, headers: _headers());

    if (res.statusCode == 401) {
      await logout();
      throw Exception('Session expired. Please login again.');
    }

    if (res.statusCode != 200) {
      throw Exception('Failed to fetch jobs: ${res.body}');
    }

    final List list = jsonDecode(res.body);

    return list.map((e) => Job.fromJson(e)).toList();
  }

  Future<List<Job>> getSavedJobs() async {
    final res = await http.get(
      Uri.parse('$_baseUrl/jobs/saved'),
      headers: _headers(),
    );

    if (res.statusCode == 401) {
      throw Exception('Session expired. Please login again.');
    }

    if (res.statusCode != 200) {
      throw Exception('Failed to fetch saved jobs: ${res.body}');
    }

    final List list = jsonDecode(res.body);

    return list.map((e) => Job.fromJson(e)).toList();
  }

  Future<void> saveJob(int jobId) async {
    final res = await http.post(
      Uri.parse('$_baseUrl/jobs/save'),
      headers: _headers(),
      body: jsonEncode({'job_id': jobId}),
    );

    if (res.statusCode != 201) {
      throw Exception(res.body);
    }
  }

  Future<void> unsaveJob(int jobId) async {
    final res = await http.delete(
      Uri.parse('$_baseUrl/jobs/unsave/$jobId'),
      headers: _headers(),
    );

    if (res.statusCode != 200) {
      throw Exception(res.body);
    }
  }

  // ================= PROFILE =================
  Future<Map<String, dynamic>> getProfile() async {
    final res = await http.get(Uri.parse('$_baseUrl/profile/'), headers: _headers());
    if (res.statusCode != 200) throw Exception('Failed to get profile: ${res.body}');
    return jsonDecode(res.body);
  }

  Future<void> updateProfile({List<String>? selectedSources}) async {
    final body = <String, dynamic>{};
    if (selectedSources != null) body['selected_sources'] = selectedSources;
    final res = await http.put(
      Uri.parse('$_baseUrl/profile/'),
      headers: _headers(),
      body: jsonEncode(body),
    );
    if (res.statusCode != 200) throw Exception('Failed to update profile: ${res.body}');
  }

  Future<List<String>> getKeywords() async {
    final res = await http.get(Uri.parse('$_baseUrl/profile/keywords'), headers: _headers());
    if (res.statusCode != 200) throw Exception('Failed to get keywords: ${res.body}');
    final List list = jsonDecode(res.body);
    return list.cast<String>();
  }

  Future<void> addKeyword(String keyword) async {
    final res = await http.post(
      Uri.parse('$_baseUrl/profile/keywords'),
      headers: _headers(),
      body: jsonEncode({'keyword': keyword}),
    );
    if (res.statusCode != 201) throw Exception('Failed to add keyword: ${res.body}');
  }

  Future<void> deleteKeyword(String keyword) async {
    final res = await http.delete(
      Uri.parse('$_baseUrl/profile/keywords/$keyword'),
      headers: _headers(),
    );
    if (res.statusCode != 200) throw Exception('Failed to delete keyword: ${res.body}');
  }

  Future<Map<String, dynamic>> getAvailableSources() async {
    final res = await http.get(Uri.parse('$_baseUrl/profile/sources'), headers: _headers());
    if (res.statusCode != 200) throw Exception('Failed to get sources: ${res.body}');
    return jsonDecode(res.body);
  }

}

// ================= JOB MODEL =================

class Job {
  final int id;
  final String title;
  final String? company;
  final String? location;
  final String description;
  final String url;
  final bool isNew;                 // added
  final String? applicationType;    // added
  final String? contactEmail;       // added

  Job({
    required this.id,
    required this.title,
    this.company,
    this.location,
    required this.description,
    required this.url,
    required this.isNew,
    this.applicationType,
    this.contactEmail,
  });

  factory Job.fromJson(Map<String, dynamic> json) {
    return Job(
      id: json['id'],
      title: json['title'],
      company: json['company'],
      location: json['location'],
      description: json['description'],
      url: json['url'],
      isNew: json['is_new'] ?? false,
      applicationType: json['application_type'],
      contactEmail: json['contact_email'],
    );
  }
}
