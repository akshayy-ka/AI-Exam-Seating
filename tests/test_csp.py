"""
Unit and integration tests for AI Examination Seating Arrangement CSP Solver.

Tests all required scenarios:
  1. A simple valid seating arrangement.
  2. Same-subject students not sitting adjacent (horizontal and vertical).
  3. No duplicate seat assignments (Injective mapping).
  4. Unavailable seats never being assigned.
  5. Multiple rooms and room capacities.
  6. An impossible constraint configuration.
  7. Empty or invalid input.
"""

import unittest
from csp.problem import Student, Seat, Room, CSPConfig, CSPProblem
from csp.solver import CSPSolver
from csp.validator import CSPValidator


class TestExaminationSeatingCSP(unittest.TestCase):

    def test_1_simple_valid_seating_arrangement(self):
        """Test 1: Simple valid arrangement with 4 students in a 2x3 room."""
        students = [
            Student(id="S1", name="Alice", subject="Math"),
            Student(id="S2", name="Bob", subject="Physics"),
            Student(id="S3", name="Charlie", subject="Chemistry"),
            Student(id="S4", name="Diana", subject="Biology"),
        ]
        rooms = [
            Room(id="R101", name="Hall A", rows=2, cols=3)  # 6 seats
        ]
        config = CSPConfig(
            prevent_same_subject_horizontal=True,
            prevent_same_subject_vertical=True,
            prevent_same_subject_diagonal=False,
        )

        problem = CSPProblem(students, rooms, config)
        solver = CSPSolver(problem)
        result = solver.solve()

        self.assertTrue(result.success, f"Expected success, got: {result.reason}")
        self.assertEqual(len(result.assignment), 4)

        # Audit with CSPValidator
        valid, violations = CSPValidator.verify_solution(problem, result.assignment)
        self.assertTrue(valid, f"Violations found: {violations}")

    def test_2_same_subject_not_adjacent(self):
        """Test 2: Multiple students with the SAME subject must not sit adjacent."""
        # 4 students taking Math in a 2x4 room (8 seats).
        # In a 2x4 grid, a checkerboard placement allows up to 4 non-adjacent seats!
        students = [
            Student(id="M1", name="Math Student 1", subject="Math"),
            Student(id="M2", name="Math Student 2", subject="Math"),
            Student(id="M3", name="Math Student 3", subject="Math"),
            Student(id="M4", name="Math Student 4", subject="Math"),
            Student(id="P1", name="Physics Student 1", subject="Physics"),
            Student(id="P2", name="Physics Student 2", subject="Physics"),
        ]
        rooms = [
            Room(id="R101", name="Hall A", rows=2, cols=4)  # 8 seats
        ]
        config = CSPConfig(
            prevent_same_subject_horizontal=True,
            prevent_same_subject_vertical=True,
            prevent_same_subject_diagonal=False,
        )

        problem = CSPProblem(students, rooms, config)
        solver = CSPSolver(problem)
        result = solver.solve()

        self.assertTrue(result.success, f"Expected success, got: {result.reason}")
        self.assertEqual(len(result.assignment), 6)

        # Explicitly verify no two Math students are horizontally or vertically adjacent
        math_seats = [result.assignment[f"M{i}"] for i in range(1, 5)]
        for i in range(len(math_seats)):
            for j in range(i + 1, len(math_seats)):
                s1, s2 = math_seats[i], math_seats[j]
                dr = abs(s1.row - s2.row)
                dc = abs(s1.col - s2.col)
                self.assertFalse(dr == 0 and dc == 1, f"Horizontal conflict between {s1} and {s2}")
                self.assertFalse(dr == 1 and dc == 0, f"Vertical conflict between {s1} and {s2}")

        # Post-verification audit
        valid, violations = CSPValidator.verify_solution(problem, result.assignment)
        self.assertTrue(valid, f"Violations found: {violations}")

    def test_3_no_duplicate_seat_assignments(self):
        """Test 3: Every assigned seat must be unique (AllDifferent constraint)."""
        students = [
            Student(id=f"S{i}", name=f"Student {i}", subject=f"Sub_{i % 3}")
            for i in range(1, 9)
        ]
        rooms = [
            Room(id="R101", name="Hall A", rows=3, cols=3)  # 9 seats
        ]
        config = CSPConfig()
        problem = CSPProblem(students, rooms, config)
        solver = CSPSolver(problem)
        result = solver.solve()

        self.assertTrue(result.success)
        assigned_seat_ids = [seat.seat_id for seat in result.assignment.values()]
        # Check uniqueness: length of set must equal length of list
        self.assertEqual(len(assigned_seat_ids), len(set(assigned_seat_ids)))

    def test_4_unavailable_seats_never_assigned(self):
        """Test 4: Broken/unavailable seats must never be assigned to any student."""
        # A 2x2 room (4 seats) where seat (0, 0) and seat (1, 1) are marked unavailable.
        # Leaves exactly 2 available seats: (0, 1) and (1, 0).
        unavailable = {(0, 0), (1, 1)}
        rooms = [
            Room(id="R101", name="Lab 1", rows=2, cols=2, unavailable_seats=unavailable)
        ]
        students = [
            Student(id="S1", name="Alice", subject="Math"),
            Student(id="S2", name="Bob", subject="Physics"),
        ]
        config = CSPConfig()
        problem = CSPProblem(students, rooms, config)
        solver = CSPSolver(problem)
        result = solver.solve()

        self.assertTrue(result.success)
        for sid, seat in result.assignment.items():
            self.assertTrue(seat.is_available, f"Seat {seat} is marked unavailable!")
            self.assertNotIn((seat.row, seat.col), unavailable, f"Seat {seat} is in unavailable set!")

        # Verification audit
        valid, violations = CSPValidator.verify_solution(problem, result.assignment)
        self.assertTrue(valid)

    def test_5_multiple_rooms_and_room_capacities(self):
        """Test 5: Students distributed across multiple rooms respecting each room's capacity."""
        # 10 students, Room A capacity 6, Room B capacity 6
        students = [
            Student(id=f"S{i}", name=f"Student {i}", subject="Subject A" if i % 2 == 0 else "Subject B")
            for i in range(1, 11)
        ]
        rooms = [
            Room(id="Room_A", name="East Wing", rows=2, cols=3),  # 6 seats
            Room(id="Room_B", name="West Wing", rows=2, cols=3),  # 6 seats
        ]
        config = CSPConfig(
            prevent_same_subject_horizontal=True,
            prevent_same_subject_vertical=True,
        )
        problem = CSPProblem(students, rooms, config)
        solver = CSPSolver(problem)
        result = solver.solve()

        self.assertTrue(result.success)
        self.assertEqual(len(result.assignment), 10)

        # Count seats per room
        room_a_count = sum(1 for s in result.assignment.values() if s.room_id == "Room_A")
        room_b_count = sum(1 for s in result.assignment.values() if s.room_id == "Room_B")

        self.assertLessEqual(room_a_count, 6)
        self.assertLessEqual(room_b_count, 6)
        self.assertEqual(room_a_count + room_b_count, 10)

        # Verification audit
        valid, violations = CSPValidator.verify_solution(problem, result.assignment)
        self.assertTrue(valid)

    def test_6_impossible_constraint_configuration(self):
        """Test 6: Impossible configuration must fail cleanly without violating hard constraints."""
        # Scenario A: More students than total seats (Pigeonhole principle)
        students_overflow = [
            Student(id=f"S{i}", name=f"Student {i}", subject="CS")
            for i in range(1, 6)
        ]
        rooms_small = [
            Room(id="R1", name="Tiny Room", rows=2, cols=2)  # 4 seats
        ]
        problem_overflow = CSPProblem(students_overflow, rooms_small, CSPConfig())
        solver_overflow = CSPSolver(problem_overflow)
        result_overflow = solver_overflow.solve()

        self.assertFalse(result_overflow.success)
        self.assertIn("Insufficient total seats", result_overflow.reason)

        # Scenario B: Too many students of the SAME subject in a room where orthogonal
        # adjacency is forbidden. In a 2x2 room (4 seats), max independent set is 2.
        # If 3 students take 'Math', it is mathematically impossible.
        students_same_subject = [
            Student(id="M1", name="Math 1", subject="Math"),
            Student(id="M2", name="Math 2", subject="Math"),
            Student(id="M3", name="Math 3", subject="Math"),
        ]
        problem_same_subject = CSPProblem(
            students_same_subject,
            [Room(id="R1", name="Small Room", rows=2, cols=2)],
            CSPConfig(prevent_same_subject_horizontal=True, prevent_same_subject_vertical=True)
        )
        solver_same_subject = CSPSolver(problem_same_subject)
        result_same_subject = solver_same_subject.solve()

        self.assertFalse(result_same_subject.success)
        self.assertIn("theoretical maximum conflict-free capacity", result_same_subject.reason)

    def test_7_empty_or_invalid_input(self):
        """Test 7: Empty students or empty rooms must be caught by pre-validation."""
        # Empty students
        problem_empty_students = CSPProblem([], [Room(id="R1", name="Room", rows=2, cols=2)], CSPConfig())
        res1 = CSPSolver(problem_empty_students).solve()
        self.assertFalse(res1.success)
        self.assertEqual(res1.status, "FAILED_PREVALIDATION")
        self.assertIn("Student list is empty", res1.reason)

        # Empty rooms
        problem_empty_rooms = CSPProblem(
            [Student(id="S1", name="Alice", subject="Math")],
            [],
            CSPConfig()
        )
        res2 = CSPSolver(problem_empty_rooms).solve()
        self.assertFalse(res2.success)
        self.assertEqual(res2.status, "FAILED_PREVALIDATION")
        self.assertIn("No examination rooms configured", res2.reason)

        # Duplicate student IDs
        problem_dup_ids = CSPProblem(
            [
                Student(id="S1", name="Alice", subject="Math"),
                Student(id="S1", name="Bob", subject="Physics")
            ],
            [Room(id="R1", name="Room", rows=2, cols=2)],
            CSPConfig()
        )
        res3 = CSPSolver(problem_dup_ids).solve()
        self.assertFalse(res3.success)
        self.assertEqual(res3.status, "FAILED_PREVALIDATION")
        self.assertIn("Duplicate student IDs", res3.reason)

    def test_8_diagonal_adjacency_constraint(self):
        """Test 8: Verify diagonal adjacency restriction when enabled."""
        # In a 2x2 room, diagonal seats are (0,0) and (1,1).
        # If 2 students take Math and diagonal adjacency is prevented, they cannot sit at (0,0) and (1,1) either!
        students = [
            Student(id="M1", name="Math 1", subject="Math"),
            Student(id="M2", name="Math 2", subject="Math"),
        ]
        room = Room(id="R1", name="Small Room", rows=2, cols=2)
        # Enable horizontal, vertical, AND diagonal
        config = CSPConfig(
            prevent_same_subject_horizontal=True,
            prevent_same_subject_vertical=True,
            prevent_same_subject_diagonal=True
        )
        problem = CSPProblem(students, [room], config)
        solver = CSPSolver(problem)
        result = solver.solve()

        # In a 2x2 grid, all 4 seats are within horizontal, vertical, or diagonal distance 1 of each other!
        # Therefore, only 1 student of 'Math' can ever be placed in a 2x2 room if diagonal is forbidden.
        # With 2 students, it must fail without violating constraints.
        self.assertFalse(result.success)

    def test_9_mrv_and_forward_checking_heuristics(self):
        """Test 9: Verify MRV and Forward Checking search heuristics and prune counts."""
        # S_Restricted can only sit in Room 1 (domain size 1)
        # S_Free can sit in Room 1 or Room 2 (domain size 2)
        students = [
            Student(id="S_Free", name="Free Student", subject="Math"),
            Student(id="S_Restricted", name="Restricted Student", subject="Physics", eligible_rooms=["R1"]),
        ]
        rooms = [
            Room(id="R1", name="Hall 1", rows=1, cols=1),
            Room(id="R2", name="Hall 2", rows=1, cols=1),
        ]

        # Scenario A: MRV enabled -> S_Restricted is chosen first (Fail-First principle)
        # Solves without backtracks
        cfg_mrv = CSPConfig(use_mrv=True, use_forward_checking=True)
        prob_mrv = CSPProblem(students, rooms, cfg_mrv)
        res_mrv = CSPSolver(prob_mrv).solve()
        self.assertTrue(res_mrv.success)
        self.assertEqual(res_mrv.backtracks, 0)
        self.assertGreaterEqual(res_mrv.domain_prunes, 1)

        # Scenario B: MRV disabled, Forward Checking disabled -> S_Free is chosen first (arbitrary order),
        # takes R1, leaving S_Restricted with empty domain, requiring a backtrack!
        cfg_no_mrv = CSPConfig(use_mrv=False, use_forward_checking=False)
        prob_no_mrv = CSPProblem(students, rooms, cfg_no_mrv)
        res_no_mrv = CSPSolver(prob_no_mrv).solve()
        self.assertTrue(res_no_mrv.success)
        self.assertEqual(res_no_mrv.backtracks, 1)
        self.assertEqual(res_no_mrv.domain_prunes, 0)


if __name__ == "__main__":
    unittest.main()
