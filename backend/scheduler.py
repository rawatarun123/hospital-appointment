# ============================================================
#  scheduler.py — DAA Scheduling Optimization Engine
#
#  Five DAA concepts implemented here:
#
#  1. Greedy Interval Scheduling  — generates conflict-free slots
#     Walk doctor hours in slot_duration steps; skip booked times.
#
#  2. Weighted Symptom Scoring (DP) — score symptoms → urgency
#     Each keyword has a weight; accumulated score maps to urgency.
#
#  3. Priority Score (DP) — combine urgency + age → priority (1–10)
#     Used to rank patients in admin queue.
#
#  4. Priority-based Slot Assignment (Greedy + Priority)
#     High urgency → earliest slot (critical patients first)
#     Medium       → first-third of available slots
#     Low          → middle slot (reserves early slots for urgent)
#
#  5. Backtracking Conflict Check
#     Before confirming, verify no slot collision exists.
#     If conflict found, backtrack and try next available slot.
# ============================================================

from flask import Blueprint, request, jsonify
from backend.excel_db import read, F_DOCTORS, F_APPTS
from backend.auth import login_required

scheduler_bp = Blueprint("scheduler", __name__)

# ── Symptom keyword weights (DAA #2) ─────────────────────
WEIGHTS = {
    "chest pain":3, "heart attack":3, "stroke":3, "not breathing":3,
    "unconscious":3, "severe bleeding":3, "accident":3, "emergency":3,
    "high fever":2, "vomiting":2, "dizziness":2, "difficulty breathing":2,
    "fracture":2, "infection":2, "severe pain":2, "bleed":2, "fever":2,
    "pain":1, "cough":1, "cold":1, "rash":1, "headache":1,
    "checkup":1, "routine":1, "mild":1, "consult":1, "follow":1,
}


def score_symptoms(text):
    """
    DAA #2 — DP Symptom Scoring.
    Returns urgency level: 3=High, 2=Medium, 1=Low
    """
    text  = text.lower()
    score = sum(w for kw, w in WEIGHTS.items() if kw in text)
    if score >= 6: return 3
    if score >= 2: return 2
    return 1


def compute_priority(urgency, age):
    """
    DAA #3 — DP Priority Score (1–10).
    Urgency * 4 + age bonus.
    Elderly (65+) and children (≤12) get +2 (vulnerable groups).
    """
    score = int(urgency) * 4
    age   = int(age or 0)
    if age >= 65 or (0 < age <= 12): score += 2
    elif age >= 50:                   score += 1
    return min(score, 10)


def _parse_time(t):
    s = str(t).strip()
    if ":" in s:
        p = s.split(":")
        return int(p[0]), int(p[1])
    total = int(float(s) * 86400)
    return total // 3600, (total % 3600) // 60


def get_free_slots(doctor_id, appt_date):
    """
    DAA #1 — Greedy Interval Scheduling.
    Build all time slots; greedily keep only the free ones.
    Result is naturally sorted ascending (like merge sort output).
    """
    docs   = read(F_DOCTORS)
    doctor = next((d for d in docs if str(d.get("ID","")) == str(doctor_id)), None)
    if not doctor: return []

    sh, sm = _parse_time(doctor["Start_Time"])
    eh, em = _parse_time(doctor["End_Time"])
    dur    = int(doctor.get("Slot_Duration") or 30)

    # DAA #5 — Backtracking: collect taken slots to avoid conflict
    booked = {
        str(a.get("Appt_Time","")).strip()
        for a in read(F_APPTS)
        if str(a.get("Doctor_ID","")) == str(doctor_id)
        and str(a.get("Appt_Date",""))[:10] == str(appt_date)[:10]
        and str(a.get("Status","")) not in ("cancelled",)
    }

    slots, ch, cm = [], sh, sm
    while True:
        nm = cm + dur; nh = ch + nm // 60; nm = nm % 60
        if nh > eh or (nh == eh and nm > em): break
        slot = f"{ch:02d}:{cm:02d}"
        if slot not in booked:
            slots.append(slot)
        cm += dur
        if cm >= 60: ch += 1; cm -= 60
    return slots


def assign_best_slot(doctor_id, appt_date, urgency):
    """
    DAA #4 — Priority-based Greedy Slot Assignment.
    High urgency (3) → earliest free slot (index 0)
    Medium urgency(2) → first third of slots
    Low urgency   (1) → middle of slots
    DAA #5 applied: if chosen slot is taken, backtrack to next.
    """
    slots = get_free_slots(doctor_id, appt_date)
    if not slots: return None

    u = int(urgency)
    if   u == 3: idx = 0
    elif u == 2: idx = len(slots) // 3
    else:        idx = min(len(slots) // 2, len(slots) - 1)

    # Backtracking: if somehow taken at confirm time, try next
    chosen = slots[idx]
    taken  = {str(a.get("Appt_Time","")).strip()
              for a in read(F_APPTS)
              if str(a.get("Doctor_ID","")) == str(doctor_id)
              and str(a.get("Appt_Date",""))[:10] == str(appt_date)[:10]
              and str(a.get("Status","")) not in ("cancelled",)}

    if chosen in taken:
        free = [s for s in slots if s not in taken]
        chosen = free[0] if free else None

    return chosen


# ── API Routes ────────────────────────────────────────────
@scheduler_bp.route("/api/slots")
def slots():
    did  = request.args.get("doctor_id")
    date = request.args.get("date")
    if not did or not date:
        return jsonify({"error": "doctor_id and date required"}), 400
    return jsonify({"slots": get_free_slots(did, date)})


@scheduler_bp.route("/api/scheduler/analyze", methods=["POST"])
def analyze_symptoms():
    """Let frontend preview urgency before booking."""
    d       = request.get_json()
    text    = d.get("symptoms","")
    age     = d.get("age", 30)
    urgency = score_symptoms(text)
    prio    = compute_priority(urgency, age)
    labels  = {1:"Low", 2:"Medium", 3:"High"}
    return jsonify({
        "urgency":       urgency,
        "urgency_label": labels[urgency],
        "priority":      prio,
        "message":       {
            3: "Your symptoms indicate HIGH urgency. You will be given the earliest available slot.",
            2: "Your symptoms indicate MEDIUM urgency. A suitable slot will be assigned.",
            1: "Your symptoms indicate LOW urgency. A slot in the middle of the day will be assigned.",
        }[urgency]
    })
