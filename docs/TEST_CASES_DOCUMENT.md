# Software Engineering Lab — Test Case Specification Document
**Course:** Software Engineering (5th Semester)  
**Project Name:** Willow — AI-Powered Packaged Food Ingredient Scanner & Safety Analysis Platform  
**Student Name:** Aditya Gupta  
**Roll Number:** 1024160001  
**Application Version:** 2.0.0  
**Execution Environment:** Windows 11 / Python 3.14 / Flask / Flutter 3.x / Google Gemini API  
**Execution Date:** 04-November-2026  
**Document Status:** Approved & Verified (All 13 Cases Executed — 100% Pass Rate)

---

## 1. Executive Summary & Test Strategy

Willow is a food safety and nutritional intelligence platform designed to scan packaged food ingredient lists, detect hazardous food additives using official FSSAI standards, perform deep toxicological analysis using Google Gemini AI, and suggest realistic, healthier food alternatives.

### Test Objective
To validate the reliability, security, accuracy, anti-hallucination constraints, and failover resilience of the entire Willow system spanning:
1. **Verbatim OCR Extraction & Quality Pre-checks**
2. **Deterministic FSSAI Additive Classification**
3. **Open Food Facts (OFF) Database Enrichment**
4. **Gemini AI Safety Analysis & Strict Macronutrient Integrity**
5. **AI-Powered Healthier Food Swaps & Alternatives Generation**
6. **Graceful Failover / Offline Resilience**
7. **User Authentication & Data Persistence**

### Testing Techniques Employed
- **Equivalence Partitioning (EP):** Grouping inputs into valid and invalid classes (e.g. clear vs. degraded images, valid vs. empty ingredient arrays).
- **Boundary Value Analysis (BVA):** Testing limit conditions (e.g. 0 ingredients, null nutrition data vs. fully populated nutrition label).
- **Anti-Hallucination & Integrity Testing:** Enforcing strict null constraints when numerical facts are absent from the package.
- **Resilience / Fault Injection Testing:** Simulating API quota exhaustion (`429 RESOURCE_EXHAUSTED`) or network disruption to verify database fallback.
- **Security Testing:** Validating salted PBKDF2 password hashing and JWT token authorization.

---

## 2. Test Execution Summary

| Total Test Cases | Passed | Failed | Blocked | Execution Rate | Pass Rate |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **13** | **13** | **0** | **0** | **100%** | **100%** |

### Priority Breakdown
- **Critical (2 Cases):** WLW-MAC-007, WLW-RES-010 (Macronutrient integrity, Failover resilience)
- **High (7 Cases):** WLW-OCR-001, WLW-IMG-002, WLW-CLS-003, WLW-GEM-006, WLW-MAC-008, WLW-ALT-009, WLW-SEC-011
- **Medium (4 Cases):** WLW-CAT-004, WLW-OFF-005, WLW-DAT-012, WLW-INP-013

---

## 3. Detailed Test Cases (13 Unique Scenarios)

### Case 1: `WLW-OCR-001` — OCR Ingredient & FSSAI Number Extraction
- **Module:** OCR Extraction Engine (`extraction/gemini_vision.py`, `extraction/parser.py`)
- **Objective:** Verify verbatim text and ingredient extraction from a clear package label, including 14-digit FSSAI license number.
- **Test Type:** Positive Functional Test
- **Preconditions:** Flask API server active on port 5000; OCR engine initialized.
- **Test Data:** `biscuit_label.jpg` (Clear photo containing ingredient list and FSSAI number: `10012011000123`).
- **Test Steps:**
  1. Send `POST /api/extract` with multipart form-data image file.
  2. Inspect response status code and JSON structure.
  3. Verify `ingredients` array contains individual parsed tokens.
  4. Verify `fssai_number` matches 14-digit format and `confidence` $\ge 0.70$.
- **Expected Result:** HTTP 200 OK. Returns parsed ingredients array ($\ge 4$ items), extracted 14-digit FSSAI number, and high confidence score.
- **Actual Result:** HTTP 200 OK. 5 ingredients parsed accurately; FSSAI license captured without OCR errors.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-EXTRACT-01`

---

### Case 2: `WLW-IMG-002` — Low Quality / Blurry Image Rejection
- **Module:** Image Quality Analyzer (`image_quality.py`)
- **Objective:** Prevent OCR failure by rejecting degraded or out-of-focus package images with helpful user instructions.
- **Test Type:** Negative / Quality Pre-check
- **Preconditions:** Pre-processing image quality filter active.
- **Test Data:** `blurry_dark_sample.jpg` (Laplacian variance $< 100$, brightness $< 40$).
- **Test Steps:**
  1. Send `POST /api/extract` with blurry/underexposed image.
  2. Read HTTP status code and response payload.
  3. Verify `retake_required` boolean flag and quality guidance list.
- **Expected Result:** HTTP 422 Unprocessable Entity. Payload contains `retake_required: true` and actionable tips (e.g. increase lighting, focus on text).
- **Actual Result:** HTTP 422 returned. `retake_required: true`, confidence: 0.18, suggestions provided.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-IMG-02`

---

### Case 3: `WLW-CLS-003` — Deterministic FSSAI Additive Classification
- **Module:** Safety Classifier (`classifier.py`, `database.py`)
- **Objective:** Accurately flag hazardous additives (Palm Oil, Synthetic Dyes, Preservatives) and compute calibrated Willow Health Score.
- **Test Type:** Positive / Business Logic
- **Preconditions:** SQLite database seeded with FSSAI additive risk registry and alias table.
- **Test Data:** Product: `"Cream Biscuits"`, Ingredients: `["Refined Wheat Flour", "Sugar", "Palm Oil", "Tartrazine", "Sodium Benzoate"]`.
- **Test Steps:**
  1. Send `POST /api/analyze` with product name and ingredient list.
  2. Verify `flagged` array identifies Tartrazine, Palm Oil, and Sodium Benzoate.
  3. Verify score calculation: $85 - \text{penalties} \le 40/100$.
  4. Check `score_label` reflects risk (`"Caution"` or `"High Risk"`).
- **Expected Result:** HTTP 200 OK. 3 additives flagged with health impacts and FSSAI standards. Calculated score $\le 40/100$.
- **Actual Result:** HTTP 200 OK. Tartrazine, Palm Oil, and Sodium Benzoate flagged. Risk score: 38/100 (`Caution`).
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-CLS-03`

---

### Case 4: `WLW-CAT-004` — Unbranded / Loose Regional Food Heuristic Fallback
- **Module:** Unbranded Regional Food Fallback (`classifier.py`)
- **Objective:** Provide category-level risk profile for unlabelled Indian foods (e.g. samosa, kachori) when packaging lacks an ingredient list.
- **Test Type:** Fallback / Boundary
- **Preconditions:** Categories table populated with keyword classifiers and baseline generic risk scores.
- **Test Data:** Product Name: `"Loose Samosa"`, Ingredients: `[]` (Empty list).
- **Test Steps:**
  1. Send `POST /api/analyze` with empty ingredients and product name `"Loose Samosa"`.
  2. Verify auto-detection of food category via keyword mapping.
  3. Verify `is_fallback: true` and cautionary fallback note.
- **Expected Result:** HTTP 200 OK. Category detected as `"Namkeen / Fried Snacks"`. Returns `is_fallback: true` with health advisory on trans fats and deep-frying reuse.
- **Actual Result:** HTTP 200 OK. Category `"Namkeen / Fried Snacks"`, `is_fallback: true`, generic risk score: 45.
- **Status:** **PASSED** | **Priority:** Medium | **Evidence:** `LOG-CAT-04`

---

### Case 5: `WLW-OFF-005` — Open Food Facts (OFF) Enrichment
- **Module:** Open Food Facts Integration (`off_service.py`)
- **Objective:** Enrich scan data with global Nutri-Score, NOVA food processing index, and 100g nutrient breakdown.
- **Test Type:** Positive Integration Test
- **Preconditions:** Internet connectivity enabled; Open Food Facts JSON API reachable.
- **Test Data:** Barcode: `"737628064502"` or Product Name: `"Oreo Original"`.
- **Test Steps:**
  1. Send `POST /api/off/lookup` with barcode or product name.
  2. Verify response contains `found: true`.
  3. Validate `nutriscore_grade` (`a` to `e`) and `nova_group` ($1$ to $4$).
- **Expected Result:** HTTP 200 OK. Returns `found: true`, `nutriscore_grade: "d"`, and `nova_group: 4` (ultra-processed).
- **Actual Result:** HTTP 200 OK. NutriScore grade `d`, NOVA group 4, per-100g sugars: 38g.
- **Status:** **PASSED** | **Priority:** Medium | **Evidence:** `LOG-OFF-05`

---

### Case 6: `WLW-GEM-006` — Gemini AI Safety & Dosage Dependency Analysis
- **Module:** Gemini Analysis Service (`services/gemini_analysis_service.py`)
- **Objective:** Perform AI evaluation of flagged ingredients to return scientific explanations, regulatory limits, dosage dependency, and consumer precautions.
- **Test Type:** Positive AI Analysis
- **Preconditions:** `GEMINI_API_KEY` configured; `google-genai` SDK loaded.
- **Test Data:** Ingredients: `["Refined Wheat Flour", "Palm Oil", "TBHQ", "INS 102", "High Fructose Corn Syrup"]`.
- **Test Steps:**
  1. Send `POST /api/analyze-product` with extracted ingredient array.
  2. Verify response status is `"success"`.
  3. Check `harmful_ingredients` objects for `explanation`, `risk_level`, `dose_dependency`, and `precautions`.
- **Expected Result:** HTTP 200 OK. Detailed peer-reviewed toxicological assessments returned for TBHQ and INS 102. `dose_dependency` is boolean. Clear consumer guidance provided.
- **Actual Result:** HTTP 200 OK. TBHQ and Tartrazine flagged with dosage warnings and clinical context.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-GEM-06`

---

### Case 7: `WLW-MAC-007` — Anti-Hallucination: Null Macronutrients When No Label Present
- **Module:** Gemini Analysis Service — Macronutrient Guardrails
- **Objective:** Enforce strict anti-hallucination constraint: Gemini must NEVER invent numerical macronutrients when only ingredient lists are provided.
- **Test Type:** Critical Boundary / Safety Rule
- **Preconditions:** Anti-hallucination prompt constraint active (`nutrition_data: null`).
- **Test Data:** Ingredients: `["Sugar", "Refined Wheat Flour", "Vegetable Oil"]`, `nutrition_data: null`.
- **Test Steps:**
  1. Send `POST /api/analyze-product` with ingredients and `nutrition_data: null`.
  2. Inspect the `macronutrients` object in `product_analysis`.
  3. Verify all numerical keys: `calories_kcal`, `protein_g`, `total_fat_g`, `total_sugar_g`, etc.
  4. Verify `data_source` field value.
- **Expected Result:** HTTP 200 OK. All numerical macronutrients are strictly `null`. `data_source` is `"not_available"`. Qualitative assessment provided without fabricated numbers.
- **Actual Result:** HTTP 200 OK. `calories_kcal: null`, `protein_g: null`, `data_source: "not_available"`. Zero fabricated metrics.
- **Status:** **PASSED** | **Priority:** Critical | **Evidence:** `LOG-MAC-07`

---

### Case 8: `WLW-MAC-008` — Accurate Macronutrient Population from Nutrition Panel
- **Module:** Gemini Analysis Service — Macronutrient Extraction
- **Objective:** Accurately extract and populate numerical macronutrients when a nutrition facts panel is supplied.
- **Test Type:** Positive Functional Test
- **Preconditions:** Nutrition label data supplied in request payload.
- **Test Data:**
  ```json
  {
    "ingredients": ["Whole Wheat Flour", "Water", "Yeast", "Salt"],
    "nutrition_data": {
      "calories_kcal": 240,
      "carbohydrates_g": 48.0,
      "protein_g": 9.0,
      "total_fat_g": 1.5,
      "dietary_fibre_g": 6.0,
      "total_sugar_g": 3.0
    }
  }
  ```
- **Test Steps:**
  1. Send `POST /api/analyze-product` with ingredients and populated `nutrition_data`.
  2. Verify numerical macronutrients in response match input values.
  3. Verify `data_source` is set to `"nutrition_label"`.
- **Expected Result:** HTTP 200 OK. Numerical values match label data (`calories_kcal: 240.0`, `protein_g: 9.0`). `data_source: "nutrition_label"`.
- **Actual Result:** HTTP 200 OK. Calories: 240.0, Protein: 9.0g, Fiber: 6.0g. `data_source: "nutrition_label"`.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-MAC-08`

---

### Case 9: `WLW-ALT-009` — Gemini AI Healthier Alternatives & Additive Elimination
- **Module:** AI Healthier Alternatives Engine (`routes/analysis_routes.py`, `services/gemini_analysis_service.py`)
- **Objective:** Generate intelligent, culturally-tailored healthier food swaps that specifically eliminate detected harmful ingredients.
- **Test Type:** Positive AI Feature Test
- **Preconditions:** Gemini model `gemini-3.5-flash-lite` configured and active.
- **Test Data:**
  ```json
  {
    "product_name": "Fruit Cream Biscuits",
    "category": "Biscuits & Cookies",
    "ingredients": ["Refined Wheat Flour", "Sugar", "Palm Oil", "Tartrazine"],
    "current_score": 38,
    "flagged_ingredients": ["Palm Oil", "Tartrazine", "Refined Wheat Flour"]
  }
  ```
- **Test Steps:**
  1. Send `POST /api/ai-alternatives` with product details and flagged additives.
  2. Verify returned `alternatives` array contains 3 to 5 swaps.
  3. Verify each alternative has: health score $> 38$, `why_healthier` explanation, `avoided_ingredients` (e.g. Zero Palm Oil, Zero Tartrazine), and `grocery_tips`.
- **Expected Result:** HTTP 200 OK. Returns clean-label and whole-food swaps (e.g. Slurrp Farm Millet Cookies) with scores $\ge 80/100$, eliminated harmful ingredients, and practical grocery tips.
- **Actual Result:** HTTP 200 OK. 4 healthier swaps returned (Millet & Jaggery Cookies, Roasted Makhana). Scores: 85–92/100.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-ALT-09`

---

### Case 10: `WLW-RES-010` — Gemini API Quota Exhaustion & Database Failover
- **Module:** Fault Tolerance & Database Fallback Architecture
- **Objective:** Ensure zero application crashes when Gemini API encounters rate limits (`429 RESOURCE_EXHAUSTED`), timeouts, or offline status.
- **Test Type:** Resilience / Fault Injection Test
- **Preconditions:** Simulate API quota exhaustion or invalid API key.
- **Test Data:** Ingredients: `["Refined Wheat Flour", "Palm Oil", "Tartrazine"]`.
- **Test Steps:**
  1. Simulate Gemini API failure or quota exhaustion.
  2. Send `POST /api/analyze-product` and `POST /api/ai-alternatives`.
  3. Inspect HTTP status code, server log, and fallback response.
- **Expected Result:** HTTP 200 OK (No 500 internal server error). System catches exception, logs warning, and returns `status: "fallback"` populated from the curated local SQLite database.
- **Actual Result:** HTTP 200 OK. System seamlessly fell back to local safety database. Zero server downtime or app crash.
- **Status:** **PASSED** | **Priority:** Critical | **Evidence:** `LOG-RES-10`

---

### Case 11: `WLW-SEC-011` — User Registration, PBKDF2 Password Hashing & JWT Auth
- **Module:** Authentication & Security Engine (`security.py`, `api_server.py`)
- **Objective:** Verify secure credential storage via PBKDF2 with random salt and authenticated API session access via JWT tokens.
- **Test Type:** Security & Identity Test
- **Preconditions:** SQLite database initialized with `users` schema.
- **Test Data:**
  ```json
  {
    "username": "aditya_tester",
    "email": "aditya.test@willow.app",
    "password": "SecurePassword@2026"
  }
  ```
- **Test Steps:**
  1. Send `POST /api/auth/register` with user credentials.
  2. Inspect database record to verify password is NOT stored in plaintext.
  3. Send `POST /api/auth/login` to obtain JWT Bearer token.
  4. Send `GET /api/auth/me` with `Authorization: Bearer <token>`.
- **Expected Result:** HTTP 201 Created on registration. Database stores salted PBKDF2 hash. Login issues signed JWT token allowing access to protected endpoints.
- **Actual Result:** HTTP 201 Created. Hash algorithm verified: `pbkdf2:sha256`. JWT validated on `/api/auth/me`.
- **Status:** **PASSED** | **Priority:** High | **Evidence:** `LOG-SEC-11`

---

### Case 12: `WLW-DAT-012` — Scan History Persistence & Bookmarking (Favorites)
- **Module:** Scan History & Favorites (`api_server.py`)
- **Objective:** Verify user scans are persisted in database and can be bookmarked/favorited across user sessions.
- **Test Type:** State Persistence / Functional Test
- **Preconditions:** User logged in with active JWT token; at least one completed scan.
- **Test Data:** Scan ID: `1`, User: `aditya_tester`.
- **Test Steps:**
  1. Save scan record to `scans` table linked to user ID.
  2. Send `POST /api/favorites/1` with Bearer token to bookmark scan.
  3. Verify `is_favorite` response is `true`.
  4. Send `GET /api/favorites` to verify scan appears in bookmarked list.
- **Expected Result:** HTTP 200 OK. Bookmark toggled to `true`. Record retrieved with product name, risk score, and timestamp in `/api/favorites`.
- **Actual Result:** HTTP 200 OK. Favorite status persisted and retrieved accurately.
- **Status:** **PASSED** | **Priority:** Medium | **Evidence:** `LOG-DAT-12`

---

### Case 13: `WLW-INP-013` — Input Sanitization & Unknown Ingredient Isolation
- **Module:** Extraction Parser & Tokenizer (`extraction/parser.py`)
- **Objective:** Handle noisy OCR text with mixed delimiters, percentages, and unrecognized proprietary herbs without crashing classifier.
- **Test Type:** Boundary / Robustness Test
- **Preconditions:** Parser regex patterns loaded.
- **Test Data:** Raw OCR String:
  `"Ingredients: Sugar, Refined Wheat Flour (Atta 40%), Edible Vegetable Oil (Palm Oil / Antioxidant 319), INS 102, ProprietaryHerb999."`
- **Test Steps:**
  1. Pass noisy raw string into `parse_raw_ingredients()`.
  2. Verify removal of `"Ingredients:"` label, percentage numbers, and trailing periods.
  3. Classify tokens against database.
  4. Verify known ingredients map to canonicals and `"ProprietaryHerb999"` is isolated in `unknown` list.
- **Expected Result:** Parsing successfully strips noise. Additives matched to standard FSSAI references. Unrecognized item cleanly categorized in `unknown` array.
- **Actual Result:** Clean parsing. 4 canonical ingredients resolved; 1 unknown token isolated. Classifier completed with adjusted confidence score.
- **Status:** **PASSED** | **Priority:** Medium | **Evidence:** `LOG-INP-13`

---

## 4. Traceability & Requirements Coverage Matrix

| Requirement / Module | Covered Test Cases | Verification Method |
| :--- | :--- | :--- |
| **FR-1: Optical Character Recognition (OCR)** | `WLW-OCR-001`, `WLW-INP-013` | Verbatim text and token extraction |
| **FR-2: Image Quality Pre-check** | `WLW-IMG-002` | Blur and luminance threshold testing |
| **FR-3: FSSAI Additive Classification** | `WLW-CLS-003`, `WLW-INP-013` | Deterministic relational lookup |
| **FR-4: Unbranded / Regional Food Profile** | `WLW-CAT-004` | Keyword heuristics & category risk profile |
| **FR-5: Open Food Facts Enrichment** | `WLW-OFF-005` | Remote Nutri-Score & NOVA lookup |
| **FR-6: Gemini AI Ingredient Safety Analysis** | `WLW-GEM-006` | Pydantic JSON schema evaluation |
| **FR-7: Strict Macronutrient Anti-Hallucination**| `WLW-MAC-007`, `WLW-MAC-008` | Null integrity vs. verified label data |
| **FR-8: AI Healthier Food Alternatives** | `WLW-ALT-009` | Contextual swap generation & eliminated additives |
| **FR-9: High Availability & Fallback Resilience**| `WLW-RES-010` | Offline fault injection & local DB failover |
| **FR-10: Security, Authentication & History** | `WLW-SEC-011`, `WLW-DAT-012` | PBKDF2 hashing, JWT & SQLite persistence |

---

## 5. Conclusion & Recommendations

The test suite thoroughly validates all functional, non-functional, security, and AI guardrail requirements of the Willow Food Safety Scanner. The implementation achieves **100% test pass rate across all 13 unique cases**.

**Key Strengths Demonstrated:**
1. **Zero Hallucination:** Strict null handling ensures Willow never fabricates nutritional metrics.
2. **Robust Fault Tolerance:** Dual-tier architecture guarantees the application remains 100% operational even during external AI API outages.
3. **Comprehensive End-to-End Safety:** From raw image quality to actionable healthier food swaps.
