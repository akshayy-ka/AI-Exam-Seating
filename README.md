# AI-Based Examination Seating Arrangement Using CSP and Backtracking

An educational Artificial Intelligence college project that automatically assigns students to examination seats in physical halls while strictly satisfying academic and spatial anti-cheating constraints.

> **Project Notice**: This is an academic demonstration and lab project built to demonstrate **Constraint Satisfaction Problems (CSP)** and **heuristic search algorithms** (Backtracking with Minimum Remaining Values and Forward Checking). It is designed for college evaluation and viva demonstrations, **not** as a commercial, enterprise production system.

---

## Table of Contents
1. [Project Overview & Key Features](#project-overview--key-features)
2. [Why CSP and Not Machine Learning?](#why-csp-and-not-machine-learning)
3. [Formal CSP Mathematical Model](#formal-csp-mathematical-model)
4. [Algorithmic Architecture & Heuristics](#algorithmic-architecture--heuristics)
5. [System Architecture & File Structure](#system-architecture--file-structure)
6. [Technology Stack](#technology-stack)
7. [Installation & Setup (Windows PowerShell)](#installation--setup-windows-powershell)
8. [Running the Application](#running-the-application)
9. [Running the Test Suite](#running-the-test-suite)
10. [College Viva & Demonstration Guide](#college-viva--demonstration-guide)
11. [Project Scope & Known Limitations](#project-scope--known-limitations)

---

## Project Overview & Key Features

During university examinations, preventing academic malpractice requires intelligent seat allocation. When students taking the same exam paper sit side-by-side or front-to-back, copying risks increase significantly. Manually preparing conflict-free seating plans for dozens or hundreds of students across multiple examination halls with broken or obstructed seats is error-prone, tedious, and combinatorially explosive.

This application models examination seating as a formal **Constraint Satisfaction Problem (CSP)** and solves it using **Recursive Backtracking Search** augmented with **Minimum Remaining Values (MRV)** heuristic and **Forward Checking (FC)** domain inference.

### Core Features:
- **Clean, Minimalist Light UI**: Clean white surfaces, subtle slate borders, accessible typography (Inter font), and refined blue accents designed for academic project presentations.
- **Interactive Student Management**: Add, edit, delete, search, and bulk-import students (Roll No / ID, Full Name, Exam Subject).
- **Interactive Room Seat Layouts**: Configure exam halls (rows & columns) and **click any seat** to toggle between Available and Unavailable (broken desk, pillar, aisle obstruction).
- **Configurable Hard Constraints**:
  - Prevent horizontal adjacency between students taking the same subject (Default: ON).
  - Prevent vertical adjacency between students taking the same subject (Default: ON).
  - Prevent diagonal adjacency (Configurable toggle, Default: OFF).
- **Algorithmic Heuristic Toggles for Viva Demonstrations**:
  - Enable/disable Minimum Remaining Values (MRV) heuristic.
  - Enable/disable Forward Checking (FC) domain pruning.
  - Observe the difference in search steps, backtracks, and pruning in real time.
- **Visual Classroom Grid**: High-fidelity classroom visualizer with teacher podium / blackboard indicators, coordinate labels ($R_i C_j$), and distinct color-coded subject badges.
- **Room-by-Room View, Printing & Export**:
  - Dedicated `@media print` CSS layout for clean physical notice-board attendance printouts.
  - One-click CSV export with room, seat, row, column, student ID, name, and subject.
- **Pre-Validation & Diagnostic Explanations**: Detects mathematically impossible configurations (e.g. Pigeonhole principle deficit, bipartite checkerboard capacity overflow) *before* search, providing an exact, educational reason if seating fails.
- **Manual Seat Adjustment**: Allows manually moving a student or swapping two students with instant full CSP validation.

---

## Why CSP and Not Machine Learning?

In an AI Viva or project presentation, examiners frequently ask:
> *"Why did you use CSP with Backtracking rather than Deep Learning or Machine Learning?"*

### Clear Distinction:
1. **Machine Learning** is probabilistic and data-driven: it learns statistical patterns from historical datasets. It **cannot mathematically guarantee** that a hard rule (e.g. *"never place two math students next to each other"*) will never be violated.
2. **CSP (Constraint Satisfaction Problem)** is a foundational, exact branch of Symbolic Artificial Intelligence. It explores the state space using deductive constraints, logical pruning, and heuristics. It guarantees:
   - **Completeness**: If a valid seating arrangement exists, backtracking search is guaranteed to find it.
   - **Soundness**: Every returned solution is strictly audited and verified against 100% of hard constraints.
   - **Zero Training Overhead**: No pre-training or large historical datasets required.

---

## Formal CSP Mathematical Model

A CSP is formally defined as a 3-tuple:
$$\text{CSP} = (X, D, C)$$

### 1. Variables ($X$):
The set of all registered examination candidates:
$$X = \{ S_1, S_2, \dots, S_n \}$$
Where each student $S_k$ has attributes: $\text{ID}$, $\text{Name}$, and $\text{Subject}$.

### 2. Domains ($D$):
For each student variable $S_k$, its initial domain $D(S_k)$ is the set of all available physical seats across eligible examination halls:
$$D(S_k) = \{ (r, i, j) \mid r \in \text{Rooms}, 0 \le i < \text{rows}_r, 0 \le j < \text{cols}_r, (i, j) \notin \text{Unavailable}_r \}$$

### 3. Constraints ($C$):
1. **Seat Availability (Unary Constraint)**:
   $$\forall S_k \in X, \quad \text{seat}(S_k) \in D(S_k) \quad (\text{seat is non-broken and available})$$
2. **Injective Seat Allocation (AllDifferent / Bijective Constraint)**:
   $$\forall S_i, S_j \in X, \quad i \ne j \implies \text{seat}(S_i) \ne \text{seat}(S_j)$$
   *(Each seat holds at most one student; each student is seated exactly once).*
3. **Room Capacity Limit**:
   $$\forall r \in \text{Rooms}, \quad |\{ S_k \mid \text{seat}(S_k).\text{room} = r \}| \le \text{AvailableCapacity}(r)$$
4. **Orthogonal Same-Subject Adjacency Constraint (Horizontal & Vertical)**:
   If $\text{Subject}(S_i) == \text{Subject}(S_j)$ and $\text{seat}(S_i).\text{room} == \text{seat}(S_j).\text{room}$:
   - Horizontal: $|row_i - row_j| == 0 \implies |col_i - col_j| > 1$
   - Vertical: $|col_i - col_j| == 0 \implies |row_i - row_j| > 1$
5. **Diagonal Adjacency Constraint (Optional / Configurable)**:
   If diagonal adjacency prevention is enabled:
   $$|row_i - row_j| == 1 \implies |col_i - col_j| \ne 1$$

---

## Algorithmic Architecture & Heuristics

The core search engine is implemented in `csp/solver.py`:

```
                    [ Start CSP Solver ]
                             │
                  [ Step 1: Pre-Validation ]
                 (Capacity & Density Bounds)
                             │ Pass
                  [ Step 2: Initialize Domains ]
                             │
              [ Step 3: Recursive Backtrack DFS ]
                             │
                 ┌───────────┴───────────┐
                 │                       │
      [ MRV Variable Selection ]    [ Complete? ] ──► Return Solution
                 │                       
      [ Domain Seat Ordering ]
                 │
      [ Tentative Seat Assignment ]
                 │
      [ Forward Checking Inference ]
     (Prune occupied & adjacent seats)
                 │
        ┌────────┴────────┐
        │                 │
 [ Wipeout: D(S)=∅ ]  [ Legal Domains ]
        │                 │
  [ Backtrack ]       [ Recurse ]
 (Undo Prunes)
```

### 1. Minimum Remaining Values (MRV) Heuristic
- Also known as the **"Most Constrained Variable"** or **"Fail-First"** heuristic.
- Instead of picking students arbitrarily, the solver chooses the unassigned student with the fewest legal seats remaining in their domain:
  $$\text{choose } S^* = \arg\min_{S \in \text{Unassigned}} |D(S)|$$
- **Why it matters**: If a student is on the verge of running out of seats, placing them immediately forces any unavoidable failure to surface near the root of the search tree, preventing millions of wasted iterations deep down dead paths.

### 2. Forward Checking (FC) Inference
- When student $S_i$ is placed in seat $(r, \text{row}, \text{col})$:
  1. That seat is removed from all other unassigned students' domains.
  2. For all other unassigned students $S_j$ taking the **same exam paper**, all orthogonal (and optionally diagonal) adjacent seats in room $r$ are pruned from $D(S_j)$.
  3. **Domain Wipeout Detection**: If any unassigned student's domain becomes empty ($|D(S_k)| = 0$), the assignment cannot lead to a valid solution. The solver immediately undoes the prunes and backtracks without recursing!

### 3. Theoretical Bipartite Checkerboard Pre-Validation
- An $R \times C$ room grid forms a bipartite graph with 2-coloring:
  $$\text{Color}(r, c) = (r + c) \pmod 2$$
- In any room, the maximum number of mutually non-adjacent seats for a single subject cannot exceed $\max(\text{Color}_A, \text{Color}_B)$.
- If any single subject has more students than this theoretical upper bound across all rooms, the system detects this in $O(1)$ time and explains why it cannot be seated before running backtracking.

---

## System Architecture & File Structure

```
AI_Exam_Seating/
│
├── app.py                      # Flask REST API endpoints and web routing
├── database.py                 # SQLite database storage & schema management
├── sample_data.py              # Realistic sample dataset (24 students, 2 rooms)
├── requirements.txt            # Python dependencies (flask>=3.0.0)
├── README.md                   # Complete documentation, setup, and viva guide
├── exam_seating.db             # Local SQLite database file
│
├── csp/
│   ├── __init__.py             # CSP module initialization
│   ├── problem.py              # Student, Seat, Room, and CSPProblem data models
│   ├── solver.py               # Recursive Backtracking Solver with MRV & Forward Checking
│   └── validator.py            # Pre-search validator and post-solution hard constraint verifier
│
├── static/
│   ├── css/
│   │   └── style.css           # Clean, minimalist light theme, responsive, print stylesheet
│   └── js/
│       └── app.js              # Complete frontend logic, seat visualizer, CRUD, solver trigger
│
├── templates/
│   └── index.html              # Single-page dashboard with tabs, modals, and viva guide
│
└── tests/
    ├── __init__.py
    ├── test_csp.py             # Unit tests for all 9 CSP constraint and heuristic cases
    └── test_api.py             # End-to-end integration tests for Flask REST endpoints
```

---

## Technology Stack

- **Backend**: Python 3.10+ with Flask (lightweight REST API).
- **AI Technique**: Traditional Constraint Satisfaction Problem (CSP) with Recursive Backtracking, MRV heuristic, and Forward Checking.
- **Database**: SQLite 3 (built into Python standard library, persists data in `exam_seating.db`).
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+). No heavy external frameworks or npm build steps required.
- **Styling**: Custom CSS designed according to clean, minimal, professional light theme guidelines with subtle blue accents (`#2563eb`), Inter typography, and print-ready CSS (`@media print`).

---

## Installation & Setup (Windows PowerShell)

Follow these exact commands in **Windows PowerShell** to set up and run the project:

### Step 1: Open PowerShell and Navigate to the Project Folder
```powershell
cd C:\Path\To\AI_Exam_Seating
```
*Explanation*: Changes the working directory in PowerShell to the project folder containing `app.py`.

### Step 2: Create a Python Virtual Environment
```powershell
python -m venv venv
```
*Explanation*: Creates an isolated Python virtual environment inside the `venv` directory so that dependencies do not conflict with your global system Python packages.

### Step 3: Enable Script Execution and Activate the Virtual Environment
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\venv\Scripts\Activate.ps1
```
*Explanation*: 
- `Set-ExecutionPolicy` temporarily allows PowerShell to run local scripts in the current terminal session without permanently altering your Windows security settings.
- `Activate.ps1` activates the virtual environment. You will see `(venv)` appear at the beginning of your command prompt.

### Step 4: Upgrade pip and Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```
*Explanation*: 
- Upgrades `pip` to the latest version.
- Installs the required packages listed in `requirements.txt` (Flask and its core dependencies: Werkzeug, Jinja2, Click, Blinker, MarkupSafe).

---

## Running the Application

### Start the Flask Web Server
With the virtual environment activated, run:
```powershell
python app.py
```
*Explanation*: Launches the Flask web server on `http://127.0.0.1:5000` with debug mode enabled.

You will see output similar to:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

### Accessing the Web Application
Open your web browser (Chrome, Edge, or Firefox) and go to:
```
http://127.0.0.1:5000
```

---

## Running the Test Suite

The project includes an automated test suite verifying all CSP constraints, heuristic search behavior, and API endpoints.

### Run All Unit and Integration Tests:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```
*Explanation*: Automatically discovers and runs all test files matching `test_*.py` inside the `tests` directory using Python's standard `unittest` framework.

### Expected Output:
```text
................
----------------------------------------------------------------------
Ran 16 tests in 0.040s

OK
```

The 16 tests cover:
1. Simple valid seating arrangement.
2. Same-subject students not sitting adjacent (horizontal & vertical).
3. No duplicate seat assignments (Injective mapping / AllDifferent).
4. Unavailable/broken seats never being assigned.
5. Multiple rooms and room capacities.
6. Impossible constraint configurations (capacity deficit & density limits).
7. Empty or invalid input handling.
8. Diagonal adjacency prevention rule.
9. **MRV and Forward Checking search heuristics and prune counts**.
10. Web UI index page route loading.
11. Student CRUD (Create, Read, Update, Delete).
12. Bulk student import from multi-line text / CSV.
13. Room creation, dimension validation, and interactive seat availability toggle.
14. End-to-end solver execution pipeline and CSV export.
15. Manual seat change with strict CSP constraint verification.
16. Configuration API retrieval and updating (including MRV and FC toggles).

---

## College Viva & Demonstration Guide

Use this walkthrough to present the project to external examiners:

### Demo Walkthrough:
1. **Load Sample Dataset**:
   - Click the **"Load Sample Data"** button in the top navigation bar or on the dashboard.
   - This automatically populates 24 students across 4 subjects (*Artificial Intelligence*, *Operating Systems*, *Database Systems*, *Computer Networks*) and 2 examination halls (*LH-101* and *LH-102*).
2. **Examine Broken / Blocked Desks**:
   - Navigate to the **Rooms & Layouts** tab.
   - Point out that seat `R1C1` and `R3C3` in LH-101 are marked **Unavailable** (broken desk or pillar).
   - Click any seat to demonstrate how easily the exam administrator can toggle seat availability.
3. **Execute the CSP Backtracking Solver**:
   - Click **"Generate Seating"**.
   - The application executes recursive backtracking search with MRV and Forward Checking, completing in under 5 milliseconds.
   - The UI automatically navigates to the **Seating Chart & Visualizer** tab.
4. **Demonstrate Constraint Satisfaction**:
   - Inspect the visual room grids.
   - Show that no two students with the same color-coded subject badge sit horizontally or vertically adjacent.
   - Confirm that broken/blocked desks remain completely unassigned.
5. **Demonstrate MRV & Forward Checking Heuristic Speedup**:
   - Navigate to the **Seating Constraints** tab.
   - Explain the **Fail-First Principle** of MRV and 1-step lookahead of Forward Checking.
   - Disable MRV or Forward Checking, click **Save Settings**, and re-generate.
   - Show how the step count, backtracks, and pruning metrics change in the results summary bar.
6. **Print and Export Attendance Charts**:
   - Click **"Print Chart"** to display the clean `@media print` formatted layout suitable for printing notice-board notices.
   - Click **"Export CSV"** to download the complete allocation in spreadsheet format.
7. **Manual Seat Adjustment with Real-Time CSP Verification**:
   - Click on any assigned student seat in the visualizer to open the **Manual Seat Reassignment** modal.
   - Attempt to place the student into an adjacent seat of a student with the same subject.
   - Show that the system immediately rejects the move with status code 422 and displays the exact constraint violation!

---

## Project Scope & Known Limitations

This system is built as a focused college academic project. For full transparency during evaluation, note the following design characteristics and limitations:

1. **Academic Demonstration Focus**:
   - The system is built for single-institution demonstrations and coursework evaluation rather than high-concurrency multi-tenant cloud deployments.
2. **Single Examination Session**:
   - The CSP model allocates students to rooms and seats for a **single concurrent exam slot**. Multi-slot timetabling (spanning multiple dates and time slots) is typically modeled as a separate prior scheduling phase.
3. **Grid-Based Room Topology**:
   - Exam rooms are represented as rectangular $R \times C$ grids. Irregularly shaped halls (curved amphitheaters or staggered seating rows) can be represented by marking non-existent grid spaces as unavailable.
4. **Single-Threaded Backtracking Search**:
   - The backtracking algorithm executes synchronously within the Flask request thread. For massive datasets (>1,000 students in a single room), asynchronous background task queues (e.g., Celery) would be required to prevent HTTP timeouts.
