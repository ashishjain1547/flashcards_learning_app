import os
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import json

# Configuration
with open('db_config.json') as f:
    db_cfg = json.load(f)
DB_HOST = db_cfg.get('DB_HOST', 'localhost')
DB_USER = db_cfg.get('DB_USER', 'your_mysql_user')
DB_PASSWORD = db_cfg.get('DB_PASSWORD', 'your_mysql_password')
DB_NAME = db_cfg.get('DB_NAME', 'flashcards_db')

app = Flask(__name__)
CORS(app)

# MySQL connection
conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# Create database and tables if not exist
def init_db():
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS flashcards (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        topic VARCHAR(100),
        subtopic VARCHAR(100),
        question TEXT,
        answer TEXT,
        image_base64 LONGTEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        flashcard_id INT,
        correct_count INT DEFAULT 0,
        incorrect_count INT DEFAULT 0,
        last_reviewed DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE
    )''')
    conn.commit()

init_db()

# User registration
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    password_hash = generate_password_hash(password)
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        conn.commit()
        return jsonify({'message': 'User registered successfully'})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 400

# User login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    cursor.execute("SELECT id, password_hash FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    if user and check_password_hash(user[1], password):
        return jsonify({'message': 'Login successful', 'user_id': user[0]})
    return jsonify({'error': 'Invalid credentials'}), 401

# CRUD for flashcards
@app.route('/api/flashcards', methods=['GET'])
def get_flashcards():
    user_id = request.args.get('user_id')
    cursor.execute("SELECT id, topic, subtopic, question, answer, image_base64 FROM flashcards WHERE user_id=%s", (user_id,))
    cards = [
        {'id': row[0], 'topic': row[1], 'subtopic': row[2], 'question': row[3], 'answer': row[4], 'image_base64': row[5]} for row in cursor.fetchall()
    ]
    return jsonify(cards)

@app.route('/api/flashcards', methods=['POST'])
def create_flashcard():
    data = request.json
    user_id = data.get('user_id')
    topic = data.get('topic')
    subtopic = data.get('subtopic')
    question = data.get('question')
    answer = data.get('answer')
    image_base64 = data.get('image_base64', None)
    cursor.execute(
        "INSERT INTO flashcards (user_id, topic, subtopic, question, answer, image_base64) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (user_id, topic, subtopic, question, answer, image_base64)
    )
    conn.commit()
    return jsonify({'message': 'Flashcard created'})

@app.route('/api/flashcards/<int:card_id>', methods=['PUT'])
def update_flashcard(card_id):
    data = request.json
    topic = data.get('topic')
    subtopic = data.get('subtopic')
    question = data.get('question')
    answer = data.get('answer')
    image_base64 = data.get('image_base64', None)
    cursor.execute(
        "UPDATE flashcards SET topic=%s, subtopic=%s, question=%s, answer=%s, image_base64=%s WHERE id=%s",
        (topic, subtopic, question, answer, image_base64, card_id)
    )
    conn.commit()
    return jsonify({'message': 'Flashcard updated'})

@app.route('/api/flashcards/<int:card_id>', methods=['DELETE'])
def delete_flashcard(card_id):
    cursor.execute("DELETE FROM flashcards WHERE id=%s", (card_id,))
    conn.commit()
    return jsonify({'message': 'Flashcard deleted'})

# Progress tracking
@app.route('/api/progress', methods=['GET'])
def get_progress():
    user_id = request.args.get('user_id')
    cursor.execute("SELECT flashcard_id, correct_count, incorrect_count, last_reviewed FROM progress WHERE user_id=%s", (user_id,))
    progress = [
        {'flashcard_id': row[0], 'correct_count': row[1], 'incorrect_count': row[2], 'last_reviewed': row[3]} for row in cursor.fetchall()
    ]
    return jsonify(progress)

@app.route('/api/progress', methods=['POST'])
def update_progress():
    data = request.json
    user_id = data.get('user_id')
    flashcard_id = data.get('flashcard_id')
    correct = data.get('correct')
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("SELECT id FROM progress WHERE user_id=%s AND flashcard_id=%s", (user_id, flashcard_id))
    row = cursor.fetchone()
    if row:
        if correct:
            cursor.execute("UPDATE progress SET correct_count = correct_count + 1, last_reviewed=%s WHERE id=%s", (now, row[0]))
        else:
            cursor.execute("UPDATE progress SET incorrect_count = incorrect_count + 1, last_reviewed=%s WHERE id=%s", (now, row[0]))
    else:
        cursor.execute(
            "INSERT INTO progress (user_id, flashcard_id, correct_count, incorrect_count, last_reviewed) VALUES (%s, %s, %s, %s, %s)",
            (user_id, flashcard_id, 1 if correct else 0, 0 if correct else 1, now)
        )
    conn.commit()
    return jsonify({'message': 'Progress updated'})

# Serve the frontend HTML (if hosted together)
@app.route('/')
def serve_frontend():
    return send_from_directory('.', 'flashcards.html')

if __name__ == '__main__':
    app.run(debug=True)
