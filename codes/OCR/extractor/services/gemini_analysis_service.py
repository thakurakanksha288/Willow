"""
Gemini Analysis Service:
Provides AI-powered ingredient safety and nutritional analysis using the official Google GenAI SDK.
Analyzes extracted food ingredient lists for:
1. Harmful and potentially harmful ingredients with dosage-dependent risk assessment
2. Macronutrient verification (strictly requiring nutrition label data; null if unavailable)
3. Qualitative nutritional assessments (protein balance, sugar, fat composition)
4. Scientific, evidence-based ingredient explanations and consumer guidance
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure extractor base directory is on sys.path
_EXTRACTOR_DIR = Path(__file__).resolve().parent.parent
if str(_EXTRACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EXTRACTOR_DIR))

from pydantic import BaseModel, Field, ValidationError

from config.settings import settings, logger
from database import get_db_connection


# ==============================================================================
# Pydantic Schemas for Structured JSON Output
# ==============================================================================

class FlaggedIngredient(BaseModel):
    name: str = Field(description="Ingredient name as identified from the input list")
    category: str = Field(description="Risk category, e.g. Preservative, Artificial Sweetener, Synthetic Colour, Excessive Sodium Source, Emulsifier, Trans Fat Source")
    risk_level: str = Field(description="Risk level: 'Low', 'Moderate', or 'High'")
    potential_concerns: List[str] = Field(default_factory=list, description="Specific potential health concerns identified")
    explanation: str = Field(description="Scientific explanation of why it may be concerning based on clinical/regulatory evidence")
    dose_dependency: bool = Field(description="True if the health concern depends on dosage or frequency of consumption, False otherwise")
    precautions: str = Field(description="Recommended actionable precautions for the consumer")


class Macronutrients(BaseModel):
    calories_kcal: Optional[float] = Field(None, description="Calories in kcal. MUST be null if no nutrition label is provided.")
    carbohydrates_g: Optional[float] = Field(None, description="Total carbohydrates in grams. MUST be null if no nutrition label is provided.")
    protein_g: Optional[float] = Field(None, description="Protein in grams. MUST be null if no nutrition label is provided.")
    total_fat_g: Optional[float] = Field(None, description="Total fat in grams. MUST be null if no nutrition label is provided.")
    saturated_fat_g: Optional[float] = Field(None, description="Saturated fat in grams. MUST be null if no nutrition label is provided.")
    trans_fat_g: Optional[float] = Field(None, description="Trans fat in grams. MUST be null if no nutrition label is provided.")
    dietary_fibre_g: Optional[float] = Field(None, description="Dietary fibre in grams. MUST be null if no nutrition label is provided.")
    total_sugar_g: Optional[float] = Field(None, description="Total sugar in grams. MUST be null if no nutrition label is provided.")
    added_sugar_g: Optional[float] = Field(None, description="Added sugar in grams. MUST be null if no nutrition label is provided.")
    data_source: str = Field(description="'nutrition_label' if numerical values are based on supplied nutrition label, or 'not_available' if none supplied")


class NutritionalAssessment(BaseModel):
    overall_rating: str = Field(description="Overall nutritional quality: e.g. 'Good', 'Moderate', 'Poor', or 'Unrated'")
    protein_assessment: str = Field(description="Protein quality and protein-to-carbohydrate balance evaluation")
    sugar_assessment: str = Field(description="Sugar content, type of sweeteners, and glycemic impact assessment")
    fat_assessment: str = Field(description="Fat composition assessment (saturated vs unsaturated fat quality, oil types)")
    overall_summary: str = Field(description="Holistic summary of the product's nutritional profile and dietary suitability")


class HealthyAlternative(BaseModel):
    name: str = Field(description="Name of the healthier alternative product or food item (e.g. 'Whole Grain Ragi Cookies', 'Roasted Makhana')")
    brand: Optional[str] = Field(None, description="Clean-label brand name if packaged (e.g. 'Slurrp Farm', 'The Whole Truth') or 'Whole Food Swap'")
    score: int = Field(description="Estimated health score (70-98)")
    price: str = Field(description="Indicative price or price comparison (e.g. '₹45 (Similar)', 'Budget-friendly')")
    why_healthier: str = Field(description="Clear explanation of why this swap is healthier than the original product")
    avoided_ingredients: List[str] = Field(default_factory=list, description="Harmful ingredients from the original product avoided by this swap")
    key_benefits: List[str] = Field(default_factory=list, description="Nutritional highlights (e.g. ['High fiber', 'Zero trans fat', 'Naturally sweetened'])")
    swap_type: str = Field(default="Packaged Brand", description="'Packaged Brand', 'Whole Food Alternative', or 'Clean Label'")


class AlternativesResponse(BaseModel):
    status: str = Field(default="success", description="Status code: 'success' or 'fallback'")
    product_name: str = Field(description="Original product name")
    category: str = Field(description="Product category")
    current_score: Optional[int] = Field(None, description="Original product health score")
    summary: str = Field(description="Concise summary explaining why switching to healthier options improves nutrition for this category")
    alternatives: List[HealthyAlternative] = Field(description="List of 3-5 healthier alternative recommendations")
    grocery_tips: List[str] = Field(default_factory=list, description="Practical label-reading shopping tips for this food category")


class ProductAnalysis(BaseModel):
    harmful_ingredients: List[FlaggedIngredient] = Field(
        default_factory=list,
        description="List of ingredients flagged with potential health concerns"
    )
    macronutrients: Macronutrients = Field(
        description="Macronutrient information (strictly null for numerical values if no nutrition label was provided)"
    )
    nutritional_assessment: NutritionalAssessment = Field(
        description="Qualitative nutritional and dietary balance assessment"
    )
    ingredient_summary: str = Field(
        description="Concise synthesis of the overall ingredient formulation"
    )
    health_recommendation: str = Field(
        description="Consumer guidance on consumption frequency, portion control, or specific demographic cautions"
    )
    healthy_alternatives: Optional[List[HealthyAlternative]] = Field(
        default_factory=list,
        description="Curated healthier food alternatives and swaps"
    )


class AnalyzeProductResponse(BaseModel):
    status: str = Field(default="success", description="Status code: 'success' or 'fallback'")
    product_analysis: ProductAnalysis


# ==============================================================================
# Prompt Construction
# ==============================================================================

ANALYSIS_SYSTEM_INSTRUCTION = """You are an expert food safety scientist, regulatory toxicologist, and clinical nutritionist analyzing packaged food products.
You evaluate extracted ingredient lists objectively using published peer-reviewed science and standards from FSSAI, FDA, EFSA, and WHO.

Follow these strict rules:
1. HARMFUL INGREDIENT ANALYSIS:
   - Analyze EVERY ingredient in the provided list.
   - Flag ingredients with credible, documented health concerns (e.g. artificial sweeteners like aspartame/acesulfame-K, controversial preservatives like BHA/BHT/TBHQ/sodium benzoate with ascorbic acid, synthetic azo dyes like Tartrazine/Sunset Yellow, excessive sodium sources, partially hydrogenated oils/trans fats, palm oil high in palmitic acid).
   - DO NOT automatically classify every artificial, synthetic, or processed additive as harmful. Emulsifiers like soy lecithin or natural stabilizers (guar gum, pectin) in standard doses should not be marked as high risk.
   - Distinguish established clinical risks from speculative or context-dependent concerns.
   - Do NOT make unsupported medical claims or diagnose health conditions.
   - Clearly distinguish between an ingredient being hazardous at massive laboratory doses versus the actual risk at normal, regulated food exposure levels.
   - State whether the concern is dose/frequency dependent (`dose_dependency`: true/false).
   - Assign risk levels objectively:
     * 'High': Proven hazardous at common dietary exposure (e.g. industrial trans fats, banned additives, high cumulative toxic potential).
     * 'Moderate': Significant concern for sensitive populations, high habitual consumers, or additives under active regulatory review.
     * 'Low': Common food additives with minor sensitivity risks or concerns primarily at excessive consumption.

2. MACRONUTRIENT RULES (CRUCIAL):
   - Ingredient lists ALONE cannot establish exact macronutrient quantities.
   - If nutrition data is provided in the input, extract and verify the numerical values into `macronutrients` and set `data_source` to 'nutrition_label'.
   - If NO nutrition data is provided (nutrition_data is null or empty):
     YOU MUST SET all numerical values (calories_kcal, carbohydrates_g, protein_g, total_fat_g, saturated_fat_g, trans_fat_g, dietary_fibre_g, total_sugar_g, added_sugar_g) TO null.
     DO NOT GUESS OR ESTIMATE NUMERICAL MACRONUTRIENTS. Set `data_source` to 'not_available'.
   - Even without numerical macronutrients, provide a qualitative `nutritional_assessment` based on the ingredient hierarchy (e.g., whether refined sugars, flours, or oils dominate the first ingredients, presence of whole grains, nuts, or legumes).
"""


def _build_analysis_prompt(
    ingredients: List[str],
    nutrition_data: Optional[Dict[str, Any]] = None,
    product_name: Optional[str] = None,
) -> str:
    """Builds a comprehensive user prompt for Gemini."""
    prompt_lines = [
        f"Product Name: {product_name or 'Packaged Food Product'}",
        f"Extracted Ingredients ({len(ingredients)} items):",
        json.dumps(ingredients, indent=2),
    ]

    if nutrition_data and isinstance(nutrition_data, dict) and any(nutrition_data.values()):
        prompt_lines.append("\nSupplied Nutrition Label Data:")
        prompt_lines.append(json.dumps(nutrition_data, indent=2))
        prompt_lines.append(
            "\nNote: Valid numerical values from the supplied nutrition label data can be populated into the macronutrients fields."
        )
    else:
        prompt_lines.append("\nSupplied Nutrition Label Data: NONE (Not Available).")
        prompt_lines.append(
            "\nCRITICAL RULE: Since NO nutrition label data is supplied, set ALL numerical macronutrient values (calories_kcal, carbohydrates_g, protein_g, total_fat_g, saturated_fat_g, trans_fat_g, dietary_fibre_g, total_sugar_g, added_sugar_g) to null. Set data_source to 'not_available'."
        )

    prompt_lines.append(
        "\nProvide your complete analysis strictly matching the requested JSON schema."
    )
    return "\n".join(prompt_lines)


# ==============================================================================
# Fallback Analysis Generation (Deterministic Local Database)
# ==============================================================================

def _generate_fallback_analysis(
    ingredients: List[str],
    nutrition_data: Optional[Dict[str, Any]] = None,
    product_name: Optional[str] = None,
    fallback_reason: str = "Gemini API unavailable; using curated local safety database.",
) -> Dict[str, Any]:
    """
    Generates a deterministic fallback analysis using the local SQLite database
    and FSSAI-aligned ingredient catalog if Gemini API is unreachable or not configured.
    """
    logger.info("Generating local deterministic fallback analysis...")
    flagged_list: List[Dict[str, Any]] = []

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all known flagged ingredients and aliases
        cursor.execute("""
            SELECT i.canonical_name, i.category_name, i.risk_level, i.health_effects, i.fssai_ref, a.alias
            FROM ingredients i
            LEFT JOIN aliases a ON i.id = a.ingredient_id
        """)
        rows = cursor.fetchall()

        lookup: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            risk_raw = str(r["risk_level"] or "").lower()
            risk_level_val = "High" if risk_raw == "high" else ("Moderate" if risk_raw == "watch" else "Low")
            info = {
                "name": r["canonical_name"],
                "category": r["category_name"] or "Food Additive",
                "risk_level": risk_level_val,
                "health_effects": r["health_effects"] or "May cause sensitivity or adverse effects in high amounts.",
                "fssai_ref": r["fssai_ref"] or "",
            }
            lookup[r["canonical_name"].lower().strip()] = info
            if r["alias"]:
                lookup[r["alias"].lower().strip()] = info

        seen = set()
        for ing in ingredients:
            ing_lower = ing.lower().strip()
            matched = None
            if ing_lower in lookup:
                matched = lookup[ing_lower]
            else:
                for alias_k, info in lookup.items():
                    if alias_k in ing_lower or ing_lower in alias_k:
                        matched = info
                        break

            if matched and matched["name"] not in seen:
                seen.add(matched["name"])
                if matched["risk_level"] in ("High", "Moderate"):
                    flagged_list.append({
                        "name": matched["name"],
                        "category": matched["category"],
                        "risk_level": matched["risk_level"],
                        "potential_concerns": [matched["health_effects"]],
                        "explanation": f"{matched['name']} is regulated under food safety guidelines ({matched.get('fssai_ref') or 'FSSAI/Codex'}). {matched['health_effects']}",
                        "dose_dependency": True,
                        "precautions": "Consume within recommended daily intake limits.",
                    })
    except Exception as e:
        logger.warning(f"Error querying local database for fallback: {e}")
    finally:
        if conn:
            conn.close()

    # Build macronutrients structure
    macros = {
        "calories_kcal": None,
        "carbohydrates_g": None,
        "protein_g": None,
        "total_fat_g": None,
        "saturated_fat_g": None,
        "trans_fat_g": None,
        "dietary_fibre_g": None,
        "total_sugar_g": None,
        "added_sugar_g": None,
        "data_source": "not_available",
    }

    if nutrition_data and isinstance(nutrition_data, dict):
        for key in macros:
            if key in nutrition_data and nutrition_data[key] is not None:
                try:
                    macros[key] = float(nutrition_data[key])
                    macros["data_source"] = "nutrition_label"
                except (ValueError, TypeError):
                    pass

    # Curate basic fallback alternatives from SQLite
    fallback_alts = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, score, price, note FROM alternatives LIMIT 3")
        for r in cursor.fetchall():
            fallback_alts.append({
                "name": r["name"],
                "brand": "Recommended Alternative",
                "score": r["score"],
                "price": r["price"],
                "why_healthier": r["note"] or "Healthier alternative with lower processing and better nutrients.",
                "avoided_ingredients": [f["name"] for f in flagged_list[:2]],
                "key_benefits": ["Lower processed additives", "Better ingredient balance"],
                "swap_type": "Packaged Brand",
            })
        conn.close()
    except Exception:
        pass

    return {
        "status": "fallback",
        "product_analysis": {
            "harmful_ingredients": flagged_list,
            "macronutrients": macros,
            "nutritional_assessment": {
                "overall_rating": "Moderate" if flagged_list else "Good",
                "protein_assessment": "Exact protein values require the package nutrition facts panel.",
                "sugar_assessment": "Assess total sugars from the nutrition label.",
                "fat_assessment": "Assess saturated and trans fat content from the nutrition label.",
                "overall_summary": f"Analyzed using curated local safety standards. {len(flagged_list)} flagged ingredients identified.",
            },
            "ingredient_summary": f"Extracted {len(ingredients)} ingredients. ({fallback_reason})",
            "health_recommendation": "Review flagged ingredients if you have metabolic conditions, allergies, or dietary restrictions.",
            "healthy_alternatives": fallback_alts,
        },
    }


# ==============================================================================
# Core Gemini Analysis Function
# ==============================================================================

def analyze_product(
    ingredients: List[str],
    nutrition_data: Optional[Dict[str, Any]] = None,
    product_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point for Gemini-based ingredient safety and nutritional analysis.

    Args:
        ingredients: List of extracted ingredient strings.
        nutrition_data: Optional dictionary of numerical values from a nutrition label.
        product_name: Optional name/title of the product.

    Returns:
        Structured dictionary conforming to the expected JSON schema:
        {
            "status": "success" | "fallback",
            "product_analysis": { ... }
        }
    """
    # 1. Clean and validate ingredient list
    cleaned_ingredients = [ing.strip() for ing in ingredients if isinstance(ing, str) and ing.strip()]
    if not cleaned_ingredients:
        raise ValueError("Cannot analyze an empty or invalid ingredient list.")

    # 2. Check API key
    api_key = settings.get_api_key()
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured in environment. Using local safety database fallback.")
        return _generate_fallback_analysis(
            ingredients=cleaned_ingredients,
            nutrition_data=nutrition_data,
            product_name=product_name,
            fallback_reason="No GEMINI_API_KEY configured in environment variables.",
        )

    # 3. Import and initialize GenAI client
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError as e:
        logger.error(f"google-genai SDK not installed or import failed: {e}")
        return _generate_fallback_analysis(
            ingredients=cleaned_ingredients,
            nutrition_data=nutrition_data,
            product_name=product_name,
            fallback_reason="google-genai SDK not available.",
        )

    client = genai.Client(api_key=api_key)
    prompt = _build_analysis_prompt(cleaned_ingredients, nutrition_data, product_name)
    model_name = settings.GEMINI_ANALYSIS_MODEL

    # 4. Execute API call with retries for transient errors
    max_retries = max(1, settings.GEMINI_MAX_RETRIES)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Calling Gemini API (model={model_name}, attempt={attempt}/{max_retries})...")
            
            config = types.GenerateContentConfig(
                system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=AnalyzeProductResponse,
                temperature=0.2,
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

            raw_text = (response.text or "").strip()
            if not raw_text:
                raise ValueError("Received empty response from Gemini API.")

            # Parse and validate response against Pydantic schema
            # Strip code blocks if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed_data = json.loads(raw_text)
            validated = AnalyzeProductResponse.model_validate(parsed_data)
            result_dict = validated.model_dump()

            # 5. Enforce strict numerical macronutrient rule:
            # If no nutrition data was supplied, all numerical values MUST be None/null
            if not nutrition_data or not any(nutrition_data.values()):
                macros = result_dict["product_analysis"]["macronutrients"]
                for num_key in [
                    "calories_kcal",
                    "carbohydrates_g",
                    "protein_g",
                    "total_fat_g",
                    "saturated_fat_g",
                    "trans_fat_g",
                    "dietary_fibre_g",
                    "total_sugar_g",
                    "added_sugar_g",
                ]:
                    macros[num_key] = None
                macros["data_source"] = "not_available"

            result_dict["status"] = "success"
            logger.info("Gemini analysis completed successfully.")
            return result_dict

        except (json.JSONDecodeError, ValidationError) as parse_err:
            logger.warning(f"Response validation error on attempt {attempt}: {parse_err}")
            last_error = parse_err
        except APIError as api_err:
            logger.warning(f"Gemini API error on attempt {attempt}: {api_err}")
            last_error = api_err
            # If transient, sleep with exponential backoff
            if attempt < max_retries:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
        except Exception as generic_err:
            logger.error(f"Unexpected error during Gemini analysis attempt {attempt}: {generic_err}")
            last_error = generic_err
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

    # If all retries failed, fall back gracefully
    logger.error(f"All {max_retries} Gemini API attempts failed. Falling back to local analysis. Last error: {last_error}")
    return _generate_fallback_analysis(
        ingredients=cleaned_ingredients,
        nutrition_data=nutrition_data,
        product_name=product_name,
        fallback_reason=f"Gemini analysis service temporarily unavailable: {type(last_error).__name__}",
    )


# ==============================================================================
# Gemini Healthier Alternatives Service
# ==============================================================================

ALTERNATIVES_SYSTEM_INSTRUCTION = """You are an expert clinical nutritionist and consumer food guide specializing in packaged food substitutions and clean-label alternatives.
Your goal is to recommend healthier food alternatives and swaps that replace an unhealthy or processed food item.

Guidelines:
1. HEALTHIER REPLACEMENTS:
   - Identify the primary nutritional pitfalls of the original product (e.g., high refined sugar, palm oil, refined flour/maida, artificial colors/flavors, high sodium, trans fats).
   - Propose 3 to 5 realistic, accessible, and healthier alternatives that directly resolve these pitfalls.
   - For each alternative, explicitly list which harmful ingredients from the original product are avoided (e.g., 'Palm Oil', 'Tartrazine', 'Refined Wheat Flour').
   - Provide a clear, evidence-based 'why_healthier' reason highlighting better ingredient quality (e.g., uses cold-pressed oils, unrefined jaggery/dates, 100% whole millets, zero synthetic preservatives).
   - Highlight key nutritional benefits (e.g., 'High dietary fiber', 'Clean protein source', 'Zero artificial additives').

2. VARIETY OF SWAPS:
   - Provide a balanced mix of:
     a) Clean-label packaged brand alternatives (commercially available brands known for clean ingredients).
     b) Wholesome kitchen/whole-food alternatives (unprocessed or minimally processed foods like roasted seeds/nuts, fresh curd, makhana, fruit/nut mixes).
   - Set 'swap_type' to 'Packaged Brand', 'Whole Food Alternative', or 'Clean Label'.

3. REALISTIC ESTIMATES:
   - Assign an estimated health score (0-100) reflecting clean formulation (typically 75 to 95).
   - Provide practical price comparisons (e.g., 'Similar price', 'Budget-friendly', 'Slightly premium').
   - Provide 2-3 actionable grocery shopping tips for identifying clean versions in this food category.
"""


def _build_alternatives_prompt(
    product_name: str,
    category: Optional[str] = None,
    ingredients: Optional[List[str]] = None,
    current_score: Optional[int] = None,
    flagged_ingredients: Optional[List[str]] = None,
) -> str:
    lines = [
        f"Product Name: {product_name}",
        f"Category: {category or 'General Packaged Food'}",
    ]
    if current_score is not None:
        lines.append(f"Current Health Score: {current_score}/100")
    if flagged_ingredients:
        lines.append(f"Flagged Harmful / Watch Ingredients: {', '.join(flagged_ingredients)}")
    if ingredients:
        lines.append(f"Full Ingredients List ({len(ingredients)} items): {json.dumps(ingredients)}")
    lines.append("\nSuggest 3 to 5 significantly healthier, realistic alternative swaps and practical grocery shopping tips in the requested JSON schema.")
    return "\n".join(lines)


def _generate_fallback_alternatives(
    product_name: str,
    category: Optional[str] = None,
    ingredients: Optional[List[str]] = None,
    current_score: Optional[int] = None,
    flagged_ingredients: Optional[List[str]] = None,
    fallback_reason: str = "Gemini API unavailable; using curated local alternatives database.",
) -> Dict[str, Any]:
    cat = category or "Namkeen / Fried Snacks"
    conn = None
    alts = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, score, price, note FROM alternatives WHERE category_name = ? ORDER BY score DESC LIMIT 4", (cat,))
        rows = cursor.fetchall()
        if not rows:
            cursor.execute("SELECT name, score, price, note FROM alternatives ORDER BY score DESC LIMIT 3")
            rows = cursor.fetchall()
        for r in rows:
            alts.append({
                "name": r["name"],
                "brand": "Recommended Alternative",
                "score": r["score"],
                "price": r["price"],
                "why_healthier": r["note"] or "Cleaner formulation with lower additives and higher nutritional density.",
                "avoided_ingredients": flagged_ingredients or ["Trans fats", "Palm oil", "Synthetic food colors"],
                "key_benefits": ["Lower processed ingredients", "FSSAI aligned"],
                "swap_type": "Packaged Brand" if "₹" in r["price"] else "Whole Food Alternative",
            })
    except Exception as e:
        logger.warning(f"Error querying local database for fallback alternatives: {e}")
    finally:
        if conn:
            conn.close()

    if not alts:
        alts = [
            {
                "name": "Roasted Makhana (Fox Nuts) with Rock Salt & Pepper",
                "brand": "Whole Food Alternative",
                "score": 92,
                "price": "₹60 / 100g (Budget-friendly)",
                "why_healthier": "Naturally roasted without hydrogenated palm oil or chemical preservatives.",
                "avoided_ingredients": flagged_ingredients or ["Palm Oil", "Artificial Colors"],
                "key_benefits": ["Rich in magnesium and antioxidants", "Zero trans fat", "Low glycemic index"],
                "swap_type": "Whole Food Alternative",
            },
            {
                "name": "100% Whole Grain Ragi / Millet Cookies",
                "brand": "Clean Label Swap",
                "score": 86,
                "price": "₹45 (Similar price)",
                "why_healthier": "Uses whole finger millet flour and jaggery instead of refined wheat flour (maida) and white sugar.",
                "avoided_ingredients": flagged_ingredients or ["Refined Wheat Flour", "Excess Sugar"],
                "key_benefits": ["High dietary fiber", "Calcium rich", "No artificial sweeteners"],
                "swap_type": "Packaged Brand",
            }
        ]

    return {
        "status": "fallback",
        "product_name": product_name,
        "category": cat,
        "current_score": current_score,
        "summary": f"Healthier swaps for {product_name} ({fallback_reason}). Switching to these options minimizes exposure to processed additives.",
        "alternatives": alts,
        "grocery_tips": [
            "Check for '100% Whole Grain' or 'Cold Pressed' on the ingredient label.",
            "Avoid products where palm oil, refined sugar, or maida appears in the top 3 ingredients.",
            "Choose products with short ingredient lists and recognized whole food ingredients."
        ],
    }


def generate_healthy_alternatives(
    product_name: str,
    category: Optional[str] = None,
    ingredients: Optional[List[str]] = None,
    current_score: Optional[int] = None,
    flagged_ingredients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates intelligent, AI-powered healthier food alternatives and swaps using Gemini.

    Args:
        product_name: Original product name.
        category: Food category.
        ingredients: List of original ingredients.
        current_score: Original product health score (0-100).
        flagged_ingredients: Flagged harmful ingredients to avoid.

    Returns:
        Structured dictionary conforming to AlternativesResponse:
        {
            "status": "success" | "fallback",
            "product_name": str,
            "category": str,
            "current_score": int,
            "summary": str,
            "alternatives": [ ... ],
            "grocery_tips": [ ... ]
        }
    """
    cleaned_name = (product_name or "").strip() or "Packaged Food Product"

    api_key = settings.get_api_key()
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured in environment. Using fallback alternatives.")
        return _generate_fallback_alternatives(
            product_name=cleaned_name,
            category=category,
            ingredients=ingredients,
            current_score=current_score,
            flagged_ingredients=flagged_ingredients,
            fallback_reason="No GEMINI_API_KEY configured in environment variables.",
        )

    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
    except ImportError as e:
        logger.error(f"google-genai SDK not installed or import failed: {e}")
        return _generate_fallback_alternatives(
            product_name=cleaned_name,
            category=category,
            ingredients=ingredients,
            current_score=current_score,
            flagged_ingredients=flagged_ingredients,
            fallback_reason="google-genai SDK not available.",
        )

    client = genai.Client(api_key=api_key)
    prompt = _build_alternatives_prompt(
        product_name=cleaned_name,
        category=category,
        ingredients=ingredients,
        current_score=current_score,
        flagged_ingredients=flagged_ingredients,
    )
    model_name = settings.GEMINI_ANALYSIS_MODEL
    max_retries = max(1, settings.GEMINI_MAX_RETRIES)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Calling Gemini API for alternatives (model={model_name}, attempt={attempt}/{max_retries})...")
            config = types.GenerateContentConfig(
                system_instruction=ALTERNATIVES_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=AlternativesResponse,
                temperature=0.3,
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw_text = (response.text or "").strip()
            if not raw_text:
                raise ValueError("Received empty response from Gemini API for alternatives.")

            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed_data = json.loads(raw_text)
            validated = AlternativesResponse.model_validate(parsed_data)
            result_dict = validated.model_dump()
            result_dict["status"] = "success"
            logger.info("Gemini alternatives generated successfully.")
            return result_dict

        except (json.JSONDecodeError, ValidationError) as parse_err:
            logger.warning(f"Response validation error on attempt {attempt}: {parse_err}")
            last_error = parse_err
        except APIError as api_err:
            logger.warning(f"Gemini API error on attempt {attempt}: {api_err}")
            last_error = api_err
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception as generic_err:
            logger.error(f"Unexpected error during Gemini alternatives attempt {attempt}: {generic_err}")
            last_error = generic_err
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

    logger.error(f"All {max_retries} Gemini API attempts failed for alternatives. Falling back to local data. Last error: {last_error}")
    return _generate_fallback_alternatives(
        product_name=cleaned_name,
        category=category,
        ingredients=ingredients,
        current_score=current_score,
        flagged_ingredients=flagged_ingredients,
        fallback_reason=f"Gemini alternatives service temporarily unavailable: {type(last_error).__name__}",
    )
