import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import '../model/scan_model.dart';
import 'auth_service.dart';

class OcrExtractionResult {
  final String rawText;
  final List<String> ingredients;
  final String? fssaiNumber;
  final String? productName;
  final double confidence;
  final String provider;
  final String? error;

  OcrExtractionResult({
    required this.rawText,
    required this.ingredients,
    this.fssaiNumber,
    this.productName,
    required this.confidence,
    required this.provider,
    this.error,
  });
}

class IngredientScannerService {
  static final IngredientScannerService _instance = IngredientScannerService._internal();
  factory IngredientScannerService() => _instance;
  IngredientScannerService._internal();

  static const String baseUrl = "http://127.0.0.1:5000";
  final AuthService _auth = AuthService();

  Map<String, String> _headers() {
    final map = <String, String>{
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
    if (_auth.token != null) {
      map["Authorization"] = "Bearer ${_auth.token}";
    }
    return map;
  }

  /// Step 1: Perform Enhanced OCR extraction on uploaded food image
  Future<OcrExtractionResult> extractIngredients(
    File imageFile, {
    String provider = "gemini",
  }) async {
    try {
      final uri = Uri.parse("$baseUrl/api/extract");
      final request = http.MultipartRequest("POST", uri)
        ..fields["provider"] = provider
        ..files.add(await http.MultipartFile.fromPath("image", imageFile.path));

      if (_auth.token != null) {
        request.headers["Authorization"] = "Bearer ${_auth.token}";
      }

      final streamed = await request.send();
      final res = await http.Response.fromStream(streamed);

      if (res.statusCode != 200) {
        try {
          final errBody = jsonDecode(res.body);
          return OcrExtractionResult(
            rawText: "",
            ingredients: [],
            confidence: 0,
            provider: provider,
            error: errBody["error"] ?? "Extraction failed (Status ${res.statusCode})",
          );
        } catch (_) {
          return OcrExtractionResult(
            rawText: "",
            ingredients: [],
            confidence: 0,
            provider: provider,
            error: "Extraction server error: ${res.statusCode}",
          );
        }
      }

      final data = jsonDecode(res.body);
      return OcrExtractionResult(
        rawText: data["raw_text"] ?? "",
        ingredients: List<String>.from(data["ingredients"] ?? []),
        fssaiNumber: data["fssai_number"],
        productName: data["product_name"],
        confidence: (data["confidence"] as num?)?.toDouble() ?? 0.8,
        provider: data["provider"] ?? provider,
      );
    } catch (e) {
      return OcrExtractionResult(
        rawText: "",
        ingredients: [],
        confidence: 0,
        provider: provider,
        error: "Connection to OCR engine failed: $e",
      );
    }
  }

  /// Step 2: Deterministic classification against FSSAI database
  Future<ProductAnalysis?> analyze({
    required String productName,
    required List<String> ingredients,
    String? fssaiNumber,
    String? category,
  }) async {
    try {
      final uri = Uri.parse("$baseUrl/api/analyze");
      final res = await http.post(
        uri,
        headers: _headers(),
        body: jsonEncode({
          "product_name": productName,
          "ingredients": ingredients,
          "fssai_number": fssaiNumber,
          "category": category,
        }),
      );

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return ProductAnalysis.fromJson(data);
      } else {
        debugPrint("Analysis error: ${res.body}");
        return null;
      }
    } catch (e) {
      debugPrint("Analysis exception: $e");
      return null;
    }
  }

  /// One-step Scan & Analyze
  Future<ProductAnalysis?> scanAndAnalyze(
    XFile imageFile, {
    String? productHint,
    String? category,
    String provider = "gemini",
  }) async {
    try {
      final uri = Uri.parse("$baseUrl/api/scan-and-analyze");
      final request = http.MultipartRequest("POST", uri);

      // On web, XFile.path is a blob URL — must use bytes instead
      if (kIsWeb) {
        final bytes = await imageFile.readAsBytes();
        request.files.add(http.MultipartFile.fromBytes(
          "image",
          bytes,
          filename: imageFile.name,
        ));
      } else {
        request.files.add(await http.MultipartFile.fromPath(
          "image",
          imageFile.path,
        ));
      }

      request.fields["provider"] = provider;
      if (productHint != null && productHint.isNotEmpty) {
        request.fields["product_name"] = productHint;
      }
      if (category != null && category.isNotEmpty) {
        request.fields["category"] = category;
      }
      if (_auth.token != null) {
        request.headers["Authorization"] = "Bearer ${_auth.token}";
      }

      final streamed = await request.send();
      final res = await http.Response.fromStream(streamed);

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return ProductAnalysis.fromJson(data);
      }
      return null;
    } catch (e) {
      debugPrint("Scan and analyze error: $e");
      return null;
    }
  }

  /// Fetch user's scan history
  Future<List<ScanHistoryItem>> getScanHistory() async {
    if (_auth.token == null) return [];
    try {
      final uri = Uri.parse("$baseUrl/api/history");
      final res = await http.get(uri, headers: _headers());
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final list = (data["history"] as List? ?? [])
            .map((item) => ScanHistoryItem.fromJson(item))
            .toList();
        return list;
      }
      return [];
    } catch (e) {
      debugPrint("Get history error: $e");
      return [];
    }
  }

  /// Toggle bookmark for a scan
  Future<bool?> toggleFavorite(int scanId) async {
    if (_auth.token == null) return null;
    try {
      final uri = Uri.parse("$baseUrl/api/favorites/$scanId");
      final res = await http.post(uri, headers: _headers());
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return data["is_favorite"] as bool?;
      }
      return null;
    } catch (e) {
      debugPrint("Toggle favorite error: $e");
      return null;
    }
  }

  /// Fetch categories list
  Future<List<Map<String, dynamic>>> getCategories() async {
    try {
      final uri = Uri.parse("$baseUrl/api/categories");
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return List<Map<String, dynamic>>.from(data["categories"] ?? []);
      }
      return [];
    } catch (e) {
      debugPrint("Get categories error: $e");
      return [];
    }
  }

  /// Validate a product against Open Food Facts database
  Future<Map<String, dynamic>?> validateWithOFF({
    required String productName,
    String? barcode,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/off/lookup');
      final body = <String, dynamic>{'product_name': productName};
      if (barcode != null && barcode.isNotEmpty) body['barcode'] = barcode;
      final res = await http.post(
        uri,
        headers: _headers(),
        body: jsonEncode(body),
      );
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      return null;
    } catch (e) {
      debugPrint('validateWithOFF error: $e');
      return null;
    }
  }

  /// Get category risk profiles for unbranded product fallback
  Future<List<Map<String, dynamic>>> getCategoryRiskProfiles() async {
    try {
      final uri = Uri.parse('$baseUrl/api/categories/risk-profiles');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        return List<Map<String, dynamic>>.from(data['profiles'] ?? []);
      }
      return [];
    } catch (e) {
      debugPrint('getCategoryRiskProfiles error: $e');
      return [];
    }
  }

  /// Gemini AI ingredient safety and nutritional analysis.
  ///
  /// Calls POST /api/analyze-product with the ingredient list and optional
  /// nutrition label data. Returns null on error so callers can gracefully
  /// fall back to the FSSAI-based analysis already in [ProductAnalysis].
  Future<GeminiProductAnalysis?> analyzeProduct({
    required List<String> ingredients,
    Map<String, dynamic>? nutritionData,
    String? productName,
  }) async {
    if (ingredients.isEmpty) return null;
    try {
      final uri = Uri.parse('$baseUrl/api/analyze-product');
      final body = <String, dynamic>{
        'ingredients': ingredients,
        'nutrition_data': nutritionData,
      };
      if (productName != null && productName.isNotEmpty) {
        body['product_name'] = productName;
      }
      final res = await http.post(
        uri,
        headers: _headers(),
        body: jsonEncode(body),
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        return GeminiProductAnalysis.fromJson(data);
      }
      debugPrint('analyzeProduct HTTP error: ${res.statusCode} ${res.body}');
      return null;
    } catch (e) {
      debugPrint('analyzeProduct exception: $e');
      return null;
    }
  }

  /// Generate intelligent, Gemini AI-powered healthier food alternatives and swaps.
  ///
  /// Calls POST /api/ai-alternatives with product details, original ingredients,
  /// current health score, and flagged additives.
  Future<AiAlternativesResult?> getAiAlternatives({
    required String productName,
    String? category,
    List<String>? ingredients,
    int? currentScore,
    List<String>? flaggedIngredients,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/ai-alternatives');
      final body = <String, dynamic>{
        'product_name': productName,
        if (category != null && category.isNotEmpty) 'category': category,
        if (ingredients != null && ingredients.isNotEmpty) 'ingredients': ingredients,
        if (currentScore != null) 'current_score': currentScore,
        if (flaggedIngredients != null && flaggedIngredients.isNotEmpty)
          'flagged_ingredients': flaggedIngredients,
      };

      final res = await http.post(
        uri,
        headers: _headers(),
        body: jsonEncode(body),
      );

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        return AiAlternativesResult.fromJson(data);
      }
      debugPrint('getAiAlternatives HTTP error: ${res.statusCode} ${res.body}');
      return null;
    } catch (e) {
      debugPrint('getAiAlternatives exception: $e');
      return null;
    }
  }
}