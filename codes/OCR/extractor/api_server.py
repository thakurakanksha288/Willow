"""
Willow Backend API Server:
- Robust OCR extraction with local pre-processing and Gemini Vision / Tesseract engines
- Deterministic FSSAI-aligned classification & health risk analysis
- SQLite relational database with categories, ingredients, aliases, and alternatives
- Secure user registration, authentication (PBKDF2 salted hash, JWT tokens)
- User scan history and favorites persistence
- Complete error handling and input sanitization

Run:
    python api_server.py
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Ensure directory is on sys.path regardless of execution working directory
_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from dotenv import load_dotenv
load_dotenv(_BASE_DIR / ".env")

from flask import Flask, request, jsonify
from flask_cors import CORS

from database import init_db, get_db_connection
from security import (
    hash_password,
    verify_password,
    generate_token,
    validate_user_input,
    token_required,
    optional_token,
)
from extraction.base import ExtractionError
from extraction.tesseract_ocr import TesseractExtractor
from extraction.gemini_vision import GeminiVisionExtractor
from extraction.parser import parse_extraction_output, parse_ingredient_list
from classifier import classify_product
from off_service import search_by_name, lookup_by_barcode, extract_off_data, compute_blended_score
from image_quality import check_image_quality
from routes.analysis_routes import analysis_bp

# Initialize database schema and seed data
init_db()

app = Flask(__name__)
# Enable CORS for Flutter app communication across local devices / web / desktop
CORS(app, resources={r"/*": {"origins": "*"}})

# Register AI Analysis Blueprint
app.register_blueprint(analysis_bp)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit


def get_extractor(provider: str):
    if provider == "tesseract":
        return TesseractExtractor()
    return GeminiVisionExtractor()


# ==========================================
# 1. AUTHENTICATION & USER MANAGEMENT
# ==========================================

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    val_err = validate_user_input(username, email, password)
    if val_err:
        return jsonify({"error": val_err}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for existing email or username
    cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", (email, username))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "An account with this email or username already exists."}), 409

    hashed = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed),
        )
        user_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": "Failed to create account. Please try again."}), 500

    token = generate_token(user_id, username, email)
    conn.close()

    return jsonify({
        "message": "Account created successfully",
        "token": token,
        "user": {
            "id": user_id,
            "username": username,
            "email": email,
        }
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Please provide your email/username and password."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, email, password_hash FROM users WHERE LOWER(email) = ? OR LOWER(username) = ?",
        (identifier, identifier),
    )
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email/username or password."}), 401

    token = generate_token(user["id"], user["username"], user["email"])

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        }
    }), 200


@app.route("/api/auth/me", methods=["GET"])
@token_required
def me():
    user_id = int(request.user.get("user_id", request.user.get("sub", 0)))
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM scans WHERE user_id = ?", (user_id,))
    scan_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,))
    favorite_count = cursor.fetchone()[0]

    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "scan_count": scan_count,
            "favorite_count": favorite_count,
        }
    })


# ==========================================
# 2. OCR EXTRACTION ENDPOINTS
# ==========================================

@app.route("/extract", methods=["POST"])
@app.route("/api/extract", methods=["POST"])
def extract():
    """Verbatim text and ingredient extraction from uploaded package image."""
    if "image" not in request.files:
        return jsonify({"error": "No 'image' file provided in form data"}), 400

    file = request.files["image"]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Allowed: jpg, jpeg, png, webp."}), 400

    provider = request.form.get("provider", "gemini")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # ── FR-3: Image quality pre-check ─────────────────────────────────────
        quality = check_image_quality(tmp_path)
        if not quality["ok"] and quality["confidence"] < 0.3:
            return jsonify({
                "error": "Image quality too low for reliable OCR",
                "quality_issues": quality["issues"],
                "suggestions": quality["suggestions"],
                "confidence": quality["confidence"],
                "retake_required": True,
            }), 422

        extractor = get_extractor(provider)
        result = extractor.extract(tmp_path)
        parsed = parse_extraction_output(result.raw_text)

        return jsonify({
            "raw_text": result.raw_text,
            "ingredients": parsed.ingredients,
            "fssai_number": parsed.fssai_number,
            "product_name": parsed.product_name,
            "confidence": result.confidence,
            "provider": result.provider,
        })
    except ExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Image processing failed: {str(e)}"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==========================================
# 3. ANALYSIS & CLASSIFICATION ENDPOINTS
# ==========================================

@app.route("/api/analyze", methods=["POST"])
@optional_token
def analyze():
    """Analyzes a structured list of ingredients against curated FSSAI database."""
    data = request.get_json(silent=True) or {}
    product_name = (data.get("product_name") or "").strip()
    ingredients = data.get("ingredients") or []
    fssai_number = (data.get("fssai_number") or "").strip() or None
    manual_category = (data.get("category") or "").strip() or None
    user_id = int(request.user.get("user_id", request.user.get("sub", 0))) if request.user else None

    # Handle single string input if sent instead of array
    if isinstance(ingredients, str):
        ingredients = parse_ingredient_list(ingredients)

    result = classify_product(
        product_name=product_name,
        raw_ingredients=ingredients,
        fssai_number=fssai_number,
        user_id=user_id,
        manual_category=manual_category,
    )

    # Enrich with Open Food Facts data (non-blocking — failures silently ignored)
    try:
        off_product = search_by_name(product_name) if product_name else None
        if off_product:
            off_data = extract_off_data(off_product)
            result["off_data"] = off_data
            result["blended_score"] = compute_blended_score(result["risk_score"], off_data)
        else:
            result["off_data"] = None
            result["blended_score"] = result["risk_score"]
    except Exception:
        result["off_data"] = None
        result["blended_score"] = result["risk_score"]

    return jsonify(result), 200


@app.route("/api/scan-and-analyze", methods=["POST"])
@optional_token
def scan_and_analyze():
    """One-stop endpoint: Uploads image -> performs OCR -> classifies -> returns results."""
    if "image" not in request.files:
        return jsonify({"error": "No 'image' file provided"}), 400

    file = request.files["image"]
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"Unsupported file type '{ext}'"}), 400

    provider = request.form.get("provider", "gemini")
    product_hint = request.form.get("product_name", "")
    manual_category = request.form.get("category", "")
    user_id = int(request.user.get("user_id", request.user.get("sub", 0))) if request.user else None

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # ── FR-3: Image quality pre-check ─────────────────────────────────────
        quality = check_image_quality(tmp_path)
        if not quality["ok"] and quality["confidence"] < 0.3:
            return jsonify({
                "error": "Image quality too low for reliable OCR",
                "quality_issues": quality["issues"],
                "suggestions": quality["suggestions"],
                "confidence": quality["confidence"],
                "retake_required": True,
            }), 422

        extractor = get_extractor(provider)
        result = extractor.extract(tmp_path)
        parsed = parse_extraction_output(result.raw_text)

        p_name = product_hint or parsed.product_name or "Scanned Product"
        analysis = classify_product(
            product_name=p_name,
            raw_ingredients=parsed.ingredients,
            fssai_number=parsed.fssai_number,
            user_id=user_id,
            manual_category=manual_category or None,
        )

        # Enrich with Open Food Facts (non-blocking)
        try:
            off_product = search_by_name(p_name)
            if off_product:
                off_data = extract_off_data(off_product)
                analysis["off_data"] = off_data
                analysis["blended_score"] = compute_blended_score(analysis["risk_score"], off_data)
            else:
                analysis["off_data"] = None
                analysis["blended_score"] = analysis["risk_score"]
        except Exception:
            analysis["off_data"] = None
            analysis["blended_score"] = analysis["risk_score"]

        analysis["raw_text"] = result.raw_text
        analysis["provider"] = result.provider
        return jsonify(analysis), 200

    except ExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Scan failed: {str(e)}"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==========================================
# 4. SCAN HISTORY & FAVORITES
# ==========================================

@app.route("/api/history", methods=["GET"])
@token_required
def history():
    user_id = int(request.user.get("user_id", request.user.get("sub", 0)))
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.product_name, s.category, s.risk_score, s.confidence,
               s.flagged_json, s.clean_json, s.unknown_json, s.fssai_number,
               s.is_fallback, s.fallback_note, s.created_at,
               CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END AS is_favorite
        FROM scans s
        LEFT JOIN favorites f ON s.id = f.scan_id AND f.user_id = s.user_id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC
        LIMIT 50
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "product_name": r["product_name"],
            "category": r["category"],
            "risk_score": r["risk_score"],
            "confidence": r["confidence"],
            "flagged": json.loads(r["flagged_json"] or "[]"),
            "clean": json.loads(r["clean_json"] or "[]"),
            "unknown": json.loads(r["unknown_json"] or "[]"),
            "fssai_number": r["fssai_number"],
            "is_fallback": bool(r["is_fallback"]),
            "fallback_note": r["fallback_note"],
            "is_favorite": bool(r["is_favorite"]),
            "created_at": r["created_at"],
        })

    return jsonify({"history": items})


@app.route("/api/favorites/<int:scan_id>", methods=["POST"])
@token_required
def toggle_favorite(scan_id):
    user_id = int(request.user.get("user_id", request.user.get("sub", 0)))
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM favorites WHERE user_id = ? AND scan_id = ?", (user_id, scan_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
        conn.commit()
        conn.close()
        return jsonify({"is_favorite": False, "message": "Removed from favorites"})
    else:
        cursor.execute("INSERT INTO favorites (user_id, scan_id) VALUES (?, ?)", (user_id, scan_id))
        conn.commit()
        conn.close()
        return jsonify({"is_favorite": True, "message": "Added to favorites"})


@app.route("/api/favorites", methods=["GET"])
@token_required
def list_favorites():
    user_id = int(request.user.get("user_id", request.user.get("sub", 0)))
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.product_name, s.category, s.risk_score, s.confidence,
               s.flagged_json, s.clean_json, s.fssai_number, s.created_at
        FROM favorites f
        JOIN scans s ON f.scan_id = s.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "product_name": r["product_name"],
            "category": r["category"],
            "risk_score": r["risk_score"],
            "confidence": r["confidence"],
            "flagged_count": len(json.loads(r["flagged_json"] or "[]")),
            "fssai_number": r["fssai_number"],
            "created_at": r["created_at"],
        })

    return jsonify({"favorites": items})


# ==========================================
# 5. DATA CATALOG LOOKUP
# ==========================================

@app.route("/api/categories", methods=["GET"])
def categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, generic_risk, note FROM categories ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify({
        "categories": [
            {"id": r["id"], "name": r["name"], "generic_risk": r["generic_risk"], "note": r["note"]}
            for r in rows
        ]
    })


@app.route("/api/categories/risk-profiles", methods=["GET"])
def category_risk_profiles():
    """
    Return full category risk profiles for unbranded product fallback (FR-12, FR-13).
    Includes keywords used to auto-detect food sub-category from product name/image text.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, generic_risk, note, keywords FROM categories ORDER BY name ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify({
        "profiles": [
            {
                "id": r["id"],
                "name": r["name"],
                "generic_risk": r["generic_risk"],
                "note": r["note"],
                "keywords": r["keywords"],
            }
            for r in rows
        ]
    })


@app.route("/api/ingredients", methods=["GET"])
def ingredients():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, canonical_name, category_name, risk_level, health_effects, fssai_ref FROM ingredients ORDER BY canonical_name ASC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify({
        "ingredients": [
            {
                "id": r["id"],
                "canonical_name": r["canonical_name"],
                "category": r["category_name"],
                "risk_level": r["risk_level"],
                "health_effects": r["health_effects"],
                "fssai_ref": r["fssai_ref"],
            }
            for r in rows
        ]
    })


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "Willow Food Safety API", "version": "2.0.0", "off": "enabled"})


# ==========================================
# 6. OPEN FOOD FACTS LOOKUP ENDPOINT
# ==========================================

@app.route("/api/off/lookup", methods=["POST"])
@optional_token
def off_lookup():
    """Look up a product on Open Food Facts by name or barcode."""
    data = request.get_json(silent=True) or {}
    product_name = (data.get("product_name") or "").strip()
    barcode = (data.get("barcode") or "").strip()

    if not product_name and not barcode:
        return jsonify({"error": "Provide 'product_name' or 'barcode'"}), 400

    off_product = None
    if barcode:
        off_product = lookup_by_barcode(barcode)
    if not off_product and product_name:
        off_product = search_by_name(product_name)

    if not off_product:
        return jsonify({"found": False, "message": "Product not found on Open Food Facts"})

    off_data = extract_off_data(off_product)
    return jsonify({"found": True, **off_data})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)