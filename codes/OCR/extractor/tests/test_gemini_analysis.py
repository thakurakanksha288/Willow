"""
Unit and integration tests for the Gemini Analysis Service and API endpoint.
Tests:
1. Schema conformity of output
2. Strict null macronutrients when no nutrition data is supplied
3. Population of macronutrients when nutrition data is supplied
4. Fallback execution when Gemini API key is missing/unavailable
5. Input validation on POST /api/analyze-product
"""

import sys
import os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Ensure parent directory is on sys.path
_current = Path(__file__).resolve().parent
_extractor_dir = _current.parent
if str(_extractor_dir) not in sys.path:
    sys.path.insert(0, str(_extractor_dir))

from services.gemini_analysis_service import (
    analyze_product,
    AnalyzeProductResponse,
    _generate_fallback_analysis,
    _build_analysis_prompt,
    generate_healthy_alternatives,
    AlternativesResponse,
    _generate_fallback_alternatives,
)
from services.ingredient_extraction_service import parse_raw_ingredients
from api_server import app


class TestGeminiAnalysisService(unittest.TestCase):

    def test_parse_raw_ingredients(self):
        """Test ingredient parsing from string and list."""
        parsed_str = parse_raw_ingredients("Sugar, Palm Oil, Tartrazine, Sodium Benzoate")
        self.assertEqual(len(parsed_str), 4)
        self.assertIn("Sugar", parsed_str)
        self.assertIn("Tartrazine", parsed_str)

        parsed_list = parse_raw_ingredients([" Sugar ", " Salt ", ""])
        self.assertEqual(parsed_list, ["Sugar", "Salt"])

    def test_empty_ingredients_raises_error(self):
        """Empty ingredients should raise ValueError."""
        with self.assertRaises(ValueError):
            analyze_product([])

    def test_fallback_schema_conformance_without_nutrition_data(self):
        """Fallback analysis must strictly conform to schema and set numerical macros to None."""
        ingredients = ["Refined Wheat Flour", "Sugar", "Palm Oil", "Tartrazine", "Sodium Benzoate"]
        res = _generate_fallback_analysis(ingredients=ingredients, nutrition_data=None, product_name="Test Cookie")

        # Validate with Pydantic
        validated = AnalyzeProductResponse.model_validate(res)
        self.assertEqual(validated.status, "fallback")

        macros = validated.product_analysis.macronutrients
        self.assertIsNone(macros.calories_kcal)
        self.assertIsNone(macros.carbohydrates_g)
        self.assertIsNone(macros.protein_g)
        self.assertIsNone(macros.total_fat_g)
        self.assertIsNone(macros.total_sugar_g)
        self.assertEqual(macros.data_source, "not_available")

        # Flagged ingredients should contain known additives
        harmful = validated.product_analysis.harmful_ingredients
        self.assertTrue(len(harmful) > 0)
        flagged_names = [h.name.lower() for h in harmful]
        self.assertTrue(any("tartrazine" in n or "sodium benzoate" in n or "palm oil" in n for n in flagged_names))

    def test_fallback_with_nutrition_data(self):
        """Fallback analysis should incorporate supplied numerical nutrition values."""
        ingredients = ["Oats", "Honey", "Almonds"]
        nutrition_data = {
            "calories_kcal": 380,
            "carbohydrates_g": 65.5,
            "protein_g": 12.0,
            "total_fat_g": 8.0,
            "saturated_fat_g": 1.2,
            "trans_fat_g": 0.0,
            "dietary_fibre_g": 9.0,
            "total_sugar_g": 14.0,
            "added_sugar_g": 5.0,
        }
        res = _generate_fallback_analysis(ingredients=ingredients, nutrition_data=nutrition_data)

        validated = AnalyzeProductResponse.model_validate(res)
        macros = validated.product_analysis.macronutrients
        self.assertEqual(macros.calories_kcal, 380.0)
        self.assertEqual(macros.protein_g, 12.0)
        self.assertEqual(macros.total_sugar_g, 14.0)
        self.assertEqual(macros.data_source, "nutrition_label")

    def test_prompt_construction(self):
        """Prompt should include clear instructions on macronutrients."""
        prompt_no_nutr = _build_analysis_prompt(["Sugar", "Salt"], nutrition_data=None)
        self.assertIn("CRITICAL RULE", prompt_no_nutr)
        self.assertIn("set ALL numerical macronutrient values", prompt_no_nutr)

        prompt_with_nutr = _build_analysis_prompt(["Sugar", "Salt"], nutrition_data={"calories_kcal": 200})
        self.assertIn("Supplied Nutrition Label Data", prompt_with_nutr)
        self.assertIn("200", prompt_with_nutr)

    @patch("config.settings.settings.get_api_key", return_value="fake_test_key")
    @patch("google.genai.Client")
    def test_analyze_product_with_mocked_gemini(self, mock_client_cls, mock_get_api_key):
        """Test analyze_product with simulated Gemini API response."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_gemini_payload = {
            "status": "success",
            "product_analysis": {
                "harmful_ingredients": [
                    {
                        "name": "Tartrazine",
                        "category": "Synthetic Colour",
                        "risk_level": "Moderate",
                        "potential_concerns": ["Hyperactivity in children", "Allergic reactions"],
                        "explanation": "Azo dye linked to behavioral reactions in sensitive demographics.",
                        "dose_dependency": True,
                        "precautions": "Avoid excessive intake, especially for children.",
                    }
                ],
                "macronutrients": {
                    "calories_kcal": 450.0,  # Should be forced to None if no nutrition_data supplied!
                    "carbohydrates_g": 60.0,
                    "protein_g": 5.0,
                    "total_fat_g": 15.0,
                    "saturated_fat_g": 7.0,
                    "trans_fat_g": 0.0,
                    "dietary_fibre_g": 2.0,
                    "total_sugar_g": 30.0,
                    "added_sugar_g": 25.0,
                    "data_source": "nutrition_label",
                },
                "nutritional_assessment": {
                    "overall_rating": "Poor",
                    "protein_assessment": "Low protein density relative to carbohydrates.",
                    "sugar_assessment": "High refined sugar formulation.",
                    "fat_assessment": "Elevated saturated fat from vegetable fats.",
                    "overall_summary": "High energy-density ultra-processed snack.",
                },
                "ingredient_summary": "Processed confectionery product containing artificial food coloring.",
                "health_recommendation": "Consume occasionally as a discretionary treat.",
            },
        }

        mock_response = MagicMock()
        import json
        mock_response.text = json.dumps(mock_gemini_payload)
        mock_client.models.generate_content.return_value = mock_response

        # Case 1: Without nutrition_data -> Must enforce numerical values to None!
        res = analyze_product(["Sugar", "Tartrazine"], nutrition_data=None)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["product_analysis"]["macronutrients"]["calories_kcal"], None)
        self.assertEqual(res["product_analysis"]["macronutrients"]["data_source"], "not_available")
        self.assertEqual(len(res["product_analysis"]["harmful_ingredients"]), 1)
        self.assertEqual(res["product_analysis"]["harmful_ingredients"][0]["name"], "Tartrazine")


class TestAnalysisApiEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_fallback_alternatives_schema_conformance(self):
        """Fallback alternatives must strictly conform to AlternativesResponse schema."""
        res = _generate_fallback_alternatives(
            product_name="Potato Chips",
            category="Namkeen / Fried Snacks",
            current_score=40,
            flagged_ingredients=["Palm Oil", "Excess Salt"]
        )
        validated = AlternativesResponse.model_validate(res)
        self.assertEqual(validated.status, "fallback")
        self.assertEqual(validated.product_name, "Potato Chips")
        self.assertTrue(len(validated.alternatives) > 0)
        first_alt = validated.alternatives[0]
        self.assertTrue(first_alt.score > 40)
        self.assertTrue(bool(first_alt.why_healthier))
        self.assertTrue(len(validated.grocery_tips) > 0)

    def test_missing_body(self):
        res = self.client.post("/api/analyze-product", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("status"), "error")

    def test_missing_ingredients(self):
        res = self.client.post("/api/analyze-product", json={"nutrition_data": None})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("ingredients", data.get("error", "").lower())

    def test_invalid_nutrition_data_type(self):
        res = self.client.post("/api/analyze-product", json={
            "ingredients": ["Sugar", "Flour"],
            "nutrition_data": "invalid_string_not_dict"
        })
        self.assertEqual(res.status_code, 400)

    def test_successful_analyze_product_endpoint(self):
        payload = {
            "ingredients": ["Sugar", "Refined Wheat Flour", "Palm Oil", "Monosodium Glutamate"],
            "nutrition_data": None,
            "product_name": "Test Snack"
        }
        res = self.client.post("/api/analyze-product", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("status", data)
        self.assertIn("product_analysis", data)
        analysis = data["product_analysis"]
        self.assertIn("harmful_ingredients", analysis)
        self.assertIn("macronutrients", analysis)
        self.assertIn("nutritional_assessment", analysis)
        self.assertIn("ingredient_summary", analysis)
        self.assertIn("health_recommendation", analysis)

        # Check macronutrients structure
        macros = analysis["macronutrients"]
        self.assertIsNone(macros["calories_kcal"])
        self.assertEqual(macros["data_source"], "not_available")

    def test_ai_alternatives_endpoint(self):
        payload = {
            "product_name": "Fruit Biscuits",
            "category": "Biscuits & Cookies",
            "ingredients": ["Refined Wheat Flour", "Palm Oil", "Sugar", "Tartrazine"],
            "current_score": 42,
            "flagged_ingredients": ["Palm Oil", "Tartrazine"]
        }
        res = self.client.post("/api/ai-alternatives", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("status", data)
        self.assertIn("product_name", data)
        self.assertIn("alternatives", data)
        self.assertTrue(len(data["alternatives"]) > 0)
        alt = data["alternatives"][0]
        self.assertIn("name", alt)
        self.assertIn("score", alt)
        self.assertIn("why_healthier", alt)
        self.assertIn("grocery_tips", data)


if __name__ == "__main__":
    unittest.main()

