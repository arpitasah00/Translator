

# --- Standard and third-party imports ---
import os
import json
import base64
import random
import string
import secrets
from datetime import datetime, timedelta
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from ocr_utils import ocr_from_file, get_tesseract_lang_for_code, looks_like_garbled_ocr

load_dotenv()

# --- Flask app initialization ---
app = Flask(__name__)
CORS(app, origins=["http://localhost:8080", "http://127.0.0.1:8080"], supports_credentials=True)

# --- API keys and endpoints ---
API_KEY = os.environ.get("API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
HUGGINGFACE_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
HUGGINGFACE_EMOTION_MODEL_URL = os.environ.get("HUGGINGFACE_EMOTION_MODEL_URL", "https://api-inference.huggingface.co/models/bhadresh-savani/distilbert-base-uncased-emotion")
ENABLE_HUGGINGFACE_ANALYSIS = os.environ.get("ENABLE_HUGGINGFACE_ANALYSIS", "false").strip().lower() == "true"
EDENAI_API_KEY = os.environ.get("EDENAI_TOKEN")
EDENAI_IMAGE_EMOTION_URL = os.environ.get("EDENAI_IMAGE_EMOTION_URL", "https://api.edenai.run/v2/image/face_detection")

# --- JWT, DB, and other config ---
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM")
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", 60))
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "chat_translator_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Dibs@PostgreSQL_01")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor(cursor_factory=RealDictCursor)

SUPPORTED_TEXT_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "or": "Odia",
    "bn": "Bengali",
    "sa": "Sanskrit",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ru": "Russian",
    "tr": "Turkish",
    "nl": "Dutch",
    "sv": "Swedish",
}

LANGUAGE_NAME_TO_CODE = {
    name.strip().lower(): code for code, name in SUPPORTED_TEXT_LANGUAGES.items()
}


def ensure_emotion_analyses_table():
    """Create the emotion history table if it does not already exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS emotion_analyses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_text TEXT NOT NULL,
            primary_emotion VARCHAR(50) NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            emotions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            provider VARCHAR(100),
            is_favorite BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


ensure_emotion_analyses_table()

# --- API ROUTES ---

def build_retry_session():
    """Build a requests session with light retries for transient API failures."""
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def build_no_retry_session():
    """Build a requests session with retries disabled for fast-fail fallbacks."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=Retry(total=0, connect=0, read=0))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def normalize_emotion_label(label):
    label = (label or "").strip().lower()
    alias_map = {
        "happy": "joy",
        "happiness": "joy",
        "excited": "joy",
        "excitement": "joy",
        "contentment": "joy",
        "affection": "love",
        "caring": "love",
        "calm": "neutral",
        "okay": "neutral",
    }
    return alias_map.get(label, label or "neutral")


def clamp_score(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize_emotion_result(label=None, score=None, emotions=None, provider=None, fallback_reason=None):
    normalized = []
    if isinstance(emotions, list):
        for item in emotions:
            if not isinstance(item, dict):
                continue
            item_label = normalize_emotion_label(item.get("label"))
            item_score = clamp_score(item.get("score"))
            if item_label:
                normalized.append({"label": item_label, "score": item_score})

    if not normalized and label:
        normalized.append(
            {
                "label": normalize_emotion_label(label),
                "score": clamp_score(score),
            }
        )

    normalized.sort(key=lambda item: item["score"], reverse=True)
    top = normalized[0] if normalized else {"label": "neutral", "score": 0.0}

    payload = {
        "provider": provider,
        "label": top["label"],
        "score": top["score"],
        "emotions": normalized[:3],
    }
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    return payload


def analyze_sentiment_with_heuristics(text):
    """Fast local fallback for obvious emotional cues in short text."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return None

    positive_keywords = {
        "joy": [
            "brand new",
            "new car",
            "won",
            "happy",
            "great",
            "awesome",
            "amazing",
            "excited",
            "congrats",
            "congratulations",
            "celebrate",
            "success",
            "gift",
            "promotion",
            "love",
            "wonderful",
            "fantastic",
            "good news",
        ],
        "love": [
            "friend",
            "family",
            "proud",
            "care",
            "thankful",
            "grateful",
        ],
    }
    negative_keywords = {
        "sadness": [
            "sad",
            "cry",
            "lost",
            "miss",
            "heartbroken",
            "depressed",
            "unhappy",
            "grief",
            "beaten me up",
            "abused",
            "hurt me",
        ],
        "anger": [
            "angry",
            "furious",
            "hate",
            "annoyed",
            "rage",
            "mad",
            "beat me up",
            "beaten me up",
            "abuse",
            "abused",
            "hit me",
            "hurt me",
            "attacked",
            "attack",
        ],
        "fear": [
            "afraid",
            "scared",
            "terrified",
            "anxious",
            "worried",
            "panic",
            "beat me up",
            "beaten me up",
            "abuse",
            "abused",
            "threatened",
            "unsafe",
            "hurt me",
        ],
    }

    scores = {
        "joy": 0.0,
        "love": 0.0,
        "neutral": 0.0,
        "sadness": 0.0,
        "anger": 0.0,
        "fear": 0.0,
    }

    for label, keywords in positive_keywords.items():
        for keyword in keywords:
            if keyword in lowered:
                scores[label] += 0.28

    for label, keywords in negative_keywords.items():
        for keyword in keywords:
            if keyword in lowered:
                scores[label] += 0.34

    # Gentle boost for clearly celebratory sentences.
    if "!" in lowered and (scores["joy"] > 0 or scores["love"] > 0):
        scores["joy"] += 0.12

    # If we found nothing strong, don't force a heuristic result.
    strongest_label = max(scores, key=scores.get)
    strongest_score = scores[strongest_label]
    if strongest_score < 0.25:
        return None

    if scores["joy"] > 0 and scores["love"] > 0:
        scores["joy"] += 0.08

    ranked = sorted(
        (
            {"label": label, "score": clamp_score(score)}
            for label, score in scores.items()
            if score > 0
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    return normalize_emotion_result(
        emotions=ranked,
        provider="local-heuristic",
    )


def analyze_sentiment_with_local_fallback(text):
    """Always return a lightweight local emotion estimate for common text."""
    heuristic_result = analyze_sentiment_with_heuristics(text)
    if heuristic_result:
        heuristic_result["provider"] = "local-fallback"
        return heuristic_result

    lowered = (text or "").strip().lower()
    score = 0.52
    label = "neutral"

    if any(token in lowered for token in ["please", "kindly", "thanks", "thank you"]):
        label = "neutral"
        score = 0.6
    elif "!" in lowered:
        label = "surprise"
        score = 0.58
    elif "?" in lowered:
        label = "neutral"
        score = 0.55

    return normalize_emotion_result(
        label=label,
        score=score,
        emotions=[
            {"label": label, "score": score},
            {"label": "neutral", "score": 0.45 if label != "neutral" else score},
        ],
        provider="local-fallback",
    )


def choose_best_fallback_emotion(text, gemini_result):
    """Prefer obvious local cues over Gemini when the text strongly signals them."""
    heuristic_result = analyze_sentiment_with_heuristics(text)
    if not heuristic_result:
        return gemini_result

    heuristic_top = heuristic_result["emotions"][0] if heuristic_result.get("emotions") else None
    gemini_top = gemini_result["emotions"][0] if gemini_result.get("emotions") else None
    if not heuristic_top:
        return gemini_result

    # Override Gemini when local cues strongly indicate a different emotion.
    if (
        not gemini_top
        or heuristic_top["label"] != gemini_top["label"]
        or heuristic_top["score"] >= 0.55
    ):
        heuristic_result["provider"] = "local-heuristic + gemini-fallback"
        return heuristic_result

    return gemini_result

def analyze_sentiment_with_gemini(text):
    """Fallback sentiment/emotion analysis using Gemini."""
    if not API_KEY:
        raise ValueError("Gemini API key is not configured on the backend")

    headers = {"Content-Type": "application/json"}
    prompt = (
        "Analyze the emotional tone of the following text.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "label": "primary emotion",\n'
        '  "score": 0.0,\n'
        '  "emotions": [\n'
        '    {"label": "emotion", "score": 0.0}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- score values must be between 0 and 1\n"
        "- emotions must be sorted highest to lowest confidence\n"
        "- use concise labels like joy, sadness, anger, fear, surprise, love, neutral\n"
        "- choose emotions grounded in the literal meaning of the text\n"
        "- do not use extreme negative emotions unless the text clearly expresses them\n"
        "- positive life events like celebration, success, gifts, friendship, or praise usually map to joy or love\n"
        "- everyday factual text with no strong affect should be neutral\n\n"
        "Text:\n"
        f"{text}"
    )
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    response = build_no_retry_session().post(url, headers=headers, json=data, timeout=(5, 12))
    result = response.json()
    if response.status_code != 200 or "candidates" not in result:
        raise ValueError("Bad response from Gemini during sentiment analysis")

    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw_text.startswith("```"):
        raw_text = "\n".join(
            line for line in raw_text.splitlines() if not line.strip().startswith("```")
        ).strip()

    parsed = json.loads(raw_text)
    label = str(parsed.get("label") or "neutral").strip()
    score = clamp_score(parsed.get("score", 0))

    emotions = parsed.get("emotions") or []
    return normalize_emotion_result(
        label=label,
        score=score,
        emotions=emotions,
        provider="gemini-fallback",
    )


def normalize_huggingface_emotion_response(raw_result):
    """Normalize Hugging Face emotion output into a stable frontend shape."""
    candidates = raw_result
    if isinstance(raw_result, list) and raw_result and isinstance(raw_result[0], list):
        candidates = raw_result[0]
    if not isinstance(candidates, list):
        raise ValueError("Unexpected Hugging Face emotion response format")

    return normalize_emotion_result(
        emotions=candidates,
        provider="huggingface",
    )


def analyze_image_emotion_with_gemini(image_bytes, mime_type):
    """Fallback image emotion analysis using Gemini vision."""
    if not API_KEY:
        raise ValueError("Gemini API key is not configured on the backend")

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    headers = {"Content-Type": "application/json"}
    prompt = (
        "Analyze the dominant human emotion visible in this image.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "label": "primary emotion",\n'
        '  "score": 0.0,\n'
        '  "emotions": [\n'
        '    {"label": "emotion", "score": 0.0}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Focus on visible facial expression and body language\n"
        "- Use concise labels like joy, sadness, anger, fear, surprise, love, neutral\n"
        "- If no clear face or emotion is visible, return neutral with low confidence\n"
        "- Scores must be between 0 and 1 and sorted highest to lowest\n"
    )
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "image/jpeg",
                            "data": encoded,
                        }
                    },
                ]
            }
        ]
    }

    response = build_no_retry_session().post(url, headers=headers, json=data, timeout=(5, 18))
    result = response.json()
    if response.status_code != 200 or "candidates" not in result:
        raise ValueError("Bad response from Gemini during image emotion analysis")

    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw_text.startswith("```"):
        raw_text = "\n".join(
            line for line in raw_text.splitlines() if not line.strip().startswith("```")
        ).strip()

    parsed = json.loads(raw_text)
    return normalize_emotion_result(
        label=parsed.get("label"),
        score=parsed.get("score"),
        emotions=parsed.get("emotions"),
        provider="gemini-image-fallback",
    )


def extract_text_from_image_with_gemini(image_bytes, mime_type, source_language=None):
    """Use Gemini vision OCR when Tesseract output is unavailable or garbled."""
    if not API_KEY:
        return None

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    language_hint = (
        f"The text is likely in {source_language}. "
        if source_language and source_language.lower() not in {"auto", "auto-detect"}
        else ""
    )
    headers = {"Content-Type": "application/json"}
    prompt = (
        "Extract all readable text from this image. "
        f"{language_hint}"
        "Return ONLY the extracted text with line breaks preserved as much as possible. "
        "Do not translate, explain, or add extra words."
    )
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "image/jpeg",
                            "data": encoded,
                        }
                    },
                ]
            }
        ]
    }

    try:
        response = build_no_retry_session().post(
            url,
            headers=headers,
            json=data,
            timeout=(5, 20),
        )
        result = response.json()
        if response.status_code != 200:
            print("extract_text_from_image_with_gemini error:", response.status_code, result)
            return None
        return extract_gemini_text(result)
    except Exception as e:
        print("extract_text_from_image_with_gemini exception:", e)
        return None


def save_emotion_analysis(user_id, text, analysis_result):
    """Persist an emotion analysis entry for the signed-in user."""
    emotions = analysis_result.get("emotions") or []
    cursor.execute(
        """
        INSERT INTO emotion_analyses
            (user_id, source_text, primary_emotion, confidence, emotions_json, provider)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id, created_at, is_favorite
        """,
        (
            user_id,
            text,
            analysis_result.get("label") or "neutral",
            clamp_score(analysis_result.get("score")),
            json.dumps(emotions),
            analysis_result.get("provider"),
        ),
    )
    return cursor.fetchone()

# Sentiment/Emotion Analysis Endpoint
@app.route("/analyze-sentiment", methods=["POST"])
def analyze_sentiment():
    data = request.get_json()
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided"}), 400
    user_id = get_current_user_id()

    def persist_and_respond(result):
        if user_id is None or result.get("error"):
            return jsonify(result)
        try:
            row = save_emotion_analysis(user_id, text, result)
            conn.commit()
            payload = dict(result)
            payload.update(
                {
                    "id": row["id"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "is_favorite": row["is_favorite"],
                    "item_type": "analysis",
                    "history_key": f"analysis:{row['id']}",
                }
            )
            return jsonify(payload)
        except Exception as db_error:
            conn.rollback()
            payload = dict(result)
            payload["save_warning"] = f"Analysis completed but could not be saved: {db_error}"
            return jsonify(payload)

    gemini_result = None
    gemini_error = None

    def get_gemini_result():
        nonlocal gemini_result, gemini_error
        if gemini_result is not None:
            return gemini_result

        try:
            gemini_result = choose_best_fallback_emotion(
                text, analyze_sentiment_with_gemini(text)
            )
            return gemini_result
        except Exception as e:
            gemini_error = str(e)
            raise

    if not ENABLE_HUGGINGFACE_ANALYSIS or not HUGGINGFACE_API_TOKEN:
        try:
            return persist_and_respond(get_gemini_result())
        except Exception:
            fallback_result = analyze_sentiment_with_local_fallback(text)
            fallback_result["fallback_reason"] = {
                "provider": "gemini",
                "details": gemini_error,
            }
            return persist_and_respond(fallback_result)

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": text,
        "options": {
            "wait_for_model": True,
        },
    }
    try:
        response = build_no_retry_session().post(
            HUGGINGFACE_EMOTION_MODEL_URL,
            headers=headers,
            json=payload,
            timeout=(3, 8),
        )
        if response.status_code == 200:
            return persist_and_respond(normalize_huggingface_emotion_response(response.json()))
        else:
            try:
                details = response.json()
            except ValueError:
                details = response.text
            try:
                fallback_result = get_gemini_result()
                fallback_result["fallback_reason"] = {
                    "provider": "huggingface",
                    "status_code": response.status_code,
                    "details": details,
                }
                return persist_and_respond(fallback_result)
            except Exception:
                fallback_result = analyze_sentiment_with_local_fallback(text)
                fallback_result["fallback_reason"] = {
                    "provider": "huggingface+gemini",
                    "status_code": response.status_code,
                    "details": {
                        "huggingface": details,
                        "gemini": gemini_error,
                    },
                }
                return persist_and_respond(fallback_result)
    except Exception as e:
        try:
            fallback_result = get_gemini_result()
            fallback_result["fallback_reason"] = {
                "provider": "huggingface",
                "details": str(e),
            }
            return persist_and_respond(fallback_result)
        except Exception as fallback_error:
            fallback_result = analyze_sentiment_with_local_fallback(text)
            fallback_result["fallback_reason"] = {
                "provider": "huggingface+gemini",
                "details": {
                    "huggingface": str(e),
                    "gemini": str(fallback_error),
                },
            }
            return persist_and_respond(fallback_result)

# Image Emotion Analysis Endpoint
@app.route("/analyze-image-emotion", methods=["POST"])
def analyze_image_emotion():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    image_file = request.files['image']
    user_id = get_current_user_id()
    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "Uploaded image is empty"}), 400
    source_text = f"Image analysis: {image_file.filename or 'uploaded image'}"

    def persist_and_respond(result):
        if user_id is None or result.get("error"):
            return jsonify(result)
        try:
            row = save_emotion_analysis(user_id, source_text, result)
            conn.commit()
            payload = dict(result)
            payload.update(
                {
                    "id": row["id"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "is_favorite": row["is_favorite"],
                    "item_type": "analysis",
                    "history_key": f"analysis:{row['id']}",
                    "original": source_text,
                }
            )
            return jsonify(payload)
        except Exception as db_error:
            conn.rollback()
            payload = dict(result)
            payload["save_warning"] = f"Analysis completed but could not be saved: {db_error}"
            return jsonify(payload)

    # Fast working path for this project: Gemini image analysis.
    try:
        fallback_result = analyze_image_emotion_with_gemini(image_bytes, image_file.mimetype)
        if not EDENAI_API_KEY:
            return persist_and_respond(fallback_result)
    except Exception as e:
        fallback_error = str(e)
        if not EDENAI_API_KEY:
            return jsonify({"error": f"Image analysis failed: {fallback_error}"}), 500

    files = {'file': (image_file.filename, image_bytes, image_file.mimetype)}
    headers = {
        "Authorization": f"Bearer {EDENAI_API_KEY}",
    }
    data = {
        "providers": "amazon,google,microsoft",
        "attributes": "emotion"
    }
    try:
        response = build_no_retry_session().post(
            EDENAI_IMAGE_EMOTION_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=(3, 8),
        )
        if response.status_code == 200:
            eden_payload = response.json()
            if isinstance(eden_payload, dict):
                # Keep raw provider payload but normalize enough to save/display in history.
                eden_label = "neutral"
                eden_score = 0.0
                return persist_and_respond(
                    {
                        "provider": "eden-ai",
                        "label": eden_label,
                        "score": eden_score,
                        "emotions": [],
                        "raw_result": eden_payload,
                    }
                )
            return jsonify(eden_payload)
        else:
            try:
                details = response.json()
            except ValueError:
                details = response.text
            fallback_result["fallback_reason"] = {
                "provider": "eden-ai",
                "status_code": response.status_code,
                "details": details,
            }
            return persist_and_respond(fallback_result)
    except Exception as e:
        fallback_result["fallback_reason"] = {
            "provider": "eden-ai",
            "details": str(e),
        }
        return persist_and_respond(fallback_result)


# Gemini API Key
API_KEY = os.environ.get("API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# JWT settings
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM")
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", 60))

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

# Brevo email API settings
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")

# PostgreSQL connection using environment variables
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "chat_translator_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Dibs@PostgreSQL_01")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor(cursor_factory=RealDictCursor)


def get_current_user_id():
    """Extract user_id from Bearer JWT in Authorization header.

    Returns None if token is missing or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except Exception:
        return None


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_access_token(user_id: int, email: str) -> str:
    """Create a short-lived JWT for the authenticated user."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT >= 2 returns str; older returns bytes
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP using Brevo email API.

    Returns True if sending looked successful, False otherwise.
    """
    if not (BREVO_API_KEY and BREVO_SENDER_EMAIL):
        print("[OTP EMAIL] Brevo not configured. OTP:", otp)
        return False

    try:
        payload = {
            "sender": {"email": BREVO_SENDER_EMAIL, "name": "MultiLingo"},
            "to": [{"email": to_email}],
            "subject": "Your MultiLingo verification code",
            "textContent": (
                f"Your MultiLingo verification code is: {otp}\n\n"
                "This code will expire in 10 minutes. If you did not request this, you can ignore this email."
            ),
        }
        headers = {
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=10
        )
        if resp.status_code in (200, 201, 202):
            print(f"[OTP EMAIL - BREVO] Sent OTP email to {to_email}")
            return True
        else:
            print("[OTP EMAIL - BREVO ERROR]", resp.status_code, resp.text)
            print(f"[OTP] Fallback OTP for {to_email}: {otp}")
            return False
    except Exception as e:
        print("[OTP EMAIL - BREVO ERROR]", e)
        print(f"[OTP] Fallback OTP for {to_email}: {otp}")
        return False


def send_contact_email(name: str, from_email: str, message_body: str) -> bool:
    """Send a contact form message to the site owner via Brevo.

    Returns True if sending looked successful, False otherwise.
    """
    if not (BREVO_API_KEY and BREVO_SENDER_EMAIL):
        print("[CONTACT EMAIL] Brevo not configured.")
        print(f"[CONTACT MESSAGE] From {name} <{from_email}>: {message_body}")
        return False

    try:
        subject_name = name or "MultiLingo contact form"
        payload = {
            "sender": {"email": BREVO_SENDER_EMAIL, "name": "MultiLingo"},
            "to": [{"email": BREVO_SENDER_EMAIL}],
            "subject": f"New message from {subject_name}",
            "textContent": f"Name: {name}\nEmail: {from_email}\n\nMessage:\n{message_body}",
            "replyTo": {"email": from_email or BREVO_SENDER_EMAIL},
        }
        headers = {
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=10
        )
        if resp.status_code in (200, 201, 202):
            print(f"[CONTACT EMAIL - BREVO] Sent contact email to {BREVO_SENDER_EMAIL}")
            return True
        else:
            print("[CONTACT EMAIL - BREVO ERROR]", resp.status_code, resp.text)
    except Exception as e:
        print("[CONTACT EMAIL - BREVO ERROR]", e)

    # Fallback: log message to server console
    print(f"[CONTACT MESSAGE FALLBACK] From {name} <{from_email}>: {message_body}")
    return False

def extract_gemini_text(result):
    candidates = result.get("candidates") or []
    if not candidates:
        return None

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    combined = "".join(text_parts).strip()
    return combined or None


def normalize_language_code(language_value, allow_auto=False):
    if not language_value:
        return "auto" if allow_auto else None

    normalized = str(language_value).strip().lower()
    if normalized in SUPPORTED_TEXT_LANGUAGES:
        return normalized
    if normalized in LANGUAGE_NAME_TO_CODE:
        return LANGUAGE_NAME_TO_CODE[normalized]
    if allow_auto and normalized in {"auto", "auto-detect", "detect language"}:
        return "auto"
    return None


def translate_text_via_google_web(message, target_language, source_language=None):
    target_code = normalize_language_code(target_language)
    source_code = normalize_language_code(source_language, allow_auto=True) or "auto"
    if not target_code:
        return None

    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": source_code,
                "tl": target_code,
                "dt": "t",
                "q": message,
            },
            timeout=(5, 20),
        )
        if response.status_code != 200:
            print("translate_text_via_google_web error:", response.status_code, response.text)
            return None

        payload = response.json()
        parts = payload[0] if isinstance(payload, list) and payload else []
        translated = "".join(
            part[0] for part in parts if isinstance(part, list) and part and part[0]
        ).strip()
        return translated or None
    except Exception as e:
        print("translate_text_via_google_web exception:", e)
        return None


def translate_text(message, target_language, source_language=None):
    headers = {"Content-Type": "application/json"}
    source_hint = (
        f"The source language is {source_language}. "
        if source_language and source_language.lower() not in {"auto", "auto-detect"}
        else "Detect the source language automatically. "
    )
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are a translator. "
                            f"{source_hint}"
                            f"Translate the text into {target_language}. "
                            "Return ONLY the translated text with no explanation, labels, or quotes.\n\n"
                            f"Text:\n{message}"
                        )
                    }
                ]
            }
        ]
    }
    try:
        response = build_retry_session().post(
            url,
            headers=headers,
            json=data,
            timeout=(5, 20),
        )
        result = response.json()
        translated = extract_gemini_text(result)
        if response.status_code == 200 and translated:
            return translated

        print("translate_text error:", response.status_code, result)
        return translate_text_via_google_web(message, target_language, source_language)
    except Exception as e:
        print("translate_text exception:", e)
        return translate_text_via_google_web(message, target_language, source_language)


def detect_language_heuristic(text):
    sample = (text or "").strip()
    if not sample:
        return None

    script_checks = [
        ("ar", lambda ch: "\u0600" <= ch <= "\u06FF"),
        ("ru", lambda ch: "\u0400" <= ch <= "\u04FF"),
        ("bn", lambda ch: "\u0980" <= ch <= "\u09FF"),
        ("hi", lambda ch: "\u0900" <= ch <= "\u097F"),
        ("or", lambda ch: "\u0B00" <= ch <= "\u0B7F"),
        ("ta", lambda ch: "\u0B80" <= ch <= "\u0BFF"),
        ("te", lambda ch: "\u0C00" <= ch <= "\u0C7F"),
        ("kn", lambda ch: "\u0C80" <= ch <= "\u0CFF"),
        ("zh", lambda ch: "\u4E00" <= ch <= "\u9FFF"),
        ("ja", lambda ch: ("\u3040" <= ch <= "\u309F") or ("\u30A0" <= ch <= "\u30FF")),
        ("ko", lambda ch: "\uAC00" <= ch <= "\uD7AF"),
    ]

    for code, matcher in script_checks:
        if any(matcher(ch) for ch in sample):
            return code

    lowered = f" {sample.lower()} "
    keyword_map = {
        "sv": [" och ", " det ", " att ", " inte ", " jag "],
        "nl": [" de ", " het ", " een ", " niet ", " ik "],
        "tr": [" ve ", " bir ", " bu ", " için ", " değil "],
        "pt": [" não ", " você ", " para ", " uma ", " com "],
        "es": [" que ", " los ", " las ", " una ", " estoy "],
        "fr": [" je ", " pas ", " une ", " est ", " les "],
        "de": [" und ", " ist ", " nicht ", " ich ", " das "],
        "it": [" che ", " non ", " una ", " per ", " sono "],
        "en": [" the ", " and ", " are ", " you ", " this "],
    }

    best_code = None
    best_score = 0
    for code, keywords in keyword_map.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score > best_score:
            best_code = code
            best_score = score

    return best_code if best_score > 0 else None


def detect_supported_language(text):
    heuristic_code = detect_language_heuristic(text)
    if heuristic_code in SUPPORTED_TEXT_LANGUAGES:
        return {
            "language_code": heuristic_code,
            "language_name": SUPPORTED_TEXT_LANGUAGES[heuristic_code],
            "provider": "heuristic",
        }

    headers = {"Content-Type": "application/json"}
    allowed_json = json.dumps(SUPPORTED_TEXT_LANGUAGES, ensure_ascii=False)
    prompt = (
        "Detect the language of the user's text.\n"
        "Choose exactly one language_code from this JSON object and use the matching language_name:\n"
        f"{allowed_json}\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        "{\"language_code\":\"en\",\"language_name\":\"English\"}\n"
        "If unsure, choose the closest supported language from the list.\n\n"
        "Text:\n"
        f"{text}"
    )
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, headers=headers, json=data, timeout=(3, 12))
    result = response.json()
    if response.status_code != 200 or "candidates" not in result:
        raise ValueError("Language detection failed")

    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw_text.startswith("```"):
        raw_text = "\n".join(
            line for line in raw_text.splitlines() if not line.strip().startswith("```")
        ).strip()

    parsed = json.loads(raw_text)
    language_code = (parsed.get("language_code") or "").strip().lower()
    language_name = (parsed.get("language_name") or "").strip()

    if language_code not in SUPPORTED_TEXT_LANGUAGES:
        raise ValueError("Unsupported language code returned")

    return {
        "language_code": language_code,
        "language_name": SUPPORTED_TEXT_LANGUAGES[language_code] or language_name,
        "provider": "gemini",
    }


def translate_with_variants(message, target_language, source_language=None):
    """Ask Gemini for neutral/formal/informal variants + synonyms.

    Returns a dict: {"neutral", "formal", "informal", "synonyms"[]}.
    Falls back to a simple translation if parsing fails.
    """
    headers = {"Content-Type": "application/json"}
    source_hint = (
        f"The source language is {source_language}.\n"
        if source_language and source_language.lower() not in {"auto", "auto-detect"}
        else "Detect the source language before translating.\n"
    )
    prompt = (
        "You are an expert translator and writing assistant.\n"
        f"{source_hint}"
        f"Translate the following text into {target_language}.\n"
        "Return three tone variants of the TRANSLATED text (neutral/formal/informal) in the target language,\n"
        "but generate SYNONYMS as alternative phrasings in the ORIGINAL language of the input (do NOT translate synonyms).\n"
        "Respond ONLY with valid JSON in this exact format (no markdown, no explanation):\n"
        "{\n"
        "  \"neutral\": \"translated text (target language)\",\n"
        "  \"formal\": \"translated text (target language, more formal)\",\n"
        "  \"informal\": \"translated text (target language, more casual)\",\n"
        "  \"synonyms\": [\"source-language paraphrase 1\", \"source-language paraphrase 2\", \"source-language paraphrase 3\"]\n"
        "}\n\n"
        "Text to translate:\n"
        f"{message}"
    )
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = build_retry_session().post(
            url,
            headers=headers,
            json=data,
            timeout=(5, 20),
        )
        result = response.json()
        if response.status_code != 200 or "candidates" not in result:
            raise ValueError("Bad response from Gemini")

        raw_text = extract_gemini_text(result)
        if not raw_text:
            raise ValueError("No text returned from Gemini")
        # Strip code fences if model wrapped JSON
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines() if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(cleaned)
        neutral = parsed.get("neutral") or translate_text(message, target_language, source_language)
        formal = parsed.get("formal") or neutral
        informal = parsed.get("informal") or neutral
        synonyms = parsed.get("synonyms") or []
        if not isinstance(synonyms, list):
            synonyms = []
        synonyms = [str(s).strip() for s in synonyms if str(s).strip()]

        return {
            "neutral": neutral,
            "formal": formal,
            "informal": informal,
            "synonyms": synonyms,
        }
    except Exception as e:
        print("translate_with_variants error:", e)
        # Fallback to a single translation
        neutral = translate_text(message, target_language, source_language)
        if not neutral:
            neutral = "Translation failed. Please try again."
        return {
            "neutral": neutral,
            "formal": neutral,
            "informal": neutral,
            "synonyms": [],
        }


@app.route("/detect-language", methods=["POST"])
def detect_language():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        return jsonify(detect_supported_language(text))
    except Exception as e:
        heuristic_code = detect_language_heuristic(text)
        if heuristic_code in SUPPORTED_TEXT_LANGUAGES:
            return jsonify(
                {
                    "language_code": heuristic_code,
                    "language_name": SUPPORTED_TEXT_LANGUAGES[heuristic_code],
                    "provider": "heuristic-fallback",
                }
            )
        return jsonify({"error": f"Language detection failed: {str(e)}"}), 500


@app.route("/contact", methods=["POST"])
def contact():
    """Receive contact form submissions and email them to the site owner."""
    data = request.json or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "name, email, and message are required"}), 400

    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    success = send_contact_email(name=name, from_email=email, message_body=message)
    if not success:
        return jsonify({"error": "Failed to send message"}), 500

    return jsonify({"message": "Message sent successfully"}), 200

@app.route("/translate", methods=["POST"])
def translate():
    data = request.json or {}
    message = data.get("message")
    source_language = data.get("source_language")
    target_language = data.get("target_language")

    if not message or not target_language:
        return jsonify({"error": "message and target_language are required"}), 400

    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    translated = translate_text(message, target_language, source_language)
    if not translated:
        return jsonify({"error": "Translation failed"}), 502

    # Save to DB, linked to user
    try:
        cursor.execute(
            """
            INSERT INTO chats (user_id, original_text, translated_text, target_language)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at, is_favorite
            """,
            (user_id, message, translated, target_language),
        )
        row = cursor.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("DB Insert Error:", e)
        return jsonify({"error": "Failed to save translation"}), 500

    return jsonify(
        {
            "id": row["id"],
            "original": message,
            "translated": translated,
            "target_language": target_language,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "is_favorite": row["is_favorite"],
        }
    )


@app.route("/translate/variants", methods=["POST"])
def translate_variants():
    """Translate and return multiple style variants plus synonyms.

    Also saves the neutral variant to chats history for this user.
    """
    data = request.json or {}
    message = data.get("message")
    source_language = data.get("source_language")
    target_language = data.get("target_language")

    if not message or not target_language:
        return jsonify({"error": "message and target_language are required"}), 400

    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    variants = translate_with_variants(message, target_language, source_language)
    neutral = variants.get("neutral")
    if not neutral or neutral == "Translation failed. Please try again.":
        return jsonify({"error": "Translation failed"}), 502

    # Save neutral translation to DB, linked to user
    try:
        cursor.execute(
            """
            INSERT INTO chats (user_id, original_text, translated_text, target_language)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at, is_favorite
            """,
            (user_id, message, neutral, target_language),
        )
        row = cursor.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("DB Insert Error (variants):", e)
        return jsonify({"error": "Failed to save translation"}), 500

    return jsonify(
        {
            "id": row["id"],
            "original": message,
            "translated": neutral,
            "target_language": target_language,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "is_favorite": row["is_favorite"],
            "variants": variants,
        }
    )


@app.route("/history", methods=["GET"])
def get_history():
    """Return recent translations for the current user."""
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    try:
        cursor.execute(
            """
            SELECT id, original_text, translated_text, target_language, is_favorite, created_at
            FROM chats
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        chat_rows = cursor.fetchall() or []
        chat_items = [
            {
                "id": r["id"],
                "history_key": f"chat:{r['id']}",
                "item_type": "translation",
                "original": r["original_text"],
                "translated": r["translated_text"],
                "target_language": r["target_language"],
                "is_favorite": r["is_favorite"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in chat_rows
        ]
        cursor.execute(
            """
            SELECT id, source_text, primary_emotion, confidence, emotions_json, provider, is_favorite, created_at
            FROM emotion_analyses
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        analysis_rows = cursor.fetchall() or []
        analysis_items = [
            {
                "id": r["id"],
                "history_key": f"analysis:{r['id']}",
                "item_type": "analysis",
                "original": r["source_text"],
                "translated": None,
                "target_language": None,
                "label": r["primary_emotion"],
                "score": float(r["confidence"]) if r["confidence"] is not None else 0.0,
                "emotions": r["emotions_json"] or [],
                "provider": r["provider"],
                "is_favorite": r["is_favorite"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in analysis_rows
        ]
        items = sorted(
            chat_items + analysis_items,
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )
        return jsonify({"items": items[:100]})
    except Exception as e:
        print("History query error:", e)
        return jsonify({"error": "Failed to load history"}), 500


@app.route("/history/<string:item_type>/<int:item_id>/favorite", methods=["POST"])
def toggle_favorite(item_type: str, item_id: int):
    """Mark/unmark a history item as favorite for the current user."""
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}
    is_favorite = bool(data.get("is_favorite", True))
    table_name = "chats" if item_type == "translation" else "emotion_analyses" if item_type == "analysis" else None
    if table_name is None:
        return jsonify({"error": "Invalid history item type"}), 400

    try:
        cursor.execute(
            f"SELECT id FROM {table_name} WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Not found"}), 404

        cursor.execute(
            f"UPDATE {table_name} SET is_favorite = %s WHERE id = %s",
            (is_favorite, item_id),
        )
        conn.commit()
        return jsonify({"id": item_id, "item_type": item_type, "is_favorite": is_favorite})
    except Exception as e:
        conn.rollback()
        print("Favorite toggle error:", e)
        return jsonify({"error": "Failed to update favorite"}), 500


@app.route("/history/<string:item_type>/<int:item_id>", methods=["DELETE"])
def delete_history_item(item_type: str, item_id: int):
    """Delete a single history item for the current user."""
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401
    table_name = "chats" if item_type == "translation" else "emotion_analyses" if item_type == "analysis" else None
    if table_name is None:
        return jsonify({"error": "Invalid history item type"}), 400

    try:
        cursor.execute(
            f"SELECT id FROM {table_name} WHERE id = %s AND user_id = %s",
            (item_id, user_id),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Not found"}), 404

        cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (item_id,))
        conn.commit()
        return jsonify({"id": item_id, "item_type": item_type, "deleted": True})
    except Exception as e:
        conn.rollback()
        print("Delete history error:", e)
        return jsonify({"error": "Failed to delete history item"}), 500


@app.route("/auth/google", methods=["POST"])
def auth_google():
    """Authenticate a user via Google ID token and issue our JWT."""
    data = request.json or {}
    token = data.get("id_token")

    if not token:
        return jsonify({"error": "Missing id_token"}), 400

    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Server is not configured for Google login"}), 500

    try:
        idinfo = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        if idinfo.get("iss") not in [
            "accounts.google.com",
            "https://accounts.google.com",
        ]:
            return jsonify({"error": "Invalid Google token issuer"}), 400

        email = (idinfo.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "No email in Google token"}), 400

        # Find or create user
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            random_password = secrets.token_urlsafe(32)
            password_hash = generate_password_hash(random_password)
            cursor.execute(
                "INSERT INTO users (email, password_hash, is_verified) VALUES (%s, %s, TRUE) RETURNING id",
                (email, password_hash),
            )
            user = cursor.fetchone()
            conn.commit()

        user_id = user["id"]

        access_token = create_access_token(user_id=user_id, email=email)

        return jsonify(
            {"message": "Login with Google successful", "token": access_token}
        ), 200
    except ValueError:
        return jsonify({"error": "Invalid Google token"}), 400
    except Exception as e:
        conn.rollback()
        print("Google auth error:", e)
        return jsonify({"error": "Google auth failed"}), 500


@app.route("/auth/signup", methods=["POST"])
def signup():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            return jsonify({"error": "User already exists. Please log in instead."}), 400

        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, is_verified",
            (email, password_hash),
        )
        new_user = cursor.fetchone()
        user_id = new_user["id"]

        # Generate and store OTP (expiry handled in DB using NOW())
        otp_plain = generate_otp()
        otp_hash = generate_password_hash(otp_plain)
        cursor.execute(
            """
            INSERT INTO otps (user_id, otp_hash, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '10 minutes')
            """,
            (user_id, otp_hash)
        )
        conn.commit()

        # Send OTP via email (with console fallback inside helper)
        send_otp_email(email, otp_plain)

        return jsonify({"message": "Signup successful. Please verify OTP.", "requires_otp": True}), 201
    except Exception as e:
        conn.rollback()
        print("Signup Error:", e)
        return jsonify({"error": "Signup failed"}), 500


@app.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "")

    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        user_id = user["id"]

        cursor.execute(
            """
            SELECT * FROM otps
            WHERE user_id = %s AND is_used = FALSE AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        otp_row = cursor.fetchone()

        if not otp_row:
            return jsonify({"error": "No valid OTP found. Please request a new one."}), 400

        if otp_row["attempt_count"] >= otp_row["max_attempts"]:
            return jsonify({"error": "Maximum OTP attempts exceeded"}), 400

        # Increment attempts first
        cursor.execute(
            "UPDATE otps SET attempt_count = attempt_count + 1 WHERE id = %s",
            (otp_row["id"],),
        )

        valid = check_password_hash(otp_row["otp_hash"], otp)

        if not valid:
            conn.commit()
            return jsonify({"error": "Invalid OTP"}), 400

        # Mark OTP used and verify user
        cursor.execute("UPDATE otps SET is_used = TRUE WHERE id = %s", (otp_row["id"],))
        cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
        conn.commit()

        # Issue JWT after successful verification
        access_token = create_access_token(user_id=user_id, email=email)

        return jsonify({
            "message": "OTP verified. You can now sign in.",
            "verified": True,
            "token": access_token,
        })
    except Exception as e:
        conn.rollback()
        print("Verify OTP Error:", e)
        return jsonify({"error": "OTP verification failed"}), 500


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "Invalid credentials"}), 400

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid credentials"}), 400

        # If user not verified, require OTP
        if not user["is_verified"]:
            otp_plain = generate_otp()
            otp_hash = generate_password_hash(otp_plain)

            cursor.execute(
                "INSERT INTO otps (user_id, otp_hash, expires_at) VALUES (%s, %s, NOW() + INTERVAL '10 minutes')",
                (user["id"], otp_hash),
            )
            cursor.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = %s",
                (user["id"],),
            )
            conn.commit()

            # Send OTP via email (with console fallback inside helper)
            send_otp_email(email, otp_plain)

            return jsonify({"message": "OTP required", "requires_otp": True}), 200

        # Already verified: no OTP needed - issue JWT
        cursor.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = %s",
            (user["id"],),
        )
        conn.commit()

        access_token = create_access_token(user_id=user["id"], email=email)

        return jsonify({
            "message": "Login successful",
            "requires_otp": False,
            "token": access_token,
        }), 200
    except Exception as e:
        conn.rollback()
        print("Login Error:", e)
        return jsonify({"error": "Login failed"}), 500


@app.route("/auth/logout", methods=["POST"])
def logout():
    """Simple logout endpoint.

    Since this app does not use server-side sessions or JWTs yet,
    logout is handled on the frontend (clearing local storage).
    This endpoint exists so the frontend can call it if needed and
    for future expansion (e.g., token blacklisting).
    """
    return jsonify({"message": "Logged out successfully"}), 200

# OCR Route
@app.route("/translate-image", methods=["POST"])
def translate_image():
    file = request.files.get("image")
    if not file:
        return {"error": "No image uploaded"}, 400

    image_bytes = file.read()
    if not image_bytes:
        return {"error": "Uploaded image is empty"}, 400

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as temp_file:
        temp_file.write(image_bytes)

    target_language = request.form.get("target_language", "hi")
    source_language = request.form.get("source_language", "auto")
    mime_type = getattr(file, "mimetype", None)

    ocr_lang = get_tesseract_lang_for_code(source_language)
    extracted_text = ocr_from_file(temp_path, lang=ocr_lang)
    if looks_like_garbled_ocr(extracted_text):
        gemini_ocr_text = extract_text_from_image_with_gemini(
            image_bytes=image_bytes,
            mime_type=mime_type,
            source_language=source_language,
        )
        if gemini_ocr_text:
            extracted_text = gemini_ocr_text

    translated_text = translate_text(extracted_text, target_language, source_language)

    return {
        "original": extracted_text,
        "translated": translated_text
    }

if __name__ == "__main__":
    app.run(debug=True)
