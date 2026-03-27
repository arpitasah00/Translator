/*CREATE TABLE chats (
    id SERIAL PRIMARY KEY,
    user_message TEXT,
    translated_message TEXT,
    language VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO chats (user_message, translated_message, language)
VALUES 
('Hello', 'Hola', 'Spanish'),
('How are you?', 'Comment ça va?', 'French'),
('Good morning', 'Buenos días', 'Spanish');

SELECT * FROM chats; */

CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    original_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
SELECT * FROM chats;

ALTER TABLE chats RENAME TO chats_old;

CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    original_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
SELECT * FROM chats;