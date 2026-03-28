from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import smtplib
from email.message import EmailMessage
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


app = Flask(__name__)
CORS(app)
load_dotenv()


# Gemini API Key
API_KEY = os.environ.get("API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# JWT settings
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "60"))

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

# Email (SMTP) settings for sending OTPs
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

# PostgreSQL connection
conn = psycopg2.connect(
    host="localhost",
    database="chat_translator_db",
    user="postgres",
    password="Arpi@123#"
)
cursor = conn.cursor(cursor_factory=RealDictCursor)


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

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
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

def translate_text(message, target_language):
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {"parts": [{"text": f"You are a translator. Detect the source language and translate into {target_language}. Return ONLY translated text:\n\n{message}"}]}
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

@app.route("/translate", methods=["POST"])
def translate():
    data = request.json
    message = data.get("message")
    target_language = data.get("target_language")
    
    translated = translate_text(message, target_language)
    
    # Save to DB
    try:
        cursor.execute(
            "INSERT INTO chats (original_text, translated_text, target_language) VALUES (%s, %s, %s)",
            (message, translated, target_language)
        )
        conn.commit()
    except Exception as e:
        print("DB Insert Error:", e)
    
    return jsonify({"original": message, "translated": translated})


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
            cursor.execute(
                "INSERT INTO users (email, is_verified) VALUES (%s, TRUE) RETURNING id",
                (email,),
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

if __name__ == "__main__":
    app.run(debug=True)
