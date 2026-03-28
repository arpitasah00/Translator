--Translation
CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    original_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
SELECT * FROM chats;

-- Users for login / signup
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- OTP codes and attempts
CREATE TABLE IF NOT EXISTS otps (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 5,
    is_used BOOLEAN DEFAULT FALSE
);
