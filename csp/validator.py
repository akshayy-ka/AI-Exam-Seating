"""
Validation module for AI-Based Examination Seating Arrangement.

Provides:
  1. Pre-search validation (checks for invalid inputs, duplicate IDs, capacity overload,
     and theoretical subject density limits before spending search time).
  2. Post-search verification (strictly checks every hard constraint on generated solutions).
"""

from typing import List, Dict, Set, Tuple, Optional
from collections import Counter
import math
from .problem import Student, Seat, Room, CSPProblem, CSPConfig


class ValidationError(Exception):
    """Raised when pre-conditions for seating arrangement are invalid."""
    pass


class CSPValidator:
    """Validates inputs before CSP search and verifies solutions after search."""

    @staticmethod
    def pre_validate(
        students: List[Student],
        rooms: List[Room],
        config: CSPConfig
    ) -> Tuple[bool, List[str]]:
        """
        Validates problem configuration before invoking CSP search.
        Returns (is_valid, list_of_error_reasons).
        """
        errors: List[str] = []

        # 1. Basic emptiness checks
        if not students:
            errors.append("Student list is empty. At least one student must be registered.")
        if not rooms:
            errors.append("No examination rooms configured. At least one room is required.")

        if errors:
            return False, errors

        # 2. Check duplicate student IDs
        student_ids = [s.id for s in students]
        duplicate_ids = [sid for sid, count in Counter(student_ids).items() if count > 1]
        if duplicate_ids:
            errors.append(
                f"Duplicate student IDs detected: {', '.join(duplicate_ids[:5])}"
                f"{' and more' if len(duplicate_ids) > 5 else ''}. Student IDs must be unique."
            )

        # 3. Check room dimensions and availability
        total_capacity = 0
        total_available_seats = 0
        room_ids = set()

        for r in rooms:
            if r.id in room_ids:
                errors.append(f"Duplicate room ID detected: '{r.id}'. Room IDs must be unique.")
            room_ids.add(r.id)

            if r.rows <= 0 or r.cols <= 0:
                errors.append(f"Room '{r.id}' has invalid grid dimensions: {r.rows}x{r.cols}. Must be >= 1x1.")
            
            avail_cap = r.available_capacity
            total_capacity += r.total_capacity
            total_available_seats += avail_cap

        if total_available_seats == 0 and not errors:
            errors.append("All configured rooms have 0 available seats (all marked unavailable or 0 capacity).")

        # 4. Global Capacity Check (Pigeonhole Principle)
        if len(students) > total_available_seats:
            errors.append(
                f"Insufficient total seats: {len(students)} students registered, "
                f"but only {total_available_seats} seats are available across all {len(rooms)} room(s). "
                f"Deficit of {len(students) - total_available_seats} seat(s)."
            )

        # 5. Subject Density and Theoretical Feasibility Check
        # When both horizontal and vertical adjacency are forbidden, seats form a bipartite grid.
        # The maximum independent set (seats with no adjacent neighbors) in any room of size R x C
        # cannot exceed ceil((R * C) / 2) if all seats are available, or fewer if seats are broken.
        subject_counts = Counter(s.subject for s in students)
        
        if config.prevent_same_subject_horizontal and config.prevent_same_subject_vertical:
            # Calculate theoretical maximum independent capacity across rooms for any single subject
            max_single_subject_cap = 0
            for r in rooms:
                # In a grid, the checkerboard coloring splits available seats into two color sets.
                # The max independent set cannot exceed the size of the larger color set.
                color_a = 0
                color_b = 0
                for row in range(r.rows):
                    for col in range(r.cols):
                        if (row, col) not in r.unavailable_seats:
                            if (row + col) % 2 == 0:
                                color_a += 1
                            else:
                                color_b += 1
                max_single_subject_cap += max(color_a, color_b)

            for subject, count in subject_counts.items():
                if count > max_single_subject_cap:
                    errors.append(
                        f"Subject '{subject}' has {count} students, but the theoretical maximum conflict-free "
                        f"capacity across all rooms for a single subject under orthogonal adjacency rules is "
                        f"{max_single_subject_cap}. Reduce students for this subject or add more rooms/rows/columns."
                    )

        # 6. Eligible rooms validation
        all_room_ids = {r.id for r in rooms}
        for s in students:
            if s.eligible_rooms is not None:
                invalid_rooms = set(s.eligible_rooms) - all_room_ids
                if invalid_rooms:
                    errors.append(
                        f"Student '{s.id}' is restricted to non-existent room(s): {', '.join(invalid_rooms)}."
                    )

        return len(errors) == 0, errors

    @staticmethod
    def verify_solution(
        problem: CSPProblem,
        assignment: Dict[str, Seat]
    ) -> Tuple[bool, List[str]]:
        """
        Thoroughly audits a completed seating assignment against ALL hard constraints.
        Returns (is_valid, list_of_violations).
        """
        violations: List[str] = []
        students_by_id = {s.id: s for s in problem.students}

        # 1. Every student must be assigned exactly one seat
        assigned_student_ids = set(assignment.keys())
        expected_student_ids = set(students_by_id.keys())

        unassigned = expected_student_ids - assigned_student_ids
        if unassigned:
            violations.append(
                f"{len(unassigned)} student(s) were not assigned a seat: {list(unassigned)[:5]}"
            )

        extra_assigned = assigned_student_ids - expected_student_ids
        if extra_assigned:
            violations.append(
                f"Unknown students found in assignment: {list(extra_assigned)}"
            )

        # 2. No duplicate seat assignments (Injective mapping)
        seat_usage: Dict[str, List[str]] = {}
        for student_id, seat in assignment.items():
            seat_usage.setdefault(seat.seat_id, []).append(student_id)

        for seat_id, sids in seat_usage.items():
            if len(sids) > 1:
                violations.append(
                    f"Duplicate seat occupancy at {seat_id}: assigned to multiple students {sids}."
                )

        # 3. Unavailable / Broken seats must never be assigned
        for student_id, seat in assignment.items():
            room = problem.rooms.get(seat.room_id)
            if not room:
                violations.append(f"Student {student_id} assigned to non-existent room {seat.room_id}.")
                continue
            if not seat.is_available or (seat.row, seat.col) in room.unavailable_seats:
                violations.append(
                    f"Student {student_id} assigned to unavailable/broken seat {seat.seat_id}."
                )

        # 4. Room capacity check
        room_counts: Dict[str, int] = {}
        for seat in assignment.values():
            room_counts[seat.room_id] = room_counts.get(seat.room_id, 0) + 1

        for room_id, count in room_counts.items():
            room = problem.rooms.get(room_id)
            if room and count > room.available_capacity:
                violations.append(
                    f"Room '{room_id}' capacity exceeded: {count} assigned > {room.available_capacity} available."
                )

        # 5. Adjacency rule validation for same-subject students
        # Group assigned students by room
        students_by_room: Dict[str, List[Tuple[Student, Seat]]] = {}
        for s_id, seat in assignment.items():
            st = students_by_id.get(s_id)
            if st:
                students_by_room.setdefault(seat.room_id, []).append((st, seat))

        for room_id, placed_list in students_by_room.items():
            n = len(placed_list)
            for i in range(n):
                for j in range(i + 1, n):
                    s1, seat1 = placed_list[i]
                    s2, seat2 = placed_list[j]

                    if s1.subject == s2.subject:
                        dr = abs(seat1.row - seat2.row)
                        dc = abs(seat1.col - seat2.col)

                        # Horizontal conflict
                        if problem.config.prevent_same_subject_horizontal and dr == 0 and dc == 1:
                            violations.append(
                                f"Horizontal adjacency conflict in {room_id}: {s1.name} ({s1.id}) "
                                f"and {s2.name} ({s2.id}) both taking '{s1.subject}' sit side-by-side "
                                f"at {seat1.label} and {seat2.label}."
                            )

                        # Vertical conflict
                        if problem.config.prevent_same_subject_vertical and dr == 1 and dc == 0:
                            violations.append(
                                f"Vertical adjacency conflict in {room_id}: {s1.name} ({s1.id}) "
                                f"and {s2.name} ({s2.id}) both taking '{s1.subject}' sit front-to-back "
                                f"at {seat1.label} and {seat2.label}."
                            )

                        # Diagonal conflict
                        if problem.config.prevent_same_subject_diagonal and dr == 1 and dc == 1:
                            violations.append(
                                f"Diagonal adjacency conflict in {room_id}: {s1.name} ({s1.id}) "
                                f"and {s2.name} ({s2.id}) both taking '{s1.subject}' sit diagonally "
                                f"at {seat1.label} and {seat2.label}."
                            )

        # 6. Room eligibility check
        for student_id, seat in assignment.items():
            st = students_by_id.get(student_id)
            if st and st.eligible_rooms is not None:
                if seat.room_id not in st.eligible_rooms:
                    violations.append(
                        f"Student {student_id} assigned to ineligible room {seat.room_id}. "
                        f"Eligible: {st.eligible_rooms}"
                    )

        return len(violations) == 0, violations
