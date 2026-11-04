/// Models for Willow Food Safety Scanner — includes Open Food Facts enrichment fields.
library scan_model;

// ─────────────────────────────────────────────────────────────────────────────
// Gemini AI Analysis Models
// ─────────────────────────────────────────────────────────────────────────────

/// A single ingredient flagged by Gemini with its risk assessment.
class GeminiHarmfulIngredient {
  final String name;
  final String category;
  final String riskLevel; // 'Low', 'Moderate', 'High'
  final List<String> potentialConcerns;
  final String explanation;
  final bool doseDependency;
  final String precautions;

  GeminiHarmfulIngredient({
    required this.name,
    required this.category,
    required this.riskLevel,
    required this.potentialConcerns,
    required this.explanation,
    required this.doseDependency,
    required this.precautions,
  });

  factory GeminiHarmfulIngredient.fromJson(Map<String, dynamic> json) {
    return GeminiHarmfulIngredient(
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      riskLevel: json['risk_level'] as String? ?? 'Low',
      potentialConcerns: List<String>.from(json['potential_concerns'] as List? ?? []),
      explanation: json['explanation'] as String? ?? '',
      doseDependency: json['dose_dependency'] == true,
      precautions: json['precautions'] as String? ?? '',
    );
  }
}

/// Macronutrient data returned by Gemini (values are null when no label available).
class GeminiMacronutrients {
  final double? caloriesKcal;
  final double? carbohydratesG;
  final double? proteinG;
  final double? totalFatG;
  final double? saturatedFatG;
  final double? transFatG;
  final double? dietaryFibreG;
  final double? totalSugarG;
  final double? addedSugarG;
  final String dataSource; // 'nutrition_label' | 'not_available'

  GeminiMacronutrients({
    this.caloriesKcal,
    this.carbohydratesG,
    this.proteinG,
    this.totalFatG,
    this.saturatedFatG,
    this.transFatG,
    this.dietaryFibreG,
    this.totalSugarG,
    this.addedSugarG,
    required this.dataSource,
  });

  bool get hasData => caloriesKcal != null || totalFatG != null || proteinG != null;

  factory GeminiMacronutrients.fromJson(Map<String, dynamic> json) {
    double? parse(dynamic v) => v == null ? null : double.tryParse(v.toString());
    return GeminiMacronutrients(
      caloriesKcal: parse(json['calories_kcal']),
      carbohydratesG: parse(json['carbohydrates_g']),
      proteinG: parse(json['protein_g']),
      totalFatG: parse(json['total_fat_g']),
      saturatedFatG: parse(json['saturated_fat_g']),
      transFatG: parse(json['trans_fat_g']),
      dietaryFibreG: parse(json['dietary_fibre_g']),
      totalSugarG: parse(json['total_sugar_g']),
      addedSugarG: parse(json['added_sugar_g']),
      dataSource: json['data_source'] as String? ?? 'not_available',
    );
  }
}

/// Holistic nutritional assessment from Gemini.
class GeminiNutritionalAssessment {
  final String overallRating; // 'Good', 'Moderate', 'Poor', 'Unrated'
  final String proteinAssessment;
  final String sugarAssessment;
  final String fatAssessment;
  final String overallSummary;

  GeminiNutritionalAssessment({
    required this.overallRating,
    required this.proteinAssessment,
    required this.sugarAssessment,
    required this.fatAssessment,
    required this.overallSummary,
  });

  factory GeminiNutritionalAssessment.fromJson(Map<String, dynamic> json) {
    return GeminiNutritionalAssessment(
      overallRating: json['overall_rating'] as String? ?? 'Unrated',
      proteinAssessment: json['protein_assessment'] as String? ?? '',
      sugarAssessment: json['sugar_assessment'] as String? ?? '',
      fatAssessment: json['fat_assessment'] as String? ?? '',
      overallSummary: json['overall_summary'] as String? ?? '',
    );
  }
}

/// Full Gemini AI product analysis wrapping all sub-models.
class GeminiProductAnalysis {
  final String status; // 'success' | 'fallback'
  final List<GeminiHarmfulIngredient> harmfulIngredients;
  final GeminiMacronutrients macronutrients;
  final GeminiNutritionalAssessment nutritionalAssessment;
  final String ingredientSummary;
  final String healthRecommendation;

  GeminiProductAnalysis({
    required this.status,
    required this.harmfulIngredients,
    required this.macronutrients,
    required this.nutritionalAssessment,
    required this.ingredientSummary,
    required this.healthRecommendation,
  });

  bool get isAiPowered => status == 'success';

  factory GeminiProductAnalysis.fromJson(Map<String, dynamic> json) {
    final pa = json['product_analysis'] as Map<String, dynamic>? ?? {};
    final hiList = (pa['harmful_ingredients'] as List? ?? [])
        .map((e) => GeminiHarmfulIngredient.fromJson(e as Map<String, dynamic>))
        .toList();
    final macroJson = pa['macronutrients'] as Map<String, dynamic>? ?? {};
    final assessJson = pa['nutritional_assessment'] as Map<String, dynamic>? ?? {};

    return GeminiProductAnalysis(
      status: json['status'] as String? ?? 'fallback',
      harmfulIngredients: hiList,
      macronutrients: GeminiMacronutrients.fromJson(macroJson),
      nutritionalAssessment: GeminiNutritionalAssessment.fromJson(assessJson),
      ingredientSummary: pa['ingredient_summary'] as String? ?? '',
      healthRecommendation: pa['health_recommendation'] as String? ?? '',
    );
  }
}

class FlaggedIngredient {
  final String canonical;
  final String riskLevel; // 'high' or 'watch'
  final String healthEffects;
  final String? fssaiRef;
  final String rawToken;

  FlaggedIngredient({
    required this.canonical,
    required this.riskLevel,
    required this.healthEffects,
    this.fssaiRef,
    required this.rawToken,
  });

  factory FlaggedIngredient.fromJson(Map<String, dynamic> json) {
    return FlaggedIngredient(
      canonical: json['canonical'] ?? '',
      riskLevel: json['risk_level'] ?? 'watch',
      healthEffects: json['health_effects'] ?? '',
      fssaiRef: json['fssai_ref'],
      rawToken: json['raw_token'] ?? json['canonical'] ?? '',
    );
  }
}

class CleanIngredient {
  final String canonical;
  final String healthEffects;
  final String rawToken;

  CleanIngredient({
    required this.canonical,
    required this.healthEffects,
    required this.rawToken,
  });

  factory CleanIngredient.fromJson(Map<String, dynamic> json) {
    return CleanIngredient(
      canonical: json['canonical'] ?? '',
      healthEffects: json['health_effects'] ?? '',
      rawToken: json['raw_token'] ?? json['canonical'] ?? '',
    );
  }
}

class AlternativeSwap {
  final String name;
  final int score;
  final String price;
  final String? note;

  // Rich Gemini AI-powered fields
  final String? brand;
  final String? whyHealthier;
  final List<String> avoidedIngredients;
  final List<String> keyBenefits;
  final String? swapType; // 'Packaged Brand', 'Whole Food Alternative', 'Clean Label'

  AlternativeSwap({
    required this.name,
    required this.score,
    required this.price,
    this.note,
    this.brand,
    this.whyHealthier,
    this.avoidedIngredients = const [],
    this.keyBenefits = const [],
    this.swapType,
  });

  factory AlternativeSwap.fromJson(Map<String, dynamic> json) {
    return AlternativeSwap(
      name: json['name'] ?? '',
      score: json['score'] is int ? json['score'] : int.tryParse(json['score'].toString()) ?? 75,
      price: json['price'] ?? '',
      note: json['note'],
      brand: json['brand'],
      whyHealthier: json['why_healthier'] ?? json['note'],
      avoidedIngredients: List<String>.from(json['avoided_ingredients'] ?? []),
      keyBenefits: List<String>.from(json['key_benefits'] ?? []),
      swapType: json['swap_type'],
    );
  }
}

class AiAlternativesResult {
  final String status;
  final String productName;
  final String category;
  final int? currentScore;
  final String summary;
  final List<AlternativeSwap> alternatives;
  final List<String> groceryTips;

  AiAlternativesResult({
    required this.status,
    required this.productName,
    required this.category,
    this.currentScore,
    required this.summary,
    required this.alternatives,
    required this.groceryTips,
  });

  bool get isAiPowered => status == 'success';

  factory AiAlternativesResult.fromJson(Map<String, dynamic> json) {
    final rawAlts = json['alternatives'] as List? ?? [];
    return AiAlternativesResult(
      status: json['status'] as String? ?? 'fallback',
      productName: json['product_name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      currentScore: json['current_score'] is int
          ? json['current_score']
          : int.tryParse(json['current_score']?.toString() ?? ''),
      summary: json['summary'] as String? ?? '',
      alternatives: rawAlts
          .map((a) => AlternativeSwap.fromJson(a as Map<String, dynamic>))
          .toList(),
      groceryTips: List<String>.from(json['grocery_tips'] as List? ?? []),
    );
  }
}

/// Nutriment data from Open Food Facts (per 100g)
class OffNutrients {
  final double? energyKcal;
  final double? fatG;
  final double? saturatedFatG;
  final double? carbohydratesG;
  final double? sugarsG;
  final double? fiberG;
  final double? proteinsG;
  final double? saltG;

  OffNutrients({
    this.energyKcal,
    this.fatG,
    this.saturatedFatG,
    this.carbohydratesG,
    this.sugarsG,
    this.fiberG,
    this.proteinsG,
    this.saltG,
  });

  factory OffNutrients.fromJson(Map<String, dynamic> json) {
    double? parseDouble(dynamic v) {
      if (v == null) return null;
      return double.tryParse(v.toString());
    }

    return OffNutrients(
      energyKcal: parseDouble(json['energy_kcal']),
      fatG: parseDouble(json['fat_g']),
      saturatedFatG: parseDouble(json['saturated_fat_g']),
      carbohydratesG: parseDouble(json['carbohydrates_g']),
      sugarsG: parseDouble(json['sugars_g']),
      fiberG: parseDouble(json['fiber_g']),
      proteinsG: parseDouble(json['proteins_g']),
      saltG: parseDouble(json['salt_g']),
    );
  }
}

/// Open Food Facts enrichment data attached to a ProductAnalysis
class OffData {
  final String? offProductName;
  final String? offBrands;
  final String? offImageUrl;
  final String? nutriscoreGrade; // 'a' to 'e'
  final int? nutriscoreScore;    // 10-90
  final int? novaGroup;          // 1-4
  final List<String> additives;
  final String? aiInsight;
  final String? healthBenefit;
  final String? bestTimeToEat;
  final OffNutrients? nutrients;
  final String? ingredientsText;

  OffData({
    this.offProductName,
    this.offBrands,
    this.offImageUrl,
    this.nutriscoreGrade,
    this.nutriscoreScore,
    this.novaGroup,
    required this.additives,
    this.aiInsight,
    this.healthBenefit,
    this.bestTimeToEat,
    this.nutrients,
    this.ingredientsText,
  });

  factory OffData.fromJson(Map<String, dynamic> json) {
    final tags = json['health_tags'] as Map<String, dynamic>? ?? {};
    final nutrJson = json['nutrients'] as Map<String, dynamic>?;

    return OffData(
      offProductName: json['off_product_name'],
      offBrands: json['off_brands'],
      offImageUrl: json['off_image_url'],
      nutriscoreGrade: json['nutriscore_grade'],
      nutriscoreScore: json['nutriscore_score'] is int ? json['nutriscore_score'] : null,
      novaGroup: json['nova_group'] is int ? json['nova_group'] : null,
      additives: List<String>.from(json['additives'] ?? []),
      aiInsight: json['ai_insight'],
      healthBenefit: tags['health_benefit'],
      bestTimeToEat: tags['best_time_to_eat'],
      nutrients: nutrJson != null ? OffNutrients.fromJson(nutrJson) : null,
      ingredientsText: json['ingredients_text'],
    );
  }
}

class ProductAnalysis {
  final String productName;
  final String category;
  final int riskScore;
  final String scoreLabel;
  final int confidence;
  final bool isFallback;
  final String? fallbackNote;
  final String? fssaiNumber;
  final List<FlaggedIngredient> flagged;
  final List<CleanIngredient> clean;
  final List<String> unknown;
  final List<AlternativeSwap> alternatives;
  final int? scanId;
  final bool isFavorite;

  // Open Food Facts enrichment
  final OffData? offData;
  final int? blendedScore;

  ProductAnalysis({
    required this.productName,
    required this.category,
    required this.riskScore,
    required this.scoreLabel,
    required this.confidence,
    required this.isFallback,
    this.fallbackNote,
    this.fssaiNumber,
    required this.flagged,
    required this.clean,
    required this.unknown,
    required this.alternatives,
    this.scanId,
    this.isFavorite = false,
    this.offData,
    this.blendedScore,
  });

  /// The best available health score (blended if OFF data present, else local)
  int get displayScore => blendedScore ?? riskScore;

  factory ProductAnalysis.fromJson(Map<String, dynamic> json) {
    final flaggedList = (json['flagged'] as List? ?? [])
        .map((f) => FlaggedIngredient.fromJson(f as Map<String, dynamic>))
        .toList();

    final cleanList = (json['clean'] as List? ?? [])
        .map((c) => CleanIngredient.fromJson(c as Map<String, dynamic>))
        .toList();

    final altList = (json['alternatives'] as List? ?? [])
        .map((a) => AlternativeSwap.fromJson(a as Map<String, dynamic>))
        .toList();

    final unknownList = (json['unknown'] as List? ?? [])
        .map((u) => u.toString())
        .toList();

    final offJson = json['off_data'] as Map<String, dynamic>?;

    return ProductAnalysis(
      productName: json['product_name'] ?? 'Packaged Food',
      category: json['category'] ?? 'Namkeen / Fried Snacks',
      riskScore: json['risk_score'] is int ? json['risk_score'] : int.tryParse(json['risk_score'].toString()) ?? 50,
      scoreLabel: json['score_label'] ?? 'Moderate',
      confidence: json['confidence'] is int ? json['confidence'] : int.tryParse(json['confidence'].toString()) ?? 50,
      isFallback: json['is_fallback'] == true || json['is_fallback'] == 1,
      fallbackNote: json['fallback_note'],
      fssaiNumber: json['fssai_number'],
      flagged: flaggedList,
      clean: cleanList,
      unknown: unknownList,
      alternatives: altList,
      scanId: json['scan_id'] is int ? json['scan_id'] : int.tryParse(json['scan_id']?.toString() ?? ''),
      isFavorite: json['is_favorite'] == true || json['is_favorite'] == 1,
      offData: offJson != null ? OffData.fromJson(offJson) : null,
      blendedScore: json['blended_score'] is int ? json['blended_score'] : null,
    );
  }
}

class ScanHistoryItem {
  final int id;
  final String productName;
  final String category;
  final int riskScore;
  final int confidence;
  final int flaggedCount;
  final String? fssaiNumber;
  final bool isFavorite;
  final String createdAt;
  final bool isFallback;
  final String? fallbackNote;
  final List<FlaggedIngredient> flagged;
  final List<CleanIngredient> clean;
  final List<String> unknown;

  ScanHistoryItem({
    required this.id,
    required this.productName,
    required this.category,
    required this.riskScore,
    required this.confidence,
    required this.flaggedCount,
    this.fssaiNumber,
    required this.isFavorite,
    required this.createdAt,
    this.isFallback = false,
    this.fallbackNote,
    this.flagged = const [],
    this.clean = const [],
    this.unknown = const [],
  });

  String get timeAgo {
    if (createdAt.isEmpty) return 'Recent';
    try {
      final dt = DateTime.parse(createdAt);
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 60) {
        return '${diff.inMinutes <= 0 ? 1 : diff.inMinutes}m ago';
      }
      if (diff.inHours < 24) {
        return '${diff.inHours}h ago';
      }
      if (diff.inDays == 1) return 'Yesterday';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return createdAt;
    }
  }

  factory ScanHistoryItem.fromJson(Map<String, dynamic> json) {
    final rawFlagged = json['flagged'] as List? ?? [];
    final flaggedList = rawFlagged
        .map((f) => f is Map<String, dynamic>
            ? FlaggedIngredient.fromJson(f)
            : FlaggedIngredient(
                canonical: f.toString(),
                riskLevel: 'watch',
                healthEffects: '',
                rawToken: f.toString(),
              ))
        .toList();

    final rawClean = json['clean'] as List? ?? [];
    final cleanList = rawClean
        .map((c) => c is Map<String, dynamic>
            ? CleanIngredient.fromJson(c)
            : CleanIngredient(
                canonical: c.toString(),
                healthEffects: '',
                rawToken: c.toString(),
              ))
        .toList();

    final rawUnknown = json['unknown'] as List? ?? [];
    final unknownList = rawUnknown.map((u) => u.toString()).toList();

    return ScanHistoryItem(
      id: json['id'] is int ? json['id'] : int.tryParse(json['id'].toString()) ?? 0,
      productName: json['product_name'] ?? 'Product',
      category: json['category'] ?? 'General Food',
      riskScore: json['risk_score'] is int ? json['risk_score'] : 50,
      confidence: json['confidence'] is int ? json['confidence'] : 50,
      flaggedCount: json['flagged_count'] is int ? json['flagged_count'] : flaggedList.length,
      fssaiNumber: json['fssai_number'],
      isFavorite: json['is_favorite'] == true || json['is_favorite'] == 1,
      createdAt: json['created_at'] ?? '',
      isFallback: json['is_fallback'] == true || json['is_fallback'] == 1,
      fallbackNote: json['fallback_note'],
      flagged: flaggedList,
      clean: cleanList,
      unknown: unknownList,
    );
  }
}
