"""
API and End-to-End Tests for Flask Web Application.
"""

import unittest
import json
import os
import database
from app import app


class TestExaminationSeatingAPI(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_exam_seating.db"
        database.DEFAULT_DB_PATH = self.test_db
        database.init_db()
        database.clear_all_students()
        database.clear_all_rooms()
        database.clear_arrangements()
        self.client = app.test_client()

    def tearDown(self):
        database.clear_all_students()
        database.clear_all_rooms()
        database.clear_arrangements()
        database.DEFAULT_DB_PATH = "exam_seating.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass

    def test_index_page(self):
        """Verify index HTML route loads successfully."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AI Examination Seating Arrangement", res.data)

    def test_student_crud(self):
        """Test Student creation, retrieval, update, and deletion."""
        # 1. Create Student
        res = self.client.post("/api/students", json={
            "id": "CS101",
            "name": "Jane Doe",
            "subject": "Algorithms"
        })
        self.assertEqual(res.status_code, 201)

        # 2. Duplicate ID rejection
        res_dup = self.client.post("/api/students", json={
            "id": "CS101",
            "name": "Another Person",
            "subject": "Physics"
        })
        self.assertEqual(res_dup.status_code, 400)

        # 3. Retrieve Students
        res_list = self.client.get("/api/students")
        self.assertEqual(res_list.status_code, 200)
        data = res_list.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "CS101")

        # 4. Update Student
        res_update = self.client.put("/api/students/CS101", json={
            "name": "Jane Smith",
            "subject": "Advanced Algorithms"
        })
        self.assertEqual(res_update.status_code, 200)

        # 5. Delete Student
        res_del = self.client.delete("/api/students/CS101")
        self.assertEqual(res_del.status_code, 200)

        # Verify empty
        res_after = self.client.get("/api/students")
        self.assertEqual(len(res_after.get_json()), 0)

    def test_bulk_student_import(self):
        """Test importing students in CSV / multi-line format."""
        raw_text = """
        CS01, Alice Walker, Machine Learning
        CS02, Bob Dylan, Computer Networks
        # This is a comment
        CS03, Charlie Chaplin, Database Systems
        """
        res = self.client.post("/api/students/bulk", json={"text": raw_text})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["added_count"], 3)

    def test_room_management_and_seat_toggle(self):
        """Test room creation and toggling unavailable/broken seats."""
        # 1. Add Room
        res = self.client.post("/api/rooms", json={
            "id": "LH_01",
            "name": "Lecture Hall 1",
            "rows": 3,
            "cols": 3,
            "unavailable_seats": [[0, 0]]
        })
        self.assertEqual(res.status_code, 201)

        # Check capacities: 3x3 = 9 total, 1 unavailable => 8 available
        rooms = self.client.get("/api/rooms").get_json()
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["total_capacity"], 9)
        self.assertEqual(rooms[0]["available_capacity"], 8)

        # 2. Toggle seat (1, 1) to unavailable
        res_toggle = self.client.post("/api/rooms/LH_01/toggle-seat", json={"row": 1, "col": 1})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertEqual(res_toggle.get_json()["seat_status"], "unavailable")

        # Capacity should now be 7
        rooms_after = self.client.get("/api/rooms").get_json()
        self.assertEqual(rooms_after[0]["available_capacity"], 7)

        # Toggle seat (1, 1) back to available
        res_untoggle = self.client.post("/api/rooms/LH_01/toggle-seat", json={"row": 1, "col": 1})
        self.assertEqual(res_untoggle.status_code, 200)
        self.assertEqual(res_untoggle.get_json()["seat_status"], "available")

        # Capacity back to 8
        rooms_after2 = self.client.get("/api/rooms").get_json()
        self.assertEqual(rooms_after2[0]["available_capacity"], 8)

    def test_full_solver_pipeline(self):
        """Test end-to-end load sample data, generate arrangement, and export CSV."""
        # 1. Load sample data
        res_sample = self.client.post("/api/load-sample")
        self.assertEqual(res_sample.status_code, 200)
        self.assertTrue(res_sample.get_json()["success"])

        # 2. Generate arrangement
        res_gen = self.client.post("/api/generate", json={})
        self.assertEqual(res_gen.status_code, 200)
        gen_data = res_gen.get_json()
        self.assertTrue(gen_data["success"])
        self.assertEqual(len(gen_data["assignment"]), 24)

        # 3. Check stats reflect active arrangement
        res_stats = self.client.get("/api/stats")
        stats = res_stats.get_json()
        self.assertEqual(stats["assigned_students"], 24)
        self.assertTrue(stats["has_active_arrangement"])

        # 4. Export CSV
        res_csv = self.client.get("/api/export-csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, "text/csv")
        self.assertIn(b"Room ID,Seat,Row,Col,Student ID,Student Name,Subject", res_csv.data)

    def test_manual_reassign_seat_and_constraint_checking(self):
        """Test manual seat change API with strict constraint validation."""
        # 1. Setup simple room and 3 students
        self.client.post("/api/rooms", json={
            "id": "R1",
            "name": "Room 1",
            "rows": 2,
            "cols": 2,
            "unavailable_seats": [[1, 1]]  # (1,1) is unavailable/broken
        })
        self.client.post("/api/students", json={"id": "S1", "name": "Alice", "subject": "Math"})
        self.client.post("/api/students", json={"id": "S2", "name": "Bob", "subject": "Math"})
        self.client.post("/api/students", json={"id": "S3", "name": "Charlie", "subject": "Physics"})

        # Generate seating arrangement
        res_gen = self.client.post("/api/generate", json={})
        self.assertEqual(res_gen.status_code, 200)
        assignment = res_gen.get_json()["detailed_assignment"]

        # Notice S1 and S2 both take Math. In a 2x2 grid with (1,1) broken, seats are (0,0), (0,1), (1,0).
        # (0,0) is adjacent to (0,1) and (1,0).
        # If one Math student is at (0,0), the other Math student CANNOT be at (0,1) or (1,0)!
        # So S1 and S2 cannot sit adjacent.

        # Let's find S1's seat and S3's seat
        s1_seat = assignment["S1"]
        s2_seat = assignment["S2"]

        # 2. Try to move S1 to an unavailable/broken seat (1, 1) -> must fail with 400
        res_unavail = self.client.post("/api/reassign-seat", json={
            "student_id": "S1",
            "target_room_id": "R1",
            "target_row": 1,
            "target_col": 1
        })
        self.assertEqual(res_unavail.status_code, 400)
        self.assertIn("unavailable", res_unavail.get_json()["error"])

        # 3. Try to move or swap S1 directly adjacent to S2 (both taking Math)
        # Find which seat is adjacent to S2
        adj_row, adj_col = None, None
        for r, c in [(0, 1), (1, 0), (0, 0)]:
            dr = abs(r - s2_seat["row"])
            dc = abs(c - s2_seat["col"])
            if (dr == 0 and dc == 1) or (dr == 1 and dc == 0):
                adj_row, adj_col = r, c
                break

        res_adj = self.client.post("/api/reassign-seat", json={
            "student_id": "S1",
            "target_room_id": "R1",
            "target_row": adj_row,
            "target_col": adj_col
        })
        # If S1 moving to (adj_row, adj_col) places them adjacent to S2 who is taking Math,
        # it MUST be rejected with status code 422
        self.assertEqual(res_adj.status_code, 422)
        self.assertIn("Constraint violation", res_adj.get_json()["error"])

    def test_configuration_api(self):
        """Test retrieving and saving CSP configuration including MRV and FC flags."""
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        cfg = res.get_json()
        self.assertTrue(cfg["prevent_same_subject_horizontal"])
        self.assertTrue(cfg["use_mrv"])
        self.assertTrue(cfg["use_forward_checking"])

        # Update configuration
        res_post = self.client.post("/api/config", json={
            "prevent_same_subject_horizontal": True,
            "prevent_same_subject_vertical": False,
            "prevent_same_subject_diagonal": True,
            "use_mrv": False,
            "use_forward_checking": False,
            "max_search_steps": 25000,
            "timeout_seconds": 8.0,
        })
        self.assertEqual(res_post.status_code, 200)
        updated = res_post.get_json()["config"]
        self.assertFalse(updated["prevent_same_subject_vertical"])
        self.assertTrue(updated["prevent_same_subject_diagonal"])
        self.assertFalse(updated["use_mrv"])
        self.assertFalse(updated["use_forward_checking"])
        self.assertEqual(updated["max_search_steps"], 25000)


if __name__ == "__main__":
    unittest.main()
