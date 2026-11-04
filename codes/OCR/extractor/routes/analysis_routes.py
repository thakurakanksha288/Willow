"""
Analysis Routes Blueprint:
Exposes HTTP API endpoints for AI-powered product analysis.
"""

from flask import Blueprint, request, jsonify
from services.gemini_analysis_service import analyze_product, generate_healthy_alternatives
from services.ingredient_extraction_service import parse_raw_ingredients
from config.settings import logger

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/api/analyze-product", methods=["POST"])
@analysis_bp.route("/analyze-product", methods=["POST"])
def analyze_product_endpoint():
    """
    POST /api/analyze-product
    Accepts:
        {
            "ingredients": ["Sugar", "Refined Wheat Flour", ...],
            "nutrition_data": { "calories_kcal": 450, ... } | null,
            "product_name": "Optional Product Name"
        }
    Returns:
        Structured JSON response with harmful ingredients, macronutrients,
        nutritional assessment, ingredient summary, and health recommendation.
    """
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "status": "error",
            "error": "Invalid request body. Expected JSON object with 'ingredients' field."
        }), 400

    raw_ingredients = data.get("ingredients")
    if not raw_ingredients:
        return jsonify({
            "status": "error",
            "error": "Field 'ingredients' is required and must not be empty."
        }), 400

    # Parse ingredients whether sent as a list or a comma-separated string
    ingredients = parse_raw_ingredients(raw_ingredients)
    if not ingredients:
        return jsonify({
            "status": "error",
            "error": "No valid ingredients found in the 'ingredients' field."
        }), 400

    nutrition_data = data.get("nutrition_data")
    if nutrition_data is not None and not isinstance(nutrition_data, dict):
        return jsonify({
            "status": "error",
            "error": "Field 'nutrition_data' must be a JSON object (or null)."
        }), 400

    product_name = (data.get("product_name") or "").strip() or None

    try:
        result = analyze_product(
            ingredients=ingredients,
            nutrition_data=nutrition_data,
            product_name=product_name,
        )
        return jsonify(result), 200

    except ValueError as ve:
        logger.warning(f"Validation error in analyze_product: {ve}")
        return jsonify({
            "status": "error",
            "error": str(ve)
        }), 400

    except Exception as e:
        logger.error(f"Unexpected error in analyze_product_endpoint: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "An unexpected error occurred while processing the analysis."
        }), 500


@analysis_bp.route("/api/ai-alternatives", methods=["POST"])
@analysis_bp.route("/api/alternatives/generate", methods=["POST"])
def ai_alternatives_endpoint():
    """
    POST /api/ai-alternatives
    Accepts:
        {
            "product_name": "Fruit Biscuits",
            "category": "Biscuits & Cookies",
            "ingredients": ["Refined Wheat Flour", "Sugar", "Palm Oil", ...],
            "current_score": 45,
            "flagged_ingredients": ["Palm Oil", "Tartrazine"]
        }
    Returns:
        Structured JSON with AI-powered healthier food alternatives, rationale,
        avoided harmful ingredients, and smart shopping tips.
    """
    data = request.get_json(silent=True) or {}
    product_name = (data.get("product_name") or "").strip() or "Packaged Food Product"
    category = (data.get("category") or "").strip() or None
    raw_ingredients = data.get("ingredients")
    ingredients = parse_raw_ingredients(raw_ingredients) if raw_ingredients else None
    current_score = data.get("current_score")
    if current_score is not None:
        try:
            current_score = int(current_score)
        except (ValueError, TypeError):
            current_score = None

    flagged_ingredients = data.get("flagged_ingredients")
    if flagged_ingredients and isinstance(flagged_ingredients, list):
        flagged_ingredients = [str(f).strip() for f in flagged_ingredients if str(f).strip()]
    else:
        flagged_ingredients = None

    try:
        result = generate_healthy_alternatives(
            product_name=product_name,
            category=category,
            ingredients=ingredients,
            current_score=current_score,
            flagged_ingredients=flagged_ingredients,
        )
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in ai_alternatives_endpoint: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": "Failed to generate healthier alternatives."
        }), 500

