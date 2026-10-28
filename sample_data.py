"""
Sample and demo dataset generator for AI Examination Seating Arrangement.
Populates realistic students, rooms with unavailable seats, and default CSP configuration.
"""

from typing import List, Optional
from csp.problem import Student, Room, CSPConfig
import database


SAMPLE_STUDENTS = [
    # Artificial Intelligence (6 students)
    Student(id="24CS01", name="Aarav Sharma", subject="Artificial Intelligence"),
    Student(id="24CS02", name="Ananya Iyer", subject="Artificial Intelligence"),
    Student(id="24CS03", name="Rohan Verma", subject="Artificial Intelligence"),
    Student(id="24CS04", name="Ishita Patel", subject="Artificial Intelligence"),
    Student(id="24CS05", name="Vikram Singh", subject="Artificial Intelligence"),
    Student(id="24CS06", name="Pooja Kulkarni", subject="Artificial Intelligence"),

    # Operating Systems (6 students)
    Student(id="24CS07", name="Rahul Nair", subject="Operating Systems"),
    Student(id="24CS08", name="Sneha Reddy", subject="Operating Systems"),
    Student(id="24CS09", name="Kunal Deshmukh", subject="Operating Systems"),
    Student(id="24CS10", name="Meera Sen", subject="Operating Systems"),
    Student(id="24CS11", name="Arjun Rao", subject="Operating Systems"),
    Student(id="24CS12", name="Kavya Gupta", subject="Operating Systems"),

    # Database Systems (6 students)
    Student(id="24CS13", name="Aditya Menon", subject="Database Systems"),
    Student(id="24CS14", name="Riya Joshi", subject="Database Systems"),
    Student(id="24CS15", name="Siddharth Roy", subject="Database Systems"),
    Student(id="24CS16", name="Tanvi Bhatia", subject="Database Systems"),
    Student(id="24CS17", name="Manish Chawla", subject="Database Systems"),
    Student(id="24CS18", name="Divya Pillai", subject="Database Systems"),

    # Computer Networks (6 students)
    Student(id="24CS19", name="Varun Kapoor", subject="Computer Networks"),
    Student(id="24CS20", name="Neha Saxena", subject="Computer Networks"),
    Student(id="24CS21", name="Pranav Hegde", subject="Computer Networks"),
    Student(id="24CS22", name="Shreya Das", subject="Computer Networks"),
    Student(id="24CS23", name="Karthik Subramanian", subject="Computer Networks"),
    Student(id="24CS24", name="Simran Kaur", subject="Computer Networks"),
]

SAMPLE_ROOMS = [
    Room(
        id="HALL_101",
        name="LH-101 (Main Auditorium)",
        rows=4,
        cols=4,
        # Broken seats or pillar obstruction at (0, 0) and (2, 2)
        unavailable_seats={(0, 0), (2, 2)}
    ),
    Room(
        id="HALL_102",
        name="LH-102 (Seminar Hall)",
        rows=4,
        cols=4,
        # Aisle / broken desk at (1, 3)
        unavailable_seats={(1, 3)}
    ),
]


def load_sample_dataset(db_path: Optional[str] = None) -> dict:
    """Wipes existing data and loads clean sample data into SQLite."""
    path = db_path or database.DEFAULT_DB_PATH
    database.init_db(path)
    database.clear_all_students(path)
    database.clear_all_rooms(path)
    database.clear_arrangements(path)

    for student in SAMPLE_STUDENTS:
        database.add_student(student, path)

    for room in SAMPLE_ROOMS:
        database.add_or_update_room(room, path)

    default_config = CSPConfig(
        prevent_same_subject_horizontal=True,
        prevent_same_subject_vertical=True,
        prevent_same_subject_diagonal=False,
        use_mrv=True,
        use_forward_checking=True,
        max_search_steps=50000,
        timeout_seconds=12.0
    )
    database.save_config(default_config, path)

    return {
        "students_count": len(SAMPLE_STUDENTS),
        "rooms_count": len(SAMPLE_ROOMS),
        "total_seats": sum(r.total_capacity for r in SAMPLE_ROOMS),
        "available_seats": sum(r.available_capacity for r in SAMPLE_ROOMS),
    }
