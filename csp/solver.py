"""
CSP Backtracking Solver for AI-Based Examination Seating Arrangement.

Theoretical Foundation:
----------------------
A Constraint Satisfaction Problem (CSP) consists of:
  - X: Set of variables {Student_1, Student_2, ..., Student_n}
  - D: Set of domains {Domain_1, Domain_2, ..., Domain_n}, where each domain is a set of legal seats
  - C: Set of constraints (AllDifferent seats, room capacity, same-subject adjacency restrictions)

Algorithms and Heuristics:
-------------------------
1. Backtracking Search: Depth-First Search (DFS) that assigns one variable at a time,
   checks consistency with existing assignments, and backtracks upon reaching dead ends.
2. MRV Heuristic (Minimum Remaining Values / Most Constrained Variable):
   Selects the unassigned student with the fewest legal seats left in their domain.
   Prunes dead ends as early as possible (fail-first principle).
3. Degree / Subject Frequency Heuristic (Tie-Breaker):
   Breaks ties among MRV candidates by picking the student from the largest subject group.
4. Forward Checking (FC):
   Whenever student S is assigned to seat (r, c), forward checking immediately prunes:
     a) That seat from ALL other students' domains (AllDifferent constraint).
     b) All adjacent seats in that room from students taking the SAME subject.
   If any unassigned student's domain becomes empty (Domain Wipeout), the algorithm
   prunes the search branch immediately without descending further.
5. Resource Limit & Graceful Degradation:
   Stops safely if max search steps or time limit is reached, giving a clear diagnostic
   explanation rather than freezing the application or claiming impossibility.
"""

import time
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter
from dataclasses import dataclass, field
from .problem import Student, Seat, Room, CSPProblem, CSPConfig
from .validator import CSPValidator


@dataclass
class SolverResult:
    """Detailed result produced by the CSP solver."""
    success: bool
    status: str  # "SUCCESS", "FAILED_PREVALIDATION", "FAILED_NO_SOLUTION", "FAILED_TIMEOUT", "FAILED_STEP_LIMIT"
    assignment: Dict[str, Seat] = field(default_factory=dict)
    steps: int = 0
    backtracks: int = 0
    domain_prunes: int = 0
    time_taken_ms: float = 0.0
    reason: str = ""
    violations: List[str] = field(default_factory=list)
    diagnostics: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status,
            "assignment": {sid: s.to_dict() if hasattr(s, "to_dict") else {
                "seat_id": s.seat_id,
                "room_id": s.room_id,
                "row": s.row,
                "col": s.col,
                "label": s.label
            } for sid, s in self.assignment.items()},
            "steps": self.steps,
            "backtracks": self.backtracks,
            "domain_prunes": self.domain_prunes,
            "time_taken_ms": round(self.time_taken_ms, 2),
            "reason": self.reason,
            "violations": self.violations,
            "diagnostics": self.diagnostics,
        }


class CSPSolver:
    """
    Executes recursive Backtracking Search with MRV and Forward Checking.
    """

    def __init__(self, problem: CSPProblem):
        self.problem = problem
        self.config = problem.config

        # Metrics for analysis and viva demonstration
        self.steps = 0
        self.backtracks = 0
        self.domain_prunes = 0
        self.start_time = 0.0
        self.halted_reason = ""
        self.is_halted = False

        # Fast lookup mapping: student_id -> Student object
        self.students_by_id: Dict[str, Student] = {s.id: s for s in problem.students}

        # Subject frequency for tie-breaking
        subject_counts = Counter(s.subject for s in problem.students)
        self.subject_weights = {sid: subject_counts[s.subject] for sid, s in self.students_by_id.items()}

    def solve(self) -> SolverResult:
        """Entry point for running the CSP solver."""
        self.start_time = time.perf_counter()
        self.steps = 0
        self.backtracks = 0
        self.domain_prunes = 0
        self.is_halted = False
        self.halted_reason = ""

        # Step 1: Pre-validation
        valid, errors = CSPValidator.pre_validate(
            self.problem.students,
            list(self.problem.rooms.values()),
            self.config
        )
        if not valid:
            elapsed = (time.perf_counter() - self.start_time) * 1000.0
            return SolverResult(
                success=False,
                status="FAILED_PREVALIDATION",
                reason="Pre-validation failed: " + "; ".join(errors),
                time_taken_ms=elapsed,
                violations=errors,
            )

        # Step 2: Initialize domains for each student variable
        # domains: Dict[student_id, Set[Seat]]
        domains: Dict[str, Set[Seat]] = {}
        for student in self.problem.students:
            initial_seats = set(self.problem.get_initial_domain(student))
            if not initial_seats:
                elapsed = (time.perf_counter() - self.start_time) * 1000.0
                return SolverResult(
                    success=False,
                    status="FAILED_NO_SOLUTION",
                    reason=f"Student {student.id} ({student.name}) has no eligible available seats.",
                    time_taken_ms=elapsed,
                )
            domains[student.id] = initial_seats

        assignment: Dict[str, Seat] = {}

        # Step 3: Run recursive backtracking
        final_assignment = self._backtrack(assignment, domains)

        elapsed = (time.perf_counter() - self.start_time) * 1000.0

        if final_assignment is not None:
            # Audit the solution to guarantee 100% adherence to all hard constraints
            valid_sol, violations = CSPValidator.verify_solution(self.problem, final_assignment)
            if not valid_sol:
                return SolverResult(
                    success=False,
                    status="FAILED_VALIDATION",
                    assignment=final_assignment,
                    steps=self.steps,
                    backtracks=self.backtracks,
                    domain_prunes=self.domain_prunes,
                    time_taken_ms=elapsed,
                    reason="Generated solution failed hard constraint verification: " + "; ".join(violations),
                    violations=violations,
                )

            return SolverResult(
                success=True,
                status="SUCCESS",
                assignment=final_assignment,
                steps=self.steps,
                backtracks=self.backtracks,
                domain_prunes=self.domain_prunes,
                time_taken_ms=elapsed,
                reason=f"Valid conflict-free seating arrangement successfully found in {self.steps} search steps.",
                diagnostics={
                    "total_students": len(self.problem.students),
                    "total_available_seats": len(self.problem.all_available_seats),
                    "rooms_used": list(set(s.room_id for s in final_assignment.values())),
                    "mrv_enabled": self.config.use_mrv,
                    "forward_checking_enabled": self.config.use_forward_checking,
                }
            )

        # Failure cases: timeout, step limit, or proved impossible
        if self.is_halted:
            status = "FAILED_TIMEOUT" if "timeout" in self.halted_reason.lower() else "FAILED_STEP_LIMIT"
            return SolverResult(
                success=False,
                status=status,
                steps=self.steps,
                backtracks=self.backtracks,
                domain_prunes=self.domain_prunes,
                time_taken_ms=elapsed,
                reason=self.halted_reason,
            )

        return SolverResult(
            success=False,
            status="FAILED_NO_SOLUTION",
            steps=self.steps,
            backtracks=self.backtracks,
            domain_prunes=self.domain_prunes,
            time_taken_ms=elapsed,
            reason=(
                "No valid seating arrangement exists satisfying all constraints. "
                "Consider increasing room sizes, reducing same-subject student density, "
                "or disabling diagonal adjacency if enabled."
            ),
        )

    def _backtrack(
        self,
        assignment: Dict[str, Seat],
        domains: Dict[str, Set[Seat]]
    ) -> Optional[Dict[str, Seat]]:
        """
        Recursive Backtracking Search.
        Base Case: If assignment is complete, return assignment.
        Recursive Step: Pick variable, iterate domain values, apply forward checking, recurse, backtrack.
        """
        self.steps += 1

        # Check safety search limits
        if self.steps > self.config.max_search_steps:
            self.is_halted = True
            self.halted_reason = (
                f"Backtracking search limit reached ({self.config.max_search_steps} steps). "
                "A solution was not found within this budget. Constraints may be too restrictive."
            )
            return None

        # Check safety timeout
        elapsed_sec = time.perf_counter() - self.start_time
        if elapsed_sec > self.config.timeout_seconds:
            self.is_halted = True
            self.halted_reason = (
                f"Search timeout exceeded ({self.config.timeout_seconds:.1f}s). "
                "A solution was not found within the time limit."
            )
            return None

        # Base case: All students are assigned
        if len(assignment) == len(self.problem.students):
            return assignment

        # Select unassigned student variable (using MRV or standard ordering)
        var_student = self._select_unassigned_variable(assignment, domains)
        if var_student is None:
            return None

        # Order domain values (seats) for the selected student
        ordered_seats = self._order_domain_values(var_student, domains[var_student.id], assignment)

        for seat in ordered_seats:
            # Check consistency if forward checking is disabled
            if not self.config.use_forward_checking:
                if not self._is_consistent(var_student, seat, assignment):
                    continue

            # Tentatively assign seat to student
            assignment[var_student.id] = seat

            if self.config.use_forward_checking:
                # Apply forward checking and record pruned seats
                is_valid, prunes = self._forward_check(var_student, seat, assignment, domains)
                if is_valid:
                    result = self._backtrack(assignment, domains)
                    if result is not None:
                        return result
                    if self.is_halted:
                        return None

                # Dead end reached or wipeout: undo prunes
                self._restore_prunes(domains, prunes)
            else:
                result = self._backtrack(assignment, domains)
                if result is not None:
                    return result
                if self.is_halted:
                    return None

            # Backtrack: undo assignment
            del assignment[var_student.id]
            self.backtracks += 1

        return None

    def _select_unassigned_variable(
        self,
        assignment: Dict[str, Seat],
        domains: Dict[str, Set[Seat]]
    ) -> Optional[Student]:
        """
        Chooses the next unassigned student variable.
        Uses MRV (Minimum Remaining Values) with subject weight as tie-breaker.
        """
        unassigned = [s for s in self.problem.students if s.id not in assignment]
        if not unassigned:
            return None

        if not self.config.use_mrv:
            return unassigned[0]

        # MRV: pick student with smallest domain size
        # Tie-breaker: largest subject weight (more students in same subject = harder to seat later)
        return min(
            unassigned,
            key=lambda s: (len(domains.get(s.id, set())), -self.subject_weights.get(s.id, 0))
        )

    def _order_domain_values(
        self,
        student: Student,
        domain_seats: Set[Seat],
        assignment: Dict[str, Seat]
    ) -> List[Seat]:
        """
        Orders domain values (seats) to test.
        Sorts seats by room, row, col.
        """
        return sorted(domain_seats, key=lambda s: (s.room_id, s.row, s.col))

    def _is_consistent(
        self,
        student: Student,
        seat: Seat,
        assignment: Dict[str, Seat]
    ) -> bool:
        """
        Checks whether assigning 'student' to 'seat' satisfies all constraints
        with the current partial assignment.
        Used when Forward Checking is disabled, and as safety verification.
        """
        # Constraint 1: Seat must not already be occupied
        for other_sid, other_seat in assignment.items():
            if seat == other_seat:
                return False

            # Constraint 2: Same-subject adjacency check
            other_student = self.students_by_id[other_sid]
            if other_student.subject == student.subject:
                if self.problem.are_seats_adjacent(seat, other_seat):
                    return False

        return True

    def _forward_check(
        self,
        assigned_student: Student,
        assigned_seat: Seat,
        assignment: Dict[str, Seat],
        domains: Dict[str, Set[Seat]]
    ) -> Tuple[bool, List[Tuple[str, Seat]]]:
        """
        Forward Checking Inference:
        Propagates constraints from the newly assigned (student, seat).
        Removes:
          1. The assigned seat from all remaining unassigned students.
          2. All adjacent seats in the same room from unassigned students taking the SAME subject.
        Returns (is_valid, list_of_pruned_entries) where each entry is (student_id, seat).
        If any unassigned student's domain becomes empty, returns False immediately.
        """
        prunes: List[Tuple[str, Seat]] = []

        # Pre-calculate conflicting adjacent seats in this room
        conflicting_adjacent_seats = set()
        if self.config.prevent_same_subject_horizontal or self.config.prevent_same_subject_vertical:
            conflicting_adjacent_seats.update(
                self.problem.orthogonal_neighbors.get(assigned_seat, set())
            )
        if self.config.prevent_same_subject_diagonal:
            conflicting_adjacent_seats.update(
                self.problem.diagonal_neighbors.get(assigned_seat, set())
            )

        for sid, domain in domains.items():
            if sid in assignment:
                continue

            # Prune 1: Occupied seat cannot be used by any other student
            if assigned_seat in domain:
                domain.remove(assigned_seat)
                prunes.append((sid, assigned_seat))
                self.domain_prunes += 1

            # Prune 2: Same-subject adjacency restriction
            other_student = self.students_by_id[sid]
            if other_student.subject == assigned_student.subject:
                common_adjacent = domain.intersection(conflicting_adjacent_seats)
                for adj_seat in common_adjacent:
                    domain.remove(adj_seat)
                    prunes.append((sid, adj_seat))
                    self.domain_prunes += 1

            # Domain Wipeout detection: if any student has 0 legal seats left, FAIL immediately!
            if len(domain) == 0:
                return False, prunes

        return True, prunes

    def _restore_prunes(
        self,
        domains: Dict[str, Set[Seat]],
        prunes: List[Tuple[str, Seat]]
    ) -> None:
        """Restores seats pruned by forward checking upon backtracking."""
        for sid, seat in prunes:
            domains[sid].add(seat)
