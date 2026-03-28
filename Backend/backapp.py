from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv


app = Flask(__name__)
CORS(app)
load_dotenv()


# Gemini API Key
API_KEY = os.environ.get("API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# PostgreSQL connection
conn = psycopg2.connect(
    host="localhost",
    database="chat_translator_db",
    user="postgres",
    password="Arpi@123#"
)
cursor = conn.cursor(cursor_factory=RealDictCursor)

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

if __name__ == "__main__":
    app.run(debug=True)
