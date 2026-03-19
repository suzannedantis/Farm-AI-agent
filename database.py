import sqlite3
import hashlib
import secrets
from datetime import datetime

DB_PATH = "farming_memory.db"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            farmer_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id TEXT NOT NULL,
            location TEXT,
            crop_type TEXT,
            query TEXT,
            disease_class TEXT,
            confidence TEXT,
            advice TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def register_farmer(farmer_id: str, password: str):
    farmer_id = farmer_id.strip().lower()
    if not farmer_id or not password:
        return False, "Username and password cannot be empty."
    if len(farmer_id) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT farmer_id FROM farmers WHERE farmer_id = ?", (farmer_id,))
    if c.fetchone():
        conn.close()
        return False, "Username already taken."
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    c.execute(
        "INSERT INTO farmers (farmer_id, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
        (farmer_id, pw_hash, salt, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return True, "Account created successfully!"


def verify_farmer(farmer_id: str, password: str):
    farmer_id = farmer_id.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash, salt FROM farmers WHERE farmer_id = ?", (farmer_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, "Username not found."
    stored_hash, salt = row
    if _hash_password(password, salt) == stored_hash:
        return True, "Login successful."
    return False, "Incorrect password."


def farmer_exists(farmer_id: str) -> bool:
    farmer_id = farmer_id.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM farmers WHERE farmer_id = ?", (farmer_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


def save_session(farmer_id: str, location: str, crop_type: str, query: str,
                 disease_class: str, confidence: str, advice: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO sessions (farmer_id, location, crop_type, query, disease_class, confidence, advice, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (farmer_id, location, crop_type, query, disease_class, confidence, advice,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_past_sessions(farmer_id: str, limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT location, crop_type, query, disease_class, confidence, advice, timestamp
        FROM sessions WHERE farmer_id = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (farmer_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_recurring_issues(farmer_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT disease_class, COUNT(*) as count, MAX(timestamp) as last_seen
        FROM sessions WHERE farmer_id = ?
        GROUP BY disease_class HAVING count > 1
        ORDER BY count DESC
    """, (farmer_id,))
    rows = c.fetchall()
    conn.close()
    return rows