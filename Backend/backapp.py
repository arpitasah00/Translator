from flask import Flask, request, jsonify
import requests
import json
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random
import string
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import smtplib
from email.message import EmailMessage
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


app = Flask(__name__)

# Allow frontend origins (local dev + Vercel) to call this API.
allowed_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    # Vercel production domain
    "https://translator-phi-lemon.vercel.app",
    # Vercel preview for main branch
    "https://translator-git-main-arpitas-projects-1afa6e38.vercel.app",
]
CORS(app, resources={r"/*": {"origins": allowed_origins}})
load_dotenv()


# Gemini API Key
API_KEY = os.environ.get("API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# JWT settings
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM")
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES"))

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

# Email (SMTP) settings for sending OTPs
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

# PostgreSQL connection settings
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = int(os.environ.get("DB_PORT"))
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# Global connection & cursor; will be (re)initialized on demand
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)
cursor = conn.cursor(cursor_factory=RealDictCursor)


def get_db():
    """Ensure there is an open DB connection and cursor.

    Render can close idle connections, so we recreate them when needed.
    """
    global conn, cursor

    if conn is None or getattr(conn, "closed", 0) != 0:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )

    if cursor is None or getattr(cursor, "closed", False):
        cursor = conn.cursor(cursor_factory=RealDictCursor)

    return conn, cursor


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
    """Send OTP to user's email using basic SMTP.

    Returns True if sending looked successful, False otherwise.
    """
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_FROM):
        # Fallback: no SMTP configured
        print("[OTP EMAIL] SMTP not configured. OTP:", otp)
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = "Your MultiLingo verification code"
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.set_content(
            f"Your MultiLingo verification code is: {otp}\n\n"
            "This code will expire in 10 minutes. If you did not request this, you can ignore this email."
        )

        # Use a short timeout so the worker does not hang if SMTP is unreachable
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print(f"[OTP EMAIL] Sent OTP email to {to_email}")
        return True
    except Exception as e:
        print("[OTP EMAIL ERROR]", e)
        # Still log OTP to terminal as fallback
        print(f"[OTP] Fallback OTP for {to_email}: {otp}")
        return False


def send_contact_email(name: str, from_email: str, message_body: str) -> bool:
    """Send a contact form message to the site owner via SMTP.

    Returns True if sending looked successful, False otherwise.
    """
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_FROM):
        # Fallback: configuration missing, log message to server console
        print("[CONTACT EMAIL] SMTP not configured.")
        print(f"[CONTACT MESSAGE] From {name} <{from_email}>: {message_body}")
        return False

    try:
        msg = EmailMessage()
        subject_name = name or "MultiLingo contact form"
        msg["Subject"] = f"New message from {subject_name}"
        msg["From"] = SMTP_FROM
        # Send contact messages to the existing SMTP_FROM address
        msg["To"] = SMTP_FROM
        if from_email:
            msg["Reply-To"] = from_email

        msg.set_content(
            f"Name: {name}\nEmail: {from_email}\n\nMessage:\n{message_body}"
        )

        # Use a short timeout so the worker does not hang if SMTP is unreachable
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print(f"[CONTACT EMAIL] Sent contact email from {from_email} to {SMTP_FROM}")
        return True
    except Exception as e:
        print("[CONTACT EMAIL ERROR]", e)
        print(f"[CONTACT MESSAGE FALLBACK] From {name} <{from_email}>: {message_body}")
        return False

def translate_text(message, target_language):
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You are a translator. Detect the source language and translate into "
                            f"{target_language}. Return ONLY translated text (no quotes, no extra words):\n\n{message}"
                        )
                    }
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if response.status_code == 200 and "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "Translation Error"
    except Exception as e:
        return str(e)


def translate_with_variants(message, target_language):
    """Ask Gemini for neutral/formal/informal variants + synonyms.

    Returns a dict: {"neutral", "formal", "informal", "synonyms"[]}.
    Falls back to a simple translation if parsing fails.
    """
    headers = {"Content-Type": "application/json"}
    prompt = (
        "You are an expert translator and writing assistant.\n"
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
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if response.status_code != 200 or "candidates" not in result:
            raise ValueError("Bad response from Gemini")

        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        # Strip code fences if model wrapped JSON
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines() if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(cleaned)
        neutral = parsed.get("neutral") or translate_text(message, target_language)
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
        neutral = translate_text(message, target_language)
        return {
            "neutral": neutral,
            "formal": neutral,
            "informal": neutral,
            "synonyms": [],
        }


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
    conn, cursor = get_db()
    data = request.json or {}
    message = data.get("message")
    target_language = data.get("target_language")

    if not message or not target_language:
        return jsonify({"error": "message and target_language are required"}), 400

    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    translated = translate_text(message, target_language)

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
        try:
            conn.rollback()
        except Exception:
            pass
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
    conn, cursor = get_db()
    data = request.json or {}
    message = data.get("message")
    target_language = data.get("target_language")

    if not message or not target_language:
        return jsonify({"error": "message and target_language are required"}), 400

    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    variants = translate_with_variants(message, target_language)
    neutral = variants.get("neutral")

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
        try:
            conn.rollback()
        except Exception:
            pass
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
    conn, cursor = get_db()
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
        rows = cursor.fetchall() or []
        items = [
            {
                "id": r["id"],
                "original": r["original_text"],
                "translated": r["translated_text"],
                "target_language": r["target_language"],
                "is_favorite": r["is_favorite"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return jsonify({"items": items})
    except Exception as e:
        print("History query error:", e)
        return jsonify({"error": "Failed to load history"}), 500


@app.route("/history/<int:chat_id>/favorite", methods=["POST"])
def toggle_favorite(chat_id: int):
    """Mark/unmark a translation as favorite for the current user."""
    conn, cursor = get_db()
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    data = request.json or {}
    is_favorite = bool(data.get("is_favorite", True))

    try:
        # Ensure this chat belongs to the current user
        cursor.execute(
            "SELECT id FROM chats WHERE id = %s AND user_id = %s",
            (chat_id, user_id),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Not found"}), 404

        cursor.execute(
            "UPDATE chats SET is_favorite = %s WHERE id = %s",
            (is_favorite, chat_id),
        )
        conn.commit()
        return jsonify({"id": chat_id, "is_favorite": is_favorite})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("Favorite toggle error:", e)
        return jsonify({"error": "Failed to update favorite"}), 500


@app.route("/history/<int:chat_id>", methods=["DELETE"])
def delete_history_item(chat_id: int):
    """Delete a single history item (chat) for the current user."""
    conn, cursor = get_db()
    user_id = get_current_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Ensure this chat belongs to the user
        cursor.execute(
            "SELECT id FROM chats WHERE id = %s AND user_id = %s",
            (chat_id, user_id),
        )
        if cursor.fetchone() is None:
            return jsonify({"error": "Not found"}), 404

        cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
        conn.commit()
        return jsonify({"id": chat_id, "deleted": True})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("Delete history error:", e)
        return jsonify({"error": "Failed to delete history item"}), 500


@app.route("/auth/google", methods=["POST"])
def auth_google():
    """Authenticate a user via Google ID token and issue our JWT."""
    conn, cursor = get_db()
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
        try:
            conn.rollback()
        except Exception:
            pass
        print("Google auth error:", e)
        return jsonify({"error": "Google auth failed"}), 500


@app.route("/auth/signup", methods=["POST"])
def signup():
    conn, cursor = get_db()
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
        try:
            conn.rollback()
        except Exception:
            pass
        print("Signup Error:", e)
        return jsonify({"error": "Signup failed"}), 500


@app.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    conn, cursor = get_db()
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
        try:
            conn.rollback()
        except Exception:
            pass
        print("Verify OTP Error:", e)
        return jsonify({"error": "OTP verification failed"}), 500


@app.route("/auth/login", methods=["POST"])
def login():
    conn, cursor = get_db()
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
        try:
            conn.rollback()
        except Exception:
            pass
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

if __name__ == "__main__":
    app.run(debug=True)
