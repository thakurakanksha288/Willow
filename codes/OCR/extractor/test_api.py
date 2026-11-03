"""
Integration test script for Willow API.
Tests all major endpoints to confirm the full pipeline works end-to-end.
Run from: codes/OCR/extractor/
Usage:  python test_api.py
"""
import requests
import json
import sys
import os

BASE = "http://127.0.0.1:5000"
HEADERS = {"Content-Type": "application/json"}

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"
results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append(condition)
    detail_str = f"  -> {detail}" if detail else ""
    print(f"  {status} {name}{detail_str}")

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

# -------------------------------------------------------------------
# 1. Health check
# -------------------------------------------------------------------
section("1. Health Check")
try:
    r = requests.get(f"{BASE}/api/health", timeout=5)
    data = r.json()
    check("Server is up", r.status_code == 200)
    check("Version >= 2.0.0", data.get("version", "0") >= "2.0.0", data.get("version"))
    check("OFF integration enabled", data.get("off") == "enabled")
except Exception as e:
    check("Server reachable", False, str(e))
    print(f"\n  {FAIL} Cannot reach the server. Start it with: python api_server.py")
    sys.exit(1)

# -------------------------------------------------------------------
# 2. Auth — Register + Login
# -------------------------------------------------------------------
section("2. Auth: Register & Login")
TEST_USER = "testuser_willow_ci"
TEST_PASS = "TestPass@123"
TEST_EMAIL = f"{TEST_USER}@test.com"
token = None

try:
    r = requests.post(f"{BASE}/api/auth/register", headers=HEADERS,
                      json={"username": TEST_USER, "email": TEST_EMAIL, "password": TEST_PASS}, timeout=5)
    # 201 = new user, 400/409 = already exists (both are ok for test)
    check("Register (201, 400, or 409)", r.status_code in (201, 400, 409), str(r.status_code))

    r = requests.post(f"{BASE}/api/auth/login", headers=HEADERS,
                      json={"identifier": TEST_USER, "password": TEST_PASS}, timeout=5)
    check("Login returns 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        token = r.json().get("token") or r.json().get("access_token")
        check("JWT token in response", bool(token), f"token length={len(token or '')}")
except Exception as e:
    check("Auth flow", False, str(e))

auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"} if token else HEADERS

# -------------------------------------------------------------------
# 3. Analyze — Direct classification (no image)
# -------------------------------------------------------------------
section("3. Analyze: FSSAI + OFF classification")
try:
    payload = {
        "product_name": "Haldiram Bhujia",
        "ingredients": ["refined wheat flour", "palm oil", "salt", "monosodium glutamate", "tartrazine", "sodium benzoate"],
        "fssai_number": "10015011002804"
    }
    r = requests.post(f"{BASE}/api/analyze", headers=auth_headers, json=payload, timeout=15)
    check("Analyze returns 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = r.json()
        check("risk_score present", "risk_score" in data, str(data.get("risk_score")))
        check("blended_score present", "blended_score" in data, str(data.get("blended_score")))
        check("flagged list present", "flagged" in data, f"{len(data.get('flagged', []))} flagged")
        check("alternatives present", "alternatives" in data, f"{len(data.get('alternatives', []))} alternatives")
        check("off_data field present", "off_data" in data)
        print(f"          Score: {data.get('risk_score')} | Blended: {data.get('blended_score')}")
        print(f"          Flagged: {[f['canonical'] for f in data.get('flagged', [])]}")
except Exception as e:
    check("Analyze endpoint", False, str(e))

# -------------------------------------------------------------------
# 4. OFF Lookup
# -------------------------------------------------------------------
section("4. Open Food Facts Lookup")
try:
    r = requests.post(f"{BASE}/api/off/lookup", headers=HEADERS,
                      json={"product_name": "Lays chips"}, timeout=10)
    check("OFF lookup returns 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = r.json()
        found = data.get("found", False)
        if found:
            check("NutriScore grade present", "nutriscore_grade" in data)
            check("Nutrients present", "nutrients" in data)
            print(f"          Found: {data.get('off_product_name')} | NutriScore: {data.get('nutriscore_grade')}")
        else:
            print(f"          {SKIP} Product not found on OFF (API may be down) — graceful fallback OK")
except Exception as e:
    check("OFF lookup endpoint", False, str(e))

# -------------------------------------------------------------------
# 5. Categories & Risk Profiles (FR-12/FR-13)
# -------------------------------------------------------------------
section("5. Categories & Risk Profiles (Unbranded Fallback)")
try:
    r = requests.get(f"{BASE}/api/categories", timeout=5)
    check("Categories returns 200", r.status_code == 200)
    data = r.json()
    cats = data.get("categories", [])
    check("Has >=5 categories", len(cats) >= 5, f"{len(cats)} categories")

    r2 = requests.get(f"{BASE}/api/categories/risk-profiles", timeout=5)
    check("Risk profiles returns 200", r2.status_code == 200)
    profiles = r2.json().get("profiles", [])
    check("Has >=3 risk profiles", len(profiles) >= 3, f"{len(profiles)} profiles")
    if profiles:
        p = profiles[0]
        check("Profile has note field", "note" in p)
        check("Profile has generic_risk", "generic_risk" in p)
except Exception as e:
    check("Categories/Profiles", False, str(e))

# -------------------------------------------------------------------
# 6. Scan History (requires auth)
# -------------------------------------------------------------------
section("6. Scan History (Auth required)")
if token:
    try:
        r = requests.get(f"{BASE}/api/history", headers=auth_headers, timeout=5)
        check("History returns 200", r.status_code == 200, str(r.status_code))
        hist = r.json().get("history", [])
        check("History is a list", isinstance(hist, list), f"{len(hist)} items")
    except Exception as e:
        check("History endpoint", False, str(e))
else:
    print(f"  {SKIP} Skipped — no auth token")

# -------------------------------------------------------------------
# 7. Manual Analyze (FR-15 — no image)
# -------------------------------------------------------------------
section("7. Manual Entry Flow (FR-15)")
try:
    payload = {
        "product_name": "Homemade Namkeen",
        "ingredients": ["besan", "refined oil", "salt", "red chili", "ajwain"],
    }
    r = requests.post(f"{BASE}/api/analyze", headers=HEADERS, json=payload, timeout=12)
    check("Manual analyze returns 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        d = r.json()
        check("score_label present", "score_label" in d, d.get("score_label"))
        check("is_fallback field present", "is_fallback" in d)
except Exception as e:
    check("Manual analyze", False, str(e))

# -------------------------------------------------------------------
# 8. AI-Powered Gemini Product Analysis Layer (POST /api/analyze-product)
# -------------------------------------------------------------------
section("8. Gemini Analysis Layer (/api/analyze-product)")
try:
    payload_without_macros = {
        "ingredients": [
            "Refined Wheat Flour",
            "Sugar",
            "Palm Oil",
            "Tartrazine",
            "Sodium Benzoate",
            "Monosodium Glutamate"
        ],
        "nutrition_data": None,
        "product_name": "Ultra-Processed Snack"
    }
    r = requests.post(f"{BASE}/api/analyze-product", headers=HEADERS, json=payload_without_macros, timeout=20)
    check("Analyze-product endpoint returns 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = r.json()
        check("Status field present", data.get("status") in ("success", "fallback"), data.get("status"))
        check("product_analysis present", "product_analysis" in data)
        analysis = data.get("product_analysis", {})
        check("harmful_ingredients is list", isinstance(analysis.get("harmful_ingredients"), list))
        check("macronutrients present", "macronutrients" in analysis)
        macros = analysis.get("macronutrients", {})
        check("macronutrients null when no label", macros.get("calories_kcal") is None)
        check("data_source is not_available", macros.get("data_source") == "not_available")
        check("nutritional_assessment present", "nutritional_assessment" in analysis)
        check("ingredient_summary present", bool(analysis.get("ingredient_summary")))
        check("health_recommendation present", bool(analysis.get("health_recommendation")))

    # Test with nutrition label data provided
    payload_with_macros = {
        "ingredients": ["Whole Wheat Flour", "Water", "Yeast", "Salt"],
        "nutrition_data": {
            "calories_kcal": 240,
            "carbohydrates_g": 48.0,
            "protein_g": 9.0,
            "total_fat_g": 1.5,
            "dietary_fibre_g": 6.0,
            "total_sugar_g": 3.0
        },
        "product_name": "Whole Wheat Bread"
    }
    r2 = requests.post(f"{BASE}/api/analyze-product", headers=HEADERS, json=payload_with_macros, timeout=20)
    check("Analyze-product with nutrition_data returns 200", r2.status_code == 200, str(r2.status_code))
    if r2.status_code == 200:
        d2 = r2.json().get("product_analysis", {})
        m2 = d2.get("macronutrients", {})
        check("Calories populated from nutrition_data", m2.get("calories_kcal") == 240.0)
        check("data_source is nutrition_label", m2.get("data_source") == "nutrition_label")

except Exception as e:
    check("Analyze-product endpoint", False, str(e))

# -------------------------------------------------------------------
# 9. Gemini AI Healthier Alternatives Endpoint
# -------------------------------------------------------------------
section("9. Gemini AI Healthier Alternatives (/api/ai-alternatives)")
try:
    alt_payload = {
        "product_name": "Fruit Cream Biscuits",
        "category": "Biscuits & Cookies",
        "ingredients": ["Refined Wheat Flour", "Sugar", "Palm Oil", "Tartrazine", "Invert Sugar Syrup"],
        "current_score": 38,
        "flagged_ingredients": ["Palm Oil", "Tartrazine", "Refined Wheat Flour"]
    }
    r_alt = requests.post(f"{BASE}/api/ai-alternatives", headers=HEADERS, json=alt_payload, timeout=25)
    check("AI alternatives returns 200", r_alt.status_code == 200, str(r_alt.status_code))
    if r_alt.status_code == 200:
        alt_data = r_alt.json()
        check("Status field present", alt_data.get("status") in ("success", "fallback"), alt_data.get("status"))
        check("product_name echoed", alt_data.get("product_name") == "Fruit Cream Biscuits")
        check("alternatives list present", isinstance(alt_data.get("alternatives"), list))
        alts = alt_data.get("alternatives", [])
        check("at least 1 alternative returned", len(alts) >= 1, f"Count: {len(alts)}")
        if alts:
            first = alts[0]
            check("alternative has name", bool(first.get("name")), first.get("name"))
            check("alternative has higher score", first.get("score", 0) > 38, f"Score: {first.get('score')}")
            check("alternative has why_healthier", bool(first.get("why_healthier")))
        check("grocery_tips present", isinstance(alt_data.get("grocery_tips"), list) and len(alt_data.get("grocery_tips")) > 0)
except Exception as e:
    check("AI alternatives endpoint", False, str(e))

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
section("Summary")
total = len(results)
passed = sum(results)
failed = total - passed
status_icon = "[OK]" if failed == 0 else "[WARN]"
print(f"\n  {status_icon}  {passed}/{total} checks passed", end="")
if failed > 0:
    print(f"  ({failed} failed)")
else:
    print("  -- All clear!")
print()
sys.exit(0 if failed == 0 else 1)
