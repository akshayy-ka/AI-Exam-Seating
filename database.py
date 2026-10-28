"""
Database storage layer using SQLite for AI-Based Examination Seating Arrangement.
Stores students, examination rooms, system constraints, and generated seating charts.
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from csp.problem import Student, Room, CSPConfig


DEFAULT_DB_PATH = "exam_seating.db"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a connection to SQLite database and enables row factory."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Creates the SQLite database schema if not already present."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        
        # Students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                eligible_rooms TEXT
            )
        """)

        # Rooms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rows INTEGER NOT NULL,
                cols INTEGER NOT NULL,
                unavailable_seats TEXT NOT NULL DEFAULT '[]'
            )
        """)

        # Settings table for constraints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Seating arrangement history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arrangements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
        """)

        conn.commit()
    finally:
        conn.close()


# ==============================================================================
# Student Helpers
# ==============================================================================

def get_all_students(db_path: Optional[str] = None) -> List[Student]:
    """Retrieves all students from the database."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, subject, eligible_rooms FROM students ORDER BY id ASC")
        rows = cursor.fetchall()
        students = []
        for r in rows:
            elig = json.loads(r["eligible_rooms"]) if r["eligible_rooms"] else None
            students.append(Student(id=r["id"], name=r["name"], subject=r["subject"], eligible_rooms=elig))
        return students
    finally:
        conn.close()


def add_student(student: Student, db_path: Optional[str] = None) -> None:
    """Adds a new student."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        elig = json.dumps(student.eligible_rooms) if student.eligible_rooms else None
        cursor.execute(
            "INSERT INTO students (id, name, subject, eligible_rooms) VALUES (?, ?, ?, ?)",
            (student.id, student.name, student.subject, elig)
        )
        conn.commit()
    finally:
        conn.close()


def update_student(student: Student, db_path: Optional[str] = None) -> bool:
    """Updates an existing student."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        elig = json.dumps(student.eligible_rooms) if student.eligible_rooms else None
        cursor.execute(
            "UPDATE students SET name = ?, subject = ?, eligible_rooms = ? WHERE id = ?",
            (student.name, student.subject, elig, student.id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_student(student_id: str, db_path: Optional[str] = None) -> bool:
    """Deletes a student by ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def clear_all_students(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students")
        conn.commit()
    finally:
        conn.close()


# ==============================================================================
# Room Helpers
# ==============================================================================

def get_all_rooms(db_path: Optional[str] = None) -> List[Room]:
    """Retrieves all rooms from the database."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, rows, cols, unavailable_seats FROM rooms ORDER BY id ASC")
        rows = cursor.fetchall()
        rooms = []
        for r in rows:
            unavail_list = json.loads(r["unavailable_seats"]) if r["unavailable_seats"] else []
            unavail_set = set(tuple(p) for p in unavail_list)
            rooms.append(Room(
                id=r["id"],
                name=r["name"],
                rows=r["rows"],
                cols=r["cols"],
                unavailable_seats=unavail_set
            ))
        return rooms
    finally:
        conn.close()


def add_or_update_room(room: Room, db_path: Optional[str] = None) -> None:
    """Upserts an examination room."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        unavail = json.dumps([list(p) for p in sorted(room.unavailable_seats)])
        cursor.execute("""
            INSERT INTO rooms (id, name, rows, cols, unavailable_seats)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                rows = excluded.rows,
                cols = excluded.cols,
                unavailable_seats = excluded.unavailable_seats
        """, (room.id, room.name, room.rows, room.cols, unavail))
        conn.commit()
    finally:
        conn.close()


def delete_room(room_id: str, db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def clear_all_rooms(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rooms")
        conn.commit()
    finally:
        conn.close()


# ==============================================================================
# Configuration Helpers
# ==============================================================================

def get_config(db_path: Optional[str] = None) -> CSPConfig:
    """Loads CSP configuration from settings table, falling back to defaults."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'csp_config'")
        row = cursor.fetchone()
        if row:
            try:
                data = json.loads(row["value"])
                return CSPConfig.from_dict(data)
            except Exception:
                pass
        return CSPConfig()
    finally:
        conn.close()


def save_config(config: CSPConfig, db_path: Optional[str] = None) -> None:
    """Persists CSP configuration."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        val = json.dumps(config.to_dict())
        cursor.execute("""
            INSERT INTO settings (key, value) VALUES ('csp_config', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (val,))
        conn.commit()
    finally:
        conn.close()


# ==============================================================================
# Arrangement History Helpers
# ==============================================================================

def save_latest_arrangement(result_dict: dict, db_path: Optional[str] = None) -> int:
    """Saves the latest generated arrangement."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        status = result_dict.get("status", "UNKNOWN")
        cursor.execute(
            "INSERT INTO arrangements (status, result_json) VALUES (?, ?)",
            (status, json.dumps(result_dict))
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_latest_arrangement(db_path: Optional[str] = None) -> Optional[dict]:
    """Retrieves the most recent arrangement result."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT result_json FROM arrangements ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return json.loads(row["result_json"])
        return None
    finally:
        conn.close()


def clear_arrangements(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM arrangements")
        conn.commit()
    finally:
        conn.close()
