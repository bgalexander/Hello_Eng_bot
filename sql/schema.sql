
DROP TABLE IF EXISTS user_hidden_global_words CASCADE;
DROP TABLE IF EXISTS user_words CASCADE;
DROP TABLE IF EXISTS global_words CASCADE;
DROP TABLE IF EXISTS users CASCADE;


CREATE TABLE users (
id SERIAL PRIMARY KEY,
tg_id BIGINT UNIQUE NOT NULL,
username TEXT,
first_name TEXT,
created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE global_words (
id SERIAL PRIMARY KEY,
en TEXT NOT NULL,
ru TEXT NOT NULL,
category TEXT,
created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE UNIQUE INDEX uq_global_words_en_ru ON global_words (LOWER(en), LOWER(ru));


CREATE TABLE user_words (
id SERIAL PRIMARY KEY,
user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
en TEXT NOT NULL,
ru TEXT NOT NULL,
deleted BOOLEAN NOT NULL DEFAULT FALSE,
created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE INDEX ix_user_words_user_id ON user_words(user_id);


CREATE TABLE user_hidden_global_words (
id SERIAL PRIMARY KEY,
user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
word_id INTEGER NOT NULL REFERENCES global_words(id) ON DELETE CASCADE,
created_at TIMESTAMP NOT NULL DEFAULT NOW(),
UNIQUE (user_id, word_id)
);