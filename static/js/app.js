/**
 * AI Examination Seating Arrangement - Frontend Application Logic
 * Implements interactive dashboard, student/room management, interactive seat toggling,
 * CSP solver execution, visual seating grid rendering, and export/print actions.
 */

// Application State
const state = {
    students: [],
    rooms: [],
    config: {},
    stats: {},
    arrangement: null,
    editingStudentId: null,
    subjectColorMap: {},
};

// Distinct pastel color palette for subjects
const SUBJECT_COLORS = [
    { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" }, // Blue
    { bg: "#f0fdf4", text: "#15803d", border: "#bbf7d0" }, // Green
    { bg: "#faf5ff", text: "#7e22ce", border: "#e9d5ff" }, // Purple
    { bg: "#fff7ed", text: "#c2410c", border: "#fed7aa" }, // Orange
    { bg: "#fdf2f8", text: "#be185d", border: "#fbcfe8" }, // Pink
    { bg: "#ecfeff", text: "#0e7490", border: "#a5f3fc" }, // Cyan
    { bg: "#fefce8", text: "#a16207", border: "#fef08a" }, // Yellow/Amber
    { bg: "#f1f5f9", text: "#334155", border: "#cbd5e1" }, // Slate
];

// Utility: Assign or get subject color
function getSubjectStyle(subject) {
    if (!subject) return SUBJECT_COLORS[0];
    if (!state.subjectColorMap[subject]) {
        const index = Object.keys(state.subjectColorMap).length % SUBJECT_COLORS.length;
        state.subjectColorMap[subject] = SUBJECT_COLORS[index];
    }
    return state.subjectColorMap[subject];
}

// Utility: Toast notifications
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-message">${escapeHtml(message)}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 250);
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ==============================================================================
// INITIALIZATION & TAB NAVIGATION
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initModals();
    initEventListeners();
    refreshAllData();
});

function initTabs() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetId = tab.dataset.tab;
            switchTab(targetId);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll(".nav-tab").forEach(t => {
        t.classList.toggle("active", t.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-pane").forEach(p => {
        p.classList.toggle("active", p.id === `tab-${tabId}`);
    });

    if (tabId === "students") {
        renderStudentsTable();
    } else if (tabId === "rooms") {
        renderRoomsCards();
    } else if (tabId === "results" && state.arrangement) {
        renderArrangementResults(state.arrangement);
    }
}

function initEventListeners() {
    // Header & Dashboard action buttons
    document.getElementById("btn-load-sample")?.addEventListener("click", loadSampleData);
    document.getElementById("btn-dashboard-load-sample")?.addEventListener("click", loadSampleData);
    document.getElementById("btn-reset-data")?.addEventListener("click", resetAllData);
    document.getElementById("btn-header-generate")?.addEventListener("click", generateArrangement);
    document.getElementById("btn-dashboard-generate")?.addEventListener("click", generateArrangement);
    document.getElementById("btn-generate-results-tab")?.addEventListener("click", generateArrangement);

    // Filter students
    document.getElementById("student-search-input").addEventListener("input", renderStudentsTable);
    document.getElementById("student-subject-filter").addEventListener("change", renderStudentsTable);

    // Student clear
    document.getElementById("btn-clear-students").addEventListener("click", clearAllStudents);

    // Save & reset constraints
    document.getElementById("btn-save-constraints").addEventListener("click", saveConstraints);
    document.getElementById("btn-reset-constraints").addEventListener("click", resetConstraints);

    // Print & Export
    document.getElementById("btn-print-seating").addEventListener("click", () => {
        if (!state.arrangement || !state.arrangement.success) {
            showToast("Please generate a valid seating arrangement before printing.", "error");
            return;
        }
        window.print();
    });
    document.getElementById("btn-download-csv").addEventListener("click", () => {
        if (!state.arrangement || !state.arrangement.success) {
            showToast("Please generate a valid seating arrangement before exporting.", "error");
            return;
        }
        window.location.href = "/api/export-csv";
    });
}

// ==============================================================================
// DATA FETCHING & SYNCHRONIZATION
// ==============================================================================

async function refreshAllData() {
    await Promise.all([
        fetchStats(),
        fetchStudents(),
        fetchRooms(),
        fetchConfig(),
        fetchLatestArrangement(),
    ]);
}

async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        state.stats = data;

        document.getElementById("stat-students").textContent = data.total_students;
        document.getElementById("stat-rooms").textContent = data.total_rooms;
        document.getElementById("stat-seats").textContent = data.available_seats;
        document.getElementById("stat-seats-sub").textContent = `${data.unavailable_seats} unavailable/broken`;
        document.getElementById("stat-subjects-sub").textContent = `${data.total_subjects} distinct subject(s)`;
        document.getElementById("stat-assigned").textContent = `${data.assigned_students} / ${data.total_students}`;

        const badge = document.getElementById("stat-status-badge");
        if (data.has_active_arrangement) {
            badge.textContent = "Arrangement Ready & Active";
            badge.style.color = "var(--success)";
        } else if (data.latest_arrangement_status && data.latest_arrangement_status.startsWith("FAILED")) {
            badge.textContent = "Arrangement Failed Constraints";
            badge.style.color = "var(--danger)";
        } else {
            badge.textContent = "No arrangement generated";
            badge.style.color = "var(--text-muted)";
        }

        // Render subject badges on dashboard
        renderDashboardSubjects(data.subjects || []);
    } catch (err) {
        console.error("Error fetching stats:", err);
    }
}

function renderDashboardSubjects(subjects) {
    const container = document.getElementById("subject-tags-container");
    if (!subjects || subjects.length === 0) {
        container.innerHTML = `<span class="text-slate-500 text-sm">No students registered yet.</span>`;
        return;
    }

    container.innerHTML = subjects.map(sub => {
        const style = getSubjectStyle(sub);
        const count = state.students.filter(s => s.subject === sub).length;
        return `
            <span class="badge badge-subject" style="background-color: ${style.bg}; color: ${style.text}; border-color: ${style.border}">
                ${escapeHtml(sub)} (${count} students)
            </span>
        `;
    }).join("");
}

async function fetchStudents() {
    try {
        const res = await fetch("/api/students");
        state.students = await res.json();
        document.getElementById("badge-students-count").textContent = state.students.length;
        populateSubjectFilterOptions();
        renderStudentsTable();
    } catch (err) {
        console.error("Error fetching students:", err);
    }
}

async function fetchRooms() {
    try {
        const res = await fetch("/api/rooms");
        state.rooms = await res.json();
        document.getElementById("badge-rooms-count").textContent = state.rooms.length;
        renderRoomsCards();
        renderDashboardRooms();
    } catch (err) {
        console.error("Error fetching rooms:", err);
    }
}

async function fetchConfig() {
    try {
        const res = await fetch("/api/config");
        state.config = await res.json();
        const h = document.getElementById("cfg-horizontal");
        if (h) h.checked = state.config.prevent_same_subject_horizontal ?? true;
        const v = document.getElementById("cfg-vertical");
        if (v) v.checked = state.config.prevent_same_subject_vertical ?? true;
        const d = document.getElementById("cfg-diagonal");
        if (d) d.checked = state.config.prevent_same_subject_diagonal ?? false;
        const mrv = document.getElementById("cfg-mrv");
        if (mrv) mrv.checked = state.config.use_mrv ?? true;
        const fc = document.getElementById("cfg-fc");
        if (fc) fc.checked = state.config.use_forward_checking ?? true;
    } catch (err) {
        console.error("Error fetching config:", err);
    }
}

async function fetchLatestArrangement() {
    try {
        const res = await fetch("/api/latest-arrangement");
        const data = await res.json();
        if (data.has_arrangement) {
            state.arrangement = data.data;
            renderArrangementResults(state.arrangement);
            renderStudentsTable();
        }
    } catch (err) {
        console.error("Error fetching arrangement:", err);
    }
}

// ==============================================================================
// STUDENT MANAGEMENT
// ==============================================================================

function populateSubjectFilterOptions() {
    const select = document.getElementById("student-subject-filter");
    const currentVal = select.value;
    const subjects = Array.from(new Set(state.students.map(s => s.subject))).sort();

    select.innerHTML = `<option value="">All Subjects (${subjects.length})</option>` +
        subjects.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
    select.value = currentVal;
}

function renderStudentsTable() {
    const tbody = document.getElementById("students-table-body");
    const query = document.getElementById("student-search-input").value.trim().toLowerCase();
    const subjectFilter = document.getElementById("student-subject-filter").value;

    let filtered = state.students.filter(s => {
        const matchesQuery = !query ||
            s.id.toLowerCase().includes(query) ||
            s.name.toLowerCase().includes(query) ||
            s.subject.toLowerCase().includes(query);
        const matchesSubject = !subjectFilter || s.subject === subjectFilter;
        return matchesQuery && matchesSubject;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-slate-500 py-8">
                    ${state.students.length === 0 ? 'No students registered. Click "Add Student" or "Bulk Import".' : 'No students match your filter criteria.'}
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map(s => {
        const style = getSubjectStyle(s.subject);
        let assignedInfo = null;
        if (state.arrangement && state.arrangement.success) {
            if (state.arrangement.detailed_assignment && state.arrangement.detailed_assignment[s.id]) {
                assignedInfo = state.arrangement.detailed_assignment[s.id];
            } else if (state.arrangement.assignment && state.arrangement.assignment[s.id]) {
                const raw = state.arrangement.assignment[s.id];
                assignedInfo = {
                    room_id: raw.room_id,
                    label: raw.label || `R${raw.row + 1}C${raw.col + 1}`,
                    row: raw.row,
                    col: raw.col
                };
            }
        }

        let seatBadgeHtml = `<span class="badge badge-seat-unassigned">Not Assigned</span>`;
        if (assignedInfo) {
            seatBadgeHtml = `
                <span class="badge badge-seat-assigned font-mono" onclick="openReassignModal('${escapeHtml(s.id)}')" title="Click to manually reassign or swap seat">
                    ${escapeHtml(assignedInfo.room_id)} · ${escapeHtml(assignedInfo.label)}
                </span>
            `;
        }

        return `
            <tr>
                <td><strong class="font-mono text-slate-800">${escapeHtml(s.id)}</strong></td>
                <td>${escapeHtml(s.name)}</td>
                <td>
                    <span class="badge badge-subject" style="background-color: ${style.bg}; color: ${style.text}; border-color: ${style.border}">
                        ${escapeHtml(s.subject)}
                    </span>
                </td>
                <td>${seatBadgeHtml}</td>
                <td class="text-right">
                    ${assignedInfo ? `<button class="btn btn-outline btn-sm" onclick="openReassignModal('${escapeHtml(s.id)}')" title="Manually change or swap seat">Change Seat</button>` : ''}
                    <button class="btn btn-outline btn-sm" onclick="editStudent('${escapeHtml(s.id)}')">Edit</button>
                    <button class="btn btn-ghost btn-sm text-danger" onclick="deleteStudent('${escapeHtml(s.id)}')">Delete</button>
                </td>
            </tr>
        `;
    }).join("");
}

function editStudent(studentId) {
    const student = state.students.find(s => s.id === studentId);
    if (!student) return;

    state.editingStudentId = student.id;
    document.getElementById("modal-student-title").textContent = "Edit Student";
    document.getElementById("inp-student-id").value = student.id;
    document.getElementById("inp-student-id").disabled = true;
    document.getElementById("inp-student-name").value = student.name;
    document.getElementById("inp-student-subject").value = student.subject;

    openModal("modal-student");
}

async function deleteStudent(studentId) {
    if (!confirm(`Delete student ${studentId}?`)) return;
    try {
        const res = await fetch(`/api/students/${encodeURIComponent(studentId)}`, { method: "DELETE" });
        if (res.ok) {
            showToast(`Student ${studentId} deleted.`, "info");
            await fetchStudents();
            await fetchStats();
        } else {
            showToast("Failed to delete student.", "error");
        }
    } catch (err) {
        showToast("Error deleting student.", "error");
    }
}

async function clearAllStudents() {
    if (!confirm("Are you sure you want to clear ALL students?")) return;
    try {
        const res = await fetch("/api/students", { method: "DELETE" });
        if (res.ok) {
            showToast("All students cleared.", "info");
            await fetchStudents();
            await fetchStats();
        }
    } catch (err) {
        showToast("Error clearing students.", "error");
    }
}

// ==============================================================================
// ROOM MANAGEMENT & INTERACTIVE SEAT TOGGLE
// ==============================================================================

function renderDashboardRooms() {
    const container = document.getElementById("dashboard-rooms-list");
    if (!state.rooms || state.rooms.length === 0) {
        container.innerHTML = `<span class="text-slate-500 text-sm">No rooms configured.</span>`;
        return;
    }

    container.innerHTML = state.rooms.map(r => `
        <div class="flex items-center justify-between p-2 rounded bg-slate-50 border border-slate-200 text-sm">
            <div>
                <strong>${escapeHtml(r.name)}</strong>
                <span class="text-xs text-slate-500 ml-1 font-mono">(${r.rows}x${r.cols})</span>
            </div>
            <div class="text-xs">
                <span class="badge badge-available">${r.available_capacity} usable</span>
                ${r.unavailable_seats.length ? `<span class="badge badge-unavailable ml-1">${r.unavailable_seats.length} blocked</span>` : ''}
            </div>
        </div>
    `).join("");
}

function renderRoomsCards() {
    const container = document.getElementById("rooms-cards-container");
    if (!state.rooms || state.rooms.length === 0) {
        container.innerHTML = `
            <div class="card p-8 text-center text-slate-500">
                No examination rooms configured. Click <strong>"Add Room"</strong> to create an examination hall.
            </div>
        `;
        return;
    }

    container.innerHTML = state.rooms.map(room => {
        const unavailSet = new Set(room.unavailable_seats.map(p => `${p[0]},${p[1]}`));
        
        let gridHtml = '';
        for (let r = 0; r < room.rows; r++) {
            gridHtml += '<div style="display: flex; gap: 0.5rem; justify-content: center; margin-bottom: 0.5rem;">';
            for (let c = 0; c < room.cols; c++) {
                const isBlocked = unavailSet.has(`${r},${c}`);
                const seatLabel = `R${r+1}C${c+1}`;
                gridHtml += `
                    <div class="seat-cell room-editor-seat ${isBlocked ? 'unavailable' : ''}"
                         title="Click to toggle availability"
                         onclick="toggleSeatAvailability('${escapeHtml(room.id)}', ${r}, ${c})">
                        <div class="seat-cell-header">
                            <span class="seat-coord">${seatLabel}</span>
                        </div>
                        <div class="text-center my-auto">
                            ${isBlocked ?
                                '<span class="unavail-badge">Unavailable</span>' :
                                '<span class="badge badge-available">Available</span>'
                            }
                        </div>
                        <div class="text-xs text-slate-400 text-center">Click to toggle</div>
                    </div>
                `;
            }
            gridHtml += '</div>';
        }

        return `
            <div class="room-chart-card">
                <div class="room-chart-header">
                    <div>
                        <h3 class="room-chart-title">${escapeHtml(room.name)}</h3>
                        <span class="text-xs font-mono text-slate-500">ID: ${escapeHtml(room.id)} | ${room.rows} Rows &times; ${room.cols} Columns</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="room-stats-summary">
                            <span>Total: <strong>${room.total_capacity}</strong></span>
                            <span>Available: <strong class="text-emerald-600">${room.available_capacity}</strong></span>
                            <span>Unavailable: <strong class="text-red-500">${room.unavailable_seats.length}</strong></span>
                        </div>
                        <button class="btn btn-outline btn-sm text-danger" onclick="deleteRoom('${escapeHtml(room.id)}')">Delete Room</button>
                    </div>
                </div>
                <div class="room-chart-body">
                    <div class="lecturer-board">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                        Lecturer Podium / Front Board
                    </div>
                    <div class="seating-grid-wrapper">
                        ${gridHtml}
                    </div>
                    <div class="grid-legend">
                        <div class="legend-item">
                            <span class="legend-swatch" style="background: #ffffff; border: 1px solid #10b981;"></span> Available Seat (Usable)
                        </div>
                        <div class="legend-item">
                            <span class="legend-swatch swatch-unavail"></span> Unavailable (Pillar / Broken / Blocked)
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

async function toggleSeatAvailability(roomId, row, col) {
    try {
        const res = await fetch(`/api/rooms/${encodeURIComponent(roomId)}/toggle-seat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ row, col })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Seat R${row+1}C${col+1} marked ${data.seat_status}.`, "info");
            await fetchRooms();
            await fetchStats();
        } else {
            showToast(data.error || "Failed to toggle seat.", "error");
        }
    } catch (err) {
        showToast("Error updating seat.", "error");
    }
}

async function deleteRoom(roomId) {
    if (!confirm(`Delete room '${roomId}'?`)) return;
    try {
        const res = await fetch(`/api/rooms/${encodeURIComponent(roomId)}`, { method: "DELETE" });
        if (res.ok) {
            showToast(`Room '${roomId}' deleted.`, "info");
            await fetchRooms();
            await fetchStats();
        } else {
            showToast("Failed to delete room.", "error");
        }
    } catch (err) {
        showToast("Error deleting room.", "error");
    }
}

// ==============================================================================
// CONSTRAINTS & SETTINGS
// ==============================================================================

async function saveConstraints() {
    const payload = {
        prevent_same_subject_horizontal: document.getElementById("cfg-horizontal")?.checked ?? true,
        prevent_same_subject_vertical: document.getElementById("cfg-vertical")?.checked ?? true,
        prevent_same_subject_diagonal: document.getElementById("cfg-diagonal")?.checked ?? false,
        use_mrv: document.getElementById("cfg-mrv")?.checked ?? true,
        use_forward_checking: document.getElementById("cfg-fc")?.checked ?? true,
        max_search_steps: 50000,
        timeout_seconds: 12.0,
    };

    try {
        const res = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast("Seating constraints saved successfully.", "success");
            await fetchConfig();
        } else {
            showToast("Failed to save constraints.", "error");
        }
    } catch (err) {
        showToast("Error saving constraints.", "error");
    }
}

function resetConstraints() {
    const h = document.getElementById("cfg-horizontal");
    if (h) h.checked = true;
    const v = document.getElementById("cfg-vertical");
    if (v) v.checked = true;
    const d = document.getElementById("cfg-diagonal");
    if (d) d.checked = false;
    const mrv = document.getElementById("cfg-mrv");
    if (mrv) mrv.checked = true;
    const fc = document.getElementById("cfg-fc");
    if (fc) fc.checked = true;
    saveConstraints();
}

// ==============================================================================
// SOLVER EXECUTION & RESULTS VISUALIZER
// ==============================================================================

async function generateArrangement() {
    // Show loading state
    const genButtons = [
        document.getElementById("btn-header-generate"),
        document.getElementById("btn-dashboard-generate"),
        document.getElementById("btn-generate-results-tab")
    ];
    genButtons.forEach(b => {
        if (b) {
            b.disabled = true;
            b.dataset.originalHtml = b.innerHTML;
            b.innerHTML = `<span class="spinner"></span> Solving CSP...`;
        }
    });

    try {
        const res = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();
        state.arrangement = data;

        // Switch to the results tab to show visual chart
        switchTab("results");
        renderArrangementResults(data);
        renderStudentsTable();
        await fetchStats();

        if (data.success) {
            showToast("Conflict-free seating arrangement successfully generated!", "success");
        } else {
            showToast(data.reason || "Unable to find valid seating arrangement.", "error");
        }
    } catch (err) {
        showToast("Network error executing CSP solver.", "error");
        console.error("Solver error:", err);
    } finally {
        genButtons.forEach(b => {
            if (b && b.dataset.originalHtml) {
                b.disabled = false;
                b.innerHTML = b.dataset.originalHtml;
            }
        });
    }
}

function renderArrangementResults(res) {
    const statusContent = document.getElementById("results-status-content");
    const container = document.getElementById("seating-chart-container");
    const printMeta = document.getElementById("print-meta-info");

    if (!res) {
        statusContent.innerHTML = `No seating arrangement generated yet.`;
        container.innerHTML = ``;
        return;
    }

    if (printMeta) {
        printMeta.innerHTML = `
            <span>Date: ${new Date().toLocaleDateString()}</span> | 
            <span>Students: ${state.students.length}</span> | 
            <span>Algorithm: CSP Backtracking Search (Steps: ${res.steps || 0}, Time: ${res.time_taken_ms || 0}ms)</span>
        `;
    }

    if (res.success) {
        const mrvActive = res.diagnostics?.mrv_enabled ?? state.config?.use_mrv ?? true;
        const fcActive = res.diagnostics?.forward_checking_enabled ?? state.config?.use_forward_checking ?? true;

        statusContent.innerHTML = `
            <div class="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="badge badge-available">SOLVED SUCCESSFULLY</span>
                        <span class="badge ${mrvActive ? 'badge-available' : 'badge-unavailable'}" title="Minimum Remaining Values variable selection">MRV: ${mrvActive ? 'ON' : 'OFF'}</span>
                        <span class="badge ${fcActive ? 'badge-available' : 'badge-unavailable'}" title="Forward Checking domain pruning">Forward Checking: ${fcActive ? 'ON' : 'OFF'}</span>
                        <strong class="text-slate-800">${escapeHtml(res.reason)}</strong>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">
                        All ${Object.keys(res.assignment || {}).length} students seated. Zero hard constraint violations.
                    </p>
                </div>
                <div class="flex items-center gap-4 text-xs font-mono text-slate-600 flex-wrap">
                    <span title="Recursive Backtracking Steps">Steps: <strong>${res.steps}</strong></span>
                    <span title="Dead-End Backtracks">Backtracks: <strong>${res.backtracks}</strong></span>
                    <span title="Forward Checking Domain Prunes">Prunes: <strong>${res.domain_prunes}</strong></span>
                    <span title="Execution Time">Time: <strong>${res.time_taken_ms} ms</strong></span>
                </div>
            </div>
        `;
    } else {
        // Clear explanation of why it failed
        statusContent.innerHTML = `
            <div>
                <div class="flex items-center gap-2 mb-2">
                    <span class="badge badge-unavailable">CSP SOLVER FAILED</span>
                    <strong class="text-red-700">${escapeHtml(res.status)}</strong>
                </div>
                <div class="notice-box text-sm mb-3" style="background-color: #fef2f2; border-color: #fecaca; color: #991b1b;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <div>
                        <strong>Diagnostic Reason:</strong> ${escapeHtml(res.reason)}
                    </div>
                </div>
                ${res.violations && res.violations.length ? `
                    <div class="mt-2 text-xs text-red-600 space-y-1">
                        <strong>Pre-search check details:</strong>
                        <ul class="list-disc pl-5">
                            ${res.violations.map(v => `<li>${escapeHtml(v)}</li>`).join("")}
                        </ul>
                    </div>
                ` : ''}
                <p class="text-xs text-slate-500 mt-3">
                    <strong>Suggestions:</strong> Increase hall dimensions, add another room, decrease the number of students taking the same exam paper, or ensure sufficient non-adjacent seats are unblocked.
                </p>
            </div>
        `;
    }

    // Build the visual classroom grids room by room
    const rooms = res.rooms || state.rooms;
    const assignment = res.detailed_assignment || {};

    // Group assigned students by room and seat (r, c)
    const seatMap = {}; // roomId -> "r,c" -> studentInfo
    Object.values(assignment).forEach(item => {
        if (!seatMap[item.room_id]) seatMap[item.room_id] = {};
        seatMap[item.room_id][`${item.row},${item.col}`] = item;
    });

    container.innerHTML = rooms.map(room => {
        const unavailSet = new Set(room.unavailable_seats.map(p => `${p[0]},${p[1]}`));
        const placedInRoom = Object.values(assignment).filter(a => a.room_id === room.id);

        let gridHtml = '';
        for (let r = 0; r < room.rows; r++) {
            gridHtml += '<div style="display: flex; gap: 0.65rem; justify-content: center; margin-bottom: 0.65rem;">';
            for (let c = 0; c < room.cols; c++) {
                const coordKey = `${r},${c}`;
                const seatLabel = `R${r+1}C${c+1}`;
                const isBlocked = unavailSet.has(coordKey);
                const student = seatMap[room.id] ? seatMap[room.id][coordKey] : null;

                if (isBlocked) {
                    gridHtml += `
                        <div class="seat-cell unavailable" title="Seat ${seatLabel} is blocked/unavailable">
                            <div class="seat-cell-header">
                                <span class="seat-coord">${seatLabel}</span>
                            </div>
                            <div class="text-center my-auto">
                                <span class="unavail-badge">Blocked</span>
                            </div>
                            <div></div>
                        </div>
                    `;
                } else if (student) {
                    const style = getSubjectStyle(student.subject);
                    gridHtml += `
                        <div class="seat-cell occupied" style="border-left-color: ${style.text}; cursor: pointer;"
                             title="Assigned to ${escapeHtml(student.student_name)} (Click to change seat)"
                             onclick="openReassignModal('${escapeHtml(student.student_id)}')">
                            <div class="seat-cell-header">
                                <span class="seat-coord">${seatLabel}</span>
                                <span class="seat-student-id">${escapeHtml(student.student_id)}</span>
                            </div>
                            <div class="seat-student-name">${escapeHtml(student.student_name)}</div>
                            <div class="seat-subject-pill" style="background-color: ${style.bg}; color: ${style.text}; border: 1px solid ${style.border};" title="${escapeHtml(student.subject)}">
                                ${escapeHtml(student.subject)}
                            </div>
                        </div>
                    `;
                } else {
                    gridHtml += `
                        <div class="seat-cell empty" title="Seat ${seatLabel} is empty">
                            <div class="seat-cell-header" style="width: 100%;">
                                <span class="seat-coord">${seatLabel}</span>
                            </div>
                            <div class="empty-label">Empty</div>
                            <div></div>
                        </div>
                    `;
                }
            }
            gridHtml += '</div>';
        }

        return `
            <div class="room-chart-card">
                <div class="room-chart-header">
                    <div>
                        <h3 class="room-chart-title">${escapeHtml(room.name)}</h3>
                        <span class="text-xs font-mono text-slate-500">Hall ID: ${escapeHtml(room.id)} | Capacity: ${room.available_capacity} usable seats</span>
                    </div>
                    <div class="room-stats-summary">
                        <span>Students Seated: <strong>${placedInRoom.length}</strong> / ${room.available_capacity}</span>
                    </div>
                </div>
                <div class="room-chart-body">
                    <div class="lecturer-board">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                        Lecturer Podium / Front Blackboard
                    </div>
                    <div class="seating-grid-wrapper">
                        ${gridHtml}
                    </div>

                    <!-- Room Legend -->
                    <div class="grid-legend">
                        <div class="legend-item">
                            <span class="legend-swatch swatch-occupied"></span> Occupied (Separated by Subject)
                        </div>
                        <div class="legend-item">
                            <span class="legend-swatch swatch-empty"></span> Empty Available Seat
                        </div>
                        <div class="legend-item">
                            <span class="legend-swatch swatch-unavail"></span> Unavailable / Broken Desk
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

// ==============================================================================
// MODALS & FORMS
// ==============================================================================

function initModals() {
    // Open Student Modal
    document.getElementById("btn-open-add-student").addEventListener("click", () => {
        state.editingStudentId = null;
        document.getElementById("modal-student-title").textContent = "Add Student";
        document.getElementById("form-student").reset();
        document.getElementById("inp-student-id").disabled = false;
        openModal("modal-student");
    });

    // Close Student Modal
    document.getElementById("btn-close-student-modal").addEventListener("click", () => closeModal("modal-student"));
    document.getElementById("btn-cancel-student").addEventListener("click", () => closeModal("modal-student"));

    // Submit Student Form
    document.getElementById("form-student").addEventListener("submit", async (e) => {
        e.preventDefault();
        const sid = document.getElementById("inp-student-id").value.trim();
        const name = document.getElementById("inp-student-name").value.trim();
        const subject = document.getElementById("inp-student-subject").value.trim();

        if (!sid || !name || !subject) {
            showToast("All fields are required.", "error");
            return;
        }

        try {
            let res;
            if (state.editingStudentId) {
                res = await fetch(`/api/students/${encodeURIComponent(state.editingStudentId)}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, subject })
                });
            } else {
                res = await fetch("/api/students", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: sid, name, subject })
                });
            }

            const data = await res.json();
            if (res.ok) {
                showToast(`Student ${sid} saved successfully.`, "success");
                closeModal("modal-student");
                await fetchStudents();
                await fetchStats();
            } else {
                showToast(data.error || "Failed to save student.", "error");
            }
        } catch (err) {
            showToast("Error saving student.", "error");
        }
    });

    // Bulk Import Modal
    document.getElementById("btn-open-bulk-students").addEventListener("click", () => {
        openModal("modal-bulk");
    });
    document.getElementById("btn-close-bulk-modal").addEventListener("click", () => closeModal("modal-bulk"));
    document.getElementById("btn-cancel-bulk").addEventListener("click", () => closeModal("modal-bulk"));

    document.getElementById("form-bulk").addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = document.getElementById("inp-bulk-text").value.trim();
        if (!text) {
            showToast("Please paste student data.", "error");
            return;
        }

        try {
            const res = await fetch("/api/students/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            const data = await res.json();
            if (res.ok) {
                showToast(`Imported ${data.added_count} student(s). Skipped: ${data.skipped_count}`, "success");
                closeModal("modal-bulk");
                document.getElementById("form-bulk").reset();
                await fetchStudents();
                await fetchStats();
            } else {
                showToast(data.error || "Failed to import.", "error");
            }
        } catch (err) {
            showToast("Error importing students.", "error");
        }
    });

    // Room Modal
    document.getElementById("btn-open-add-room").addEventListener("click", () => {
        document.getElementById("form-room").reset();
        openModal("modal-room");
    });
    document.getElementById("btn-close-room-modal").addEventListener("click", () => closeModal("modal-room"));
    document.getElementById("btn-cancel-room").addEventListener("click", () => closeModal("modal-room"));

    document.getElementById("form-room").addEventListener("submit", async (e) => {
        e.preventDefault();
        const rid = document.getElementById("inp-room-id").value.trim();
        const name = document.getElementById("inp-room-name").value.trim();
        const rows = parseInt(document.getElementById("inp-room-rows").value, 10);
        const cols = parseInt(document.getElementById("inp-room-cols").value, 10);

        if (!rid || !name || !rows || !cols) {
            showToast("All room fields are required.", "error");
            return;
        }

        try {
            const res = await fetch("/api/rooms", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: rid, name, rows, cols, unavailable_seats: [] })
            });
            const data = await res.json();
            if (res.ok) {
                showToast(`Room '${rid}' created successfully.`, "success");
                closeModal("modal-room");
                await fetchRooms();
                await fetchStats();
            } else {
                showToast(data.error || "Failed to create room.", "error");
            }
        } catch (err) {
            showToast("Error creating room.", "error");
        }
    });

    // Reassign Modal Listeners
    document.getElementById("btn-close-reassign-modal")?.addEventListener("click", () => closeModal("modal-reassign"));
    document.getElementById("btn-cancel-reassign")?.addEventListener("click", () => closeModal("modal-reassign"));

    document.getElementById("radio-mode-move")?.addEventListener("change", () => {
        document.getElementById("reassign-move-section").style.display = "block";
        document.getElementById("reassign-swap-section").style.display = "none";
    });
    document.getElementById("radio-mode-swap")?.addEventListener("change", () => {
        document.getElementById("reassign-move-section").style.display = "none";
        document.getElementById("reassign-swap-section").style.display = "block";
    });

    document.getElementById("sel-reassign-room")?.addEventListener("change", updateReassignSeatDropdown);

    document.getElementById("form-reassign")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const errContainer = document.getElementById("reassign-error-container");
        errContainer.style.display = "none";
        errContainer.innerHTML = "";

        const isSwap = document.getElementById("radio-mode-swap").checked;
        let target_room_id, target_row, target_col;

        if (isSwap) {
            const swapSid = document.getElementById("sel-reassign-student").value;
            const targetStudent = state.arrangement && state.arrangement.detailed_assignment
                ? state.arrangement.detailed_assignment[swapSid]
                : null;
            if (!targetStudent) {
                showToast("Please select a student to swap with.", "error");
                return;
            }
            target_room_id = targetStudent.room_id;
            target_row = targetStudent.row;
            target_col = targetStudent.col;
        } else {
            target_room_id = document.getElementById("sel-reassign-room").value;
            const seatVal = document.getElementById("sel-reassign-seat").value;
            if (!seatVal) {
                showToast("Please select a seat.", "error");
                return;
            }
            const parts = seatVal.split(",");
            target_row = parseInt(parts[0], 10);
            target_col = parseInt(parts[1], 10);
        }

        const btnSave = document.getElementById("btn-save-reassign");
        btnSave.disabled = true;
        btnSave.textContent = "Checking Constraints...";

        try {
            const res = await fetch("/api/reassign-seat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_id: state.reassigningStudentId,
                    target_room_id,
                    target_row,
                    target_col
                })
            });

            const data = await res.json();
            if (res.ok && data.success) {
                showToast(data.message, "success");
                state.arrangement = data.arrangement;
                closeModal("modal-reassign");
                renderStudentsTable();
                renderArrangementResults(state.arrangement);
                await fetchStats();
            } else {
                errContainer.style.display = "block";
                errContainer.innerHTML = `
                    <div style="font-weight: 600; margin-bottom: 0.25rem;">Constraint Violation Detected:</div>
                    <div>${escapeHtml(data.error || "Cannot place student here due to constraint violation.")}</div>
                    ${data.violations ? `<ul style="margin-top: 0.35rem; padding-left: 1.25rem; font-size: 0.8rem;">${data.violations.map(v => `<li>${escapeHtml(v)}</li>`).join("")}</ul>` : ''}
                `;
            }
        } catch (err) {
            showToast("Network error checking constraints.", "error");
        } finally {
            btnSave.disabled = false;
            btnSave.textContent = "Verify & Apply Change";
        }
    });
}

function openReassignModal(studentId) {
    if (!state.arrangement || !state.arrangement.detailed_assignment) {
        showToast("Please generate a seating arrangement first.", "error");
        return;
    }

    const assigned = state.arrangement.detailed_assignment[studentId];
    if (!assigned) {
        showToast("This student is not assigned to any seat.", "error");
        return;
    }

    const student = state.students.find(s => s.id === studentId);
    state.reassigningStudentId = studentId;

    // Reset error container
    const errContainer = document.getElementById("reassign-error-container");
    errContainer.style.display = "none";
    errContainer.innerHTML = "";

    // Populate student summary
    const style = getSubjectStyle(student ? student.subject : assigned.subject);
    document.getElementById("reassign-student-info").innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <div>
                <strong class="text-slate-900">${escapeHtml(assigned.student_name)}</strong>
                <span class="font-mono text-xs text-slate-500 ml-1">(${escapeHtml(studentId)})</span>
                <div class="mt-1">
                    <span class="badge badge-subject" style="background-color: ${style.bg}; color: ${style.text}; border-color: ${style.border}">
                        ${escapeHtml(assigned.subject)}
                    </span>
                </div>
            </div>
            <div style="text-align: right;">
                <span class="text-xs text-slate-500 block">Current Seat</span>
                <span class="badge badge-seat-assigned font-mono mt-1">
                    ${escapeHtml(assigned.room_id)} · ${escapeHtml(assigned.label)}
                </span>
            </div>
        </div>
    `;

    // Populate Room dropdown
    const roomSelect = document.getElementById("sel-reassign-room");
    roomSelect.innerHTML = state.rooms.map(r => `
        <option value="${escapeHtml(r.id)}" ${r.id === assigned.room_id ? 'selected' : ''}>
            ${escapeHtml(r.name)} (${r.rows}x${r.cols})
        </option>
    `).join("");

    // Populate Seat dropdown for currently selected room
    updateReassignSeatDropdown();

    // Populate Swap Student dropdown
    const swapSelect = document.getElementById("sel-reassign-student");
    const otherStudents = Object.values(state.arrangement.detailed_assignment).filter(a => a.student_id !== studentId);
    swapSelect.innerHTML = otherStudents.map(o => `
        <option value="${escapeHtml(o.student_id)}">
            ${escapeHtml(o.student_name)} (${escapeHtml(o.student_id)}) - ${escapeHtml(o.subject)} [${escapeHtml(o.room_id)} · ${escapeHtml(o.label)}]
        </option>
    `).join("");

    // Reset mode to 'move'
    document.getElementById("radio-mode-move").checked = true;
    document.getElementById("reassign-move-section").style.display = "block";
    document.getElementById("reassign-swap-section").style.display = "none";

    openModal("modal-reassign");
}

function updateReassignSeatDropdown() {
    const roomId = document.getElementById("sel-reassign-room").value;
    const room = state.rooms.find(r => r.id === roomId);
    const seatSelect = document.getElementById("sel-reassign-seat");
    if (!room) {
        seatSelect.innerHTML = `<option value="">No seats found</option>`;
        return;
    }

    const unavailSet = new Set(room.unavailable_seats.map(p => `${p[0]},${p[1]}`));
    const occupiedMap = {};
    if (state.arrangement && state.arrangement.detailed_assignment) {
        Object.values(state.arrangement.detailed_assignment).forEach(a => {
            if (a.room_id === roomId) {
                occupiedMap[`${a.row},${a.col}`] = a;
            }
        });
    }

    let options = [];
    for (let r = 0; r < room.rows; r++) {
        for (let c = 0; c < room.cols; c++) {
            const key = `${r},${c}`;
            const label = `R${r+1}C${c+1}`;
            if (unavailSet.has(key)) {
                continue;
            }

            const occupant = occupiedMap[key];
            if (occupant) {
                if (occupant.student_id === state.reassigningStudentId) {
                    options.push(`<option value="${r},${c}" selected>${label} (Current Seat)</option>`);
                } else {
                    options.push(`<option value="${r},${c}">${label} (Occupied by ${escapeHtml(occupant.student_name)} - ${escapeHtml(occupant.subject)})</option>`);
                }
            } else {
                options.push(`<option value="${r},${c}">${label} (Available / Empty)</option>`);
            }
        }
    }

    seatSelect.innerHTML = options.join("");
}

function openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add("show");
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove("show");
}

// ==============================================================================
// SAMPLE DATA & RESET ACTIONS
// ==============================================================================

async function loadSampleData() {
    try {
        const res = await fetch("/api/load-sample", { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showToast("Loaded sample college exam dataset (24 students, 2 rooms).", "success");
            await refreshAllData();
            switchTab("dashboard");
        } else {
            showToast("Failed to load sample data.", "error");
        }
    } catch (err) {
        showToast("Error loading sample data.", "error");
    }
}

async function resetAllData() {
    if (!confirm("Are you sure you want to completely clear ALL students, rooms, and arrangements?")) return;
    try {
        const res = await fetch("/api/reset-all", { method: "POST" });
        if (res.ok) {
            showToast("All data cleared successfully.", "info");
            state.arrangement = null;
            await refreshAllData();
            renderArrangementResults(null);
            switchTab("dashboard");
        }
    } catch (err) {
        showToast("Error clearing data.", "error");
    }
}
