"""
Problem representation for AI-Based Examination Seating Arrangement Using CSP.

Variables: Students to be seated
Domains: Available, eligible seats in exam rooms
Constraints:
  1. Room eligibility & seat availability (Unary constraint)
  2. Each student assigned exactly one seat (Injective / AllDifferent)
  3. Room capacity cannot be exceeded
  4. Same-subject horizontal & vertical adjacency restriction (configurable)
  5. Same-subject diagonal adjacency restriction (configurable, off by default)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional


@dataclass(frozen=True)
class Seat:
    """Represents a physical examination seat in a specific room."""
    room_id: str
    row: int
    col: int
    is_available: bool = True

    @property
    def seat_id(self) -> str:
        return f"{self.room_id}-R{self.row + 1}C{self.col + 1}"

    @property
    def label(self) -> str:
        return f"R{self.row + 1}C{self.col + 1}"

    def __repr__(self) -> str:
        return f"Seat({self.seat_id})"


@dataclass
class Room:
    """Represents an examination hall / room with grid dimensions."""
    id: str
    name: str
    rows: int
    cols: int
    # Set of (row, col) tuples indicating broken or blocked seats
    unavailable_seats: Set[Tuple[int, int]] = field(default_factory=set)

    @property
    def total_capacity(self) -> int:
        return self.rows * self.cols

    @property
    def available_capacity(self) -> int:
        return max(0, self.total_capacity - len(self.unavailable_seats))

    def is_seat_available(self, row: int, col: int) -> bool:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return (row, col) not in self.unavailable_seats
        return False

    def get_all_seats(self) -> List[Seat]:
        """Returns all seats in the room, marked with their availability."""
        seats = []
        for r in range(self.rows):
            for c in range(self.cols):
                avail = (r, c) not in self.unavailable_seats
                seats.append(Seat(room_id=self.id, row=r, col=c, is_available=avail))
        return seats

    def get_available_seats(self) -> List[Seat]:
        """Returns only the usable, available seats."""
        return [s for s in self.get_all_seats() if s.is_available]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "rows": self.rows,
            "cols": self.cols,
            "unavailable_seats": [list(pos) for pos in sorted(self.unavailable_seats)],
            "total_capacity": self.total_capacity,
            "available_capacity": self.available_capacity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        unavail = set(tuple(p) for p in data.get("unavailable_seats", []))
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            rows=int(data["rows"]),
            cols=int(data["cols"]),
            unavailable_seats=unavail,
        )


@dataclass
class Student:
    """Represents a student taking an examination."""
    id: str
    name: str
    subject: str
    eligible_rooms: Optional[List[str]] = None  # None means any active room

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "eligible_rooms": self.eligible_rooms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=str(data["id"]).strip(),
            name=str(data.get("name", data["id"])).strip(),
            subject=str(data.get("subject", "General")).strip(),
            eligible_rooms=data.get("eligible_rooms"),
        )


@dataclass
class CSPConfig:
    """Configuration options for CSP constraints and algorithm execution."""
    prevent_same_subject_horizontal: bool = True
    prevent_same_subject_vertical: bool = True
    prevent_same_subject_diagonal: bool = False
    use_mrv: bool = True
    use_forward_checking: bool = True
    max_search_steps: int = 50000
    timeout_seconds: float = 12.0

    def to_dict(self) -> dict:
        return {
            "prevent_same_subject_horizontal": self.prevent_same_subject_horizontal,
            "prevent_same_subject_vertical": self.prevent_same_subject_vertical,
            "prevent_same_subject_diagonal": self.prevent_same_subject_diagonal,
            "use_mrv": self.use_mrv,
            "use_forward_checking": self.use_forward_checking,
            "max_search_steps": self.max_search_steps,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CSPConfig":
        return cls(
            prevent_same_subject_horizontal=bool(data.get("prevent_same_subject_horizontal", True)),
            prevent_same_subject_vertical=bool(data.get("prevent_same_subject_vertical", True)),
            prevent_same_subject_diagonal=bool(data.get("prevent_same_subject_diagonal", False)),
            use_mrv=bool(data.get("use_mrv", True)),
            use_forward_checking=bool(data.get("use_forward_checking", True)),
            max_search_steps=int(data.get("max_search_steps", 50000)),
            timeout_seconds=float(data.get("timeout_seconds", 12.0)),
        )


class CSPProblem:
    """
    Formal representation of the Examination Seating CSP.
    
    Contains variables (Students), available domain values (Seats),
    and adjacency constraint lookup helpers.
    """

    def __init__(self, students: List[Student], rooms: List[Room], config: Optional[CSPConfig] = None):
        self.students = students
        self.rooms = {r.id: r for r in rooms}
        self.config = config or CSPConfig()
        
        # Build list of all available seats
        self.all_available_seats: List[Seat] = []
        for room in rooms:
            self.all_available_seats.extend(room.get_available_seats())

        # Precompute seat lookups
        self.seat_by_id: Dict[str, Seat] = {s.seat_id: s for s in self.all_available_seats}

        # Precompute spatial adjacency table for fast O(1) checks during backtracking
        # adjacency_map[seat_id] -> set of adjacent seat_ids in the same room
        self.orthogonal_neighbors: Dict[Seat, Set[Seat]] = {}
        self.diagonal_neighbors: Dict[Seat, Set[Seat]] = {}
        self._build_spatial_indices()

    def _build_spatial_indices(self) -> None:
        """Precomputes neighbor relations for all available seats to avoid repeated calculations."""
        # Group available seats by room and (row, col)
        room_seat_map: Dict[str, Dict[Tuple[int, int], Seat]] = {}
        for s in self.all_available_seats:
            room_seat_map.setdefault(s.room_id, {})[(s.row, s.col)] = s

        for seat in self.all_available_seats:
            ortho = set()
            diag = set()
            grid = room_seat_map.get(seat.room_id, {})
            r, c = seat.row, seat.col

            # Orthogonal: horizontal and vertical
            if self.config.prevent_same_subject_horizontal:
                for dc in (-1, 1):
                    neighbor = grid.get((r, c + dc))
                    if neighbor:
                        ortho.add(neighbor)

            if self.config.prevent_same_subject_vertical:
                for dr in (-1, 1):
                    neighbor = grid.get((r + dr, c))
                    if neighbor:
                        ortho.add(neighbor)

            # Diagonal
            if self.config.prevent_same_subject_diagonal:
                for dr in (-1, 1):
                    for dc in (-1, 1):
                        neighbor = grid.get((r + dr, c + dc))
                        if neighbor:
                            diag.add(neighbor)

            self.orthogonal_neighbors[seat] = ortho
            self.diagonal_neighbors[seat] = diag

    def are_seats_adjacent(self, seat_a: Seat, seat_b: Seat) -> bool:
        """Determines if seat_a and seat_b violate the active adjacency rules."""
        if seat_a.room_id != seat_b.room_id:
            return False

        dr = abs(seat_a.row - seat_b.row)
        dc = abs(seat_a.col - seat_b.col)

        # Check horizontal adjacency
        if self.config.prevent_same_subject_horizontal and dr == 0 and dc == 1:
            return True

        # Check vertical adjacency
        if self.config.prevent_same_subject_vertical and dr == 1 and dc == 0:
            return True

        # Check diagonal adjacency
        if self.config.prevent_same_subject_diagonal and dr == 1 and dc == 1:
            return True

        return False

    def get_initial_domain(self, student: Student) -> List[Seat]:
        """Returns the initial legal domain of seats for a student based on room eligibility."""
        if student.eligible_rooms is None:
            return list(self.all_available_seats)
        eligible_set = set(student.eligible_rooms)
        return [s for s in self.all_available_seats if s.room_id in eligible_set]
