"""
Ingredient Extraction Service:
Delegates directly to the existing OCR extraction pipeline without modifying or duplicating it.
Bridges OCR output to downstream analysis services such as the Gemini analysis layer.
"""

from typing import Dict, Any, List
from extraction.base import ExtractionError
from extraction.tesseract_ocr import TesseractExtractor
from extraction.gemini_vision import GeminiVisionExtractor
from extraction.parser import parse_extraction_output, parse_ingredient_list
from image_quality import check_image_quality


def get_extractor(provider: str = "gemini"):
    """Returns the requested extraction engine without modifying existing logic."""
    if provider.lower() == "tesseract":
        return TesseractExtractor()
    return GeminiVisionExtractor()


def extract_ingredients_from_image(image_path: str, provider: str = "gemini") -> Dict[str, Any]:
    """
    Executes the existing OCR extraction pipeline on an image file.
    
    Returns:
        dict with keys:
            - raw_text: str
            - ingredients: List[str]
            - fssai_number: Optional[str]
            - product_name: Optional[str]
            - confidence: float
            - provider: str
            - quality: dict
    """
    # Run image quality pre-check as defined in the existing pipeline
    quality = check_image_quality(image_path)
    if not quality["ok"] and quality["confidence"] < 0.3:
        raise ExtractionError(
            f"Image quality too low for reliable OCR: {', '.join(quality.get('issues', []))}"
        )

    extractor = get_extractor(provider)
    result = extractor.extract(image_path)
    parsed = parse_extraction_output(result.raw_text)

    return {
        "raw_text": result.raw_text,
        "ingredients": parsed.ingredients,
        "fssai_number": parsed.fssai_number,
        "product_name": parsed.product_name,
        "confidence": result.confidence,
        "provider": result.provider,
        "quality": quality,
    }


def parse_raw_ingredients(ingredients_input: str | List[str]) -> List[str]:
    """
    Normalizes raw ingredients input (comma-separated string or list)
    into a clean list of individual ingredient strings.
    """
    if isinstance(ingredients_input, str):
        return parse_ingredient_list(ingredients_input)
    elif isinstance(ingredients_input, list):
        cleaned = []
        for item in ingredients_input:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        return cleaned
    return []

