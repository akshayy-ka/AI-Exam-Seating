"""
Flask Application for AI-Based Examination Seating Arrangement Using CSP and Backtracking.

Provides REST API endpoints and web interface for:
  - Dashboard analytics
  - Managing students and examination rooms
  - Configuring CSP constraints and search parameters
  - Running CSP Backtracking Solver
  - Visualizing, filtering, printing, and exporting seating charts
"""

import io
import csv
from flask import Flask, render_template, request, jsonify, Response
from csp.problem import Student, Room, CSPConfig, CSPProblem
from csp.solver import CSPSolver
from csp.validator import CSPValidator
import database
import sample_data


app = Flask(__name__)
# Initialize the database schema on startup
database.init_db()


# ------------------------------------------------------------------------------
# Frontend Routes
# ------------------------------------------------------------------------------

@app.route("/")
def index():
    """Serves the main application dashboard."""
    return render_template("index.html")


# ------------------------------------------------------------------------------
# Dashboard & Analytics API
# ------------------------------------------------------------------------------

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Returns high-level statistics for the dashboard."""
    students = database.get_all_students()
    rooms = database.get_all_rooms()
    latest = database.get_latest_arrangement()

    total_seats = sum(r.total_capacity for r in rooms)
    available_seats = sum(r.available_capacity for r in rooms)
    unavailable_seats = total_seats - available_seats
    subjects = list(set(s.subject for s in students))

    assigned_count = 0
    if latest and latest.get("success"):
        assigned_count = len(latest.get("assignment", {}))

    return jsonify({
        "total_students": len(students),
        "total_rooms": len(rooms),
        "total_seats": total_seats,
        "available_seats": available_seats,
        "unavailable_seats": unavailable_seats,
        "total_subjects": len(subjects),
        "subjects": sorted(subjects),
        "assigned_students": assigned_count,
        "has_active_arrangement": latest is not None and latest.get("success", False),
        "latest_arrangement_status": latest.get("status") if latest else "NONE",
    })


# ------------------------------------------------------------------------------
# Student Management APIs
# ------------------------------------------------------------------------------

@app.route("/api/students", methods=["GET"])
def list_students():
    """Returns all students."""
    students = database.get_all_students()
    return jsonify([s.to_dict() for s in students])


@app.route("/api/students", methods=["POST"])
def create_student():
    """Adds a new student."""
    data = request.get_json() or {}
    sid = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    subject = str(data.get("subject", "")).strip()
    eligible = data.get("eligible_rooms")

    if not sid or not name or not subject:
        return jsonify({"error": "Student ID, Name, and Subject are all required."}), 400

    existing = [s for s in database.get_all_students() if s.id.lower() == sid.lower()]
    if existing:
        return jsonify({"error": f"Student with ID '{sid}' already exists."}), 400

    student = Student(id=sid, name=name, subject=subject, eligible_rooms=eligible)
    database.add_student(student)
    return jsonify({"success": True, "student": student.to_dict()}), 201


@app.route("/api/students/<student_id>", methods=["PUT"])
def edit_student(student_id: str):
    """Updates an existing student."""
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    subject = str(data.get("subject", "")).strip()
    eligible = data.get("eligible_rooms")

    if not name or not subject:
        return jsonify({"error": "Name and Subject are required."}), 400

    student = Student(id=student_id, name=name, subject=subject, eligible_rooms=eligible)
    updated = database.update_student(student)
    if not updated:
        return jsonify({"error": f"Student with ID '{student_id}' not found."}), 404

    return jsonify({"success": True, "student": student.to_dict()})


@app.route("/api/students/<student_id>", methods=["DELETE"])
def remove_student(student_id: str):
    """Deletes a student."""
    deleted = database.delete_student(student_id)
    if not deleted:
        return jsonify({"error": f"Student '{student_id}' not found."}), 404
    return jsonify({"success": True, "deleted_id": student_id})


@app.route("/api/students/bulk", methods=["POST"])
def bulk_add_students():
    """Bulk import students from CSV or multiline text (Format: ID, Name, Subject)."""
    data = request.get_json() or {}
    raw_text = data.get("text", "")
    lines = raw_text.strip().splitlines()

    added = []
    skipped = []
    existing_ids = {s.id.lower() for s in database.get_all_students()}

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            skipped.append(f"Line {line_num}: Expected 'ID, Name, Subject'")
            continue

        sid, name, subject = parts[0], parts[1], parts[2]
        if sid.lower() in existing_ids:
            skipped.append(f"Line {line_num}: Duplicate ID '{sid}'")
            continue

        student = Student(id=sid, name=name, subject=subject)
        database.add_student(student)
        existing_ids.add(sid.lower())
        added.append(student.to_dict())

    return jsonify({
        "success": True,
        "added_count": len(added),
        "skipped_count": len(skipped),
        "skipped_details": skipped,
    })


@app.route("/api/students", methods=["DELETE"])
def clear_students():
    """Deletes all students."""
    database.clear_all_students()
    return jsonify({"success": True, "message": "All students cleared."})


# ------------------------------------------------------------------------------
# Room Management APIs
# ------------------------------------------------------------------------------

@app.route("/api/rooms", methods=["GET"])
def list_rooms():
    """Returns all examination rooms."""
    rooms = database.get_all_rooms()
    return jsonify([r.to_dict() for r in rooms])


@app.route("/api/rooms", methods=["POST"])
def save_room():
    """Creates or updates an examination room."""
    data = request.get_json() or {}
    rid = str(data.get("id", "")).strip()
    name = str(data.get("name", rid)).strip()
    try:
        rows = int(data.get("rows", 0))
        cols = int(data.get("cols", 0))
    except ValueError:
        return jsonify({"error": "Rows and columns must be integers."}), 400

    if not rid:
        return jsonify({"error": "Room ID is required."}), 400
    if rows <= 0 or cols <= 0:
        return jsonify({"error": "Rows and columns must be greater than 0."}), 400
    if rows > 20 or cols > 20:
        return jsonify({"error": "Maximum room dimension is 20x20."}), 400

    unavail_raw = data.get("unavailable_seats", [])
    unavailable_seats = set()
    for item in unavail_raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            r, c = int(item[0]), int(item[1])
            if 0 <= r < rows and 0 <= c < cols:
                unavailable_seats.add((r, c))

    room = Room(id=rid, name=name, rows=rows, cols=cols, unavailable_seats=unavailable_seats)
    database.add_or_update_room(room)
    return jsonify({"success": True, "room": room.to_dict()}), 201


@app.route("/api/rooms/<room_id>", methods=["DELETE"])
def remove_room(room_id: str):
    """Deletes a room."""
    deleted = database.delete_room(room_id)
    if not deleted:
        return jsonify({"error": f"Room '{room_id}' not found."}), 404
    return jsonify({"success": True, "deleted_id": room_id})


@app.route("/api/rooms/<room_id>/toggle-seat", methods=["POST"])
def toggle_seat(room_id: str):
    """Toggles availability of a specific seat in a room."""
    data = request.get_json() or {}
    try:
        r = int(data.get("row"))
        c = int(data.get("col"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid 'row' and 'col' are required."}), 400

    rooms = {room.id: room for room in database.get_all_rooms()}
    room = rooms.get(room_id)
    if not room:
        return jsonify({"error": f"Room '{room_id}' not found."}), 404

    if not (0 <= r < room.rows and 0 <= c < room.cols):
        return jsonify({"error": "Seat coordinates out of bounds."}), 400

    coord = (r, c)
    if coord in room.unavailable_seats:
        room.unavailable_seats.remove(coord)
        new_status = "available"
    else:
        room.unavailable_seats.add(coord)
        new_status = "unavailable"

    database.add_or_update_room(room)
    return jsonify({
        "success": True,
        "seat_status": new_status,
        "room": room.to_dict()
    })


@app.route("/api/rooms", methods=["DELETE"])
def clear_rooms():
    """Deletes all rooms."""
    database.clear_all_rooms()
    return jsonify({"success": True, "message": "All rooms cleared."})


# ------------------------------------------------------------------------------
# Constraints & Settings APIs
# ------------------------------------------------------------------------------

@app.route("/api/config", methods=["GET"])
def get_configuration():
    """Returns current CSP constraints and search limits."""
    config = database.get_config()
    return jsonify(config.to_dict())


@app.route("/api/config", methods=["POST"])
def update_configuration():
    """Updates CSP constraints and parameters."""
    data = request.get_json() or {}
    config = CSPConfig.from_dict(data)
    database.save_config(config)
    return jsonify({"success": True, "config": config.to_dict()})


# ------------------------------------------------------------------------------
# Seating Arrangement Generation (CSP Backtracking Engine)
# ------------------------------------------------------------------------------

@app.route("/api/generate", methods=["POST"])
def generate_arrangement():
    """Runs the CSP Backtracking Solver to produce a conflict-free seating chart."""
    students = database.get_all_students()
    rooms = database.get_all_rooms()
    config = database.get_config()

    # Allow one-off override from request body if passed
    req_data = request.get_json()
    if req_data and "config" in req_data:
        config = CSPConfig.from_dict(req_data["config"])

    problem = CSPProblem(students=students, rooms=rooms, config=config)
    solver = CSPSolver(problem)
    result = solver.solve()

    result_dict = result.to_dict()

    # Attach student details to the assignment for rich rendering
    student_map = {s.id: s.to_dict() for s in students}
    room_map = {r.id: r.to_dict() for r in rooms}

    detailed_assignment = {}
    for sid, seat_info in result_dict.get("assignment", {}).items():
        st = student_map.get(sid, {})
        detailed_assignment[sid] = {
            "student_id": sid,
            "student_name": st.get("name", sid),
            "subject": st.get("subject", "N/A"),
            "room_id": seat_info["room_id"],
            "row": seat_info["row"],
            "col": seat_info["col"],
            "label": seat_info["label"],
            "seat_id": seat_info["seat_id"],
        }
    result_dict["detailed_assignment"] = detailed_assignment
    result_dict["rooms"] = [r.to_dict() for r in rooms]

    # Save to history if successful or to retain state
    database.save_latest_arrangement(result_dict)

    status_code = 200 if result.success else 422
    return jsonify(result_dict), status_code


@app.route("/api/latest-arrangement", methods=["GET"])
def get_latest():
    """Fetches the latest generated arrangement from database."""
    latest = database.get_latest_arrangement()
    if not latest:
        return jsonify({"has_arrangement": False}), 200
    return jsonify({"has_arrangement": True, "data": latest}), 200


@app.route("/api/reassign-seat", methods=["POST"])
def reassign_seat():
    """
    Manually reassigns a student to a different seat (or swaps seats with another student),
    while strictly checking all CSP constraints.
    """
    data = request.get_json() or {}
    student_id = str(data.get("student_id", "")).strip()
    target_room_id = str(data.get("target_room_id", "")).strip()
    try:
        target_row = int(data.get("target_row"))
        target_col = int(data.get("target_col"))
    except (TypeError, ValueError):
        return jsonify({"error": "Target row and column must be valid integers."}), 400

    latest = database.get_latest_arrangement()
    if not latest or not latest.get("success"):
        return jsonify({"error": "No active seating arrangement exists. Generate seating first."}), 400

    current_assignment_dict = latest.get("assignment", {})
    if student_id not in current_assignment_dict:
        return jsonify({"error": f"Student '{student_id}' has not been seated in the current arrangement."}), 400

    students = database.get_all_students()
    rooms = database.get_all_rooms()
    config = database.get_config()
    problem = CSPProblem(students=students, rooms=rooms, config=config)

    target_room = problem.rooms.get(target_room_id)
    if not target_room:
        return jsonify({"error": f"Target room '{target_room_id}' does not exist."}), 404

    if not (0 <= target_row < target_room.rows and 0 <= target_col < target_room.cols):
        return jsonify({"error": "Target seat coordinates are out of bounds."}), 400

    if (target_row, target_col) in target_room.unavailable_seats:
        return jsonify({"error": f"Seat R{target_row+1}C{target_col+1} in {target_room.name} is marked unavailable/broken."}), 400

    from csp.problem import Seat

    target_seat = Seat(room_id=target_room_id, row=target_row, col=target_col, is_available=True)
    current_seat_info = current_assignment_dict[student_id]
    current_seat = Seat(
        room_id=current_seat_info["room_id"],
        row=current_seat_info["row"],
        col=current_seat_info["col"],
        is_available=True
    )

    if current_seat == target_seat:
        return jsonify({"error": "Student is already assigned to this seat."}), 400

    # Build candidate assignment dictionary
    candidate_assignment: dict = {}
    occupant_sid = None

    for sid, sinfo in current_assignment_dict.items():
        if sinfo["room_id"] == target_room_id and sinfo["row"] == target_row and sinfo["col"] == target_col:
            occupant_sid = sid
        candidate_assignment[sid] = Seat(
            room_id=sinfo["room_id"],
            row=sinfo["row"],
            col=sinfo["col"],
            is_available=True
        )

    # Perform tentative swap or move
    if occupant_sid:
        candidate_assignment[student_id] = target_seat
        candidate_assignment[occupant_sid] = current_seat
        action_desc = f"Swapped seats between {student_id} ({target_seat.label}) and {occupant_sid} ({current_seat.label})"
    else:
        candidate_assignment[student_id] = target_seat
        action_desc = f"Moved student {student_id} to {target_room.name} ({target_seat.label})"

    # Rigorous CSP verification: check ALL hard constraints
    is_valid, violations = CSPValidator.verify_solution(problem, candidate_assignment)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": "Constraint violation: " + "; ".join(violations),
            "violations": violations
        }), 422

    # If valid, serialize and persist the updated arrangement
    student_map = {s.id: s.to_dict() for s in students}
    detailed_assignment = {}
    serialized_assignment = {}

    for sid, seat in candidate_assignment.items():
        st = student_map.get(sid, {})
        seat_dict = {
            "room_id": seat.room_id,
            "row": seat.row,
            "col": seat.col,
            "label": seat.label,
            "seat_id": seat.seat_id
        }
        serialized_assignment[sid] = seat_dict
        detailed_assignment[sid] = {
            "student_id": sid,
            "student_name": st.get("name", sid),
            "subject": st.get("subject", "N/A"),
            "room_id": seat.room_id,
            "row": seat.row,
            "col": seat.col,
            "label": seat.label,
            "seat_id": seat.seat_id
        }

    latest["assignment"] = serialized_assignment
    latest["detailed_assignment"] = detailed_assignment
    latest["reason"] = f"Manual adjustment verified: {action_desc}."
    database.save_latest_arrangement(latest)

    return jsonify({
        "success": True,
        "message": action_desc,
        "arrangement": latest
    }), 200


# ------------------------------------------------------------------------------
# Export Seating Chart (CSV)
# ------------------------------------------------------------------------------

@app.route("/api/export-csv", methods=["GET"])
def export_csv():
    """Generates a downloadable CSV seating chart."""
    latest = database.get_latest_arrangement()
    if not latest or not latest.get("success"):
        return jsonify({"error": "No valid seating arrangement exists to export."}), 400

    assignment = latest.get("detailed_assignment", {})
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Room ID", "Seat", "Row", "Col", "Student ID", "Student Name", "Subject"])

    # Sort rows by room, row, col for clean printable/importable records
    sorted_items = sorted(
        assignment.values(),
        key=lambda x: (x.get("room_id", ""), x.get("row", 0), x.get("col", 0))
    )

    for item in sorted_items:
        writer.writerow([
            item.get("room_id"),
            item.get("label"),
            item.get("row", 0) + 1,
            item.get("col", 0) + 1,
            item.get("student_id"),
            item.get("student_name"),
            item.get("subject"),
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=exam_seating_arrangement.csv"}
    )


# ------------------------------------------------------------------------------
# Sample Data & Reset APIs
# ------------------------------------------------------------------------------

@app.route("/api/load-sample", methods=["POST"])
def load_sample():
    """Loads realistic sample college data for instant demonstration."""
    summary = sample_data.load_sample_dataset()
    return jsonify({
        "success": True,
        "message": "Sample dataset loaded successfully.",
        "summary": summary
    })


@app.route("/api/reset-all", methods=["POST"])
def reset_all():
    """Wipes all data from database."""
    database.clear_all_students()
    database.clear_all_rooms()
    database.clear_arrangements()
    return jsonify({"success": True, "message": "All data wiped successfully."})


if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host=host, port=port, debug=True)
