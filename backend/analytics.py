# ============================================================
#  analytics.py — Analytics Dashboard
# ============================================================

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, date
from backend.excel_db import read, F_APPTS, F_DOCTORS, F_PATIENTS, F_USERS
from backend.auth import login_required, role_required
from collections import Counter

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/api/analytics/overview")
@login_required
@role_required("admin")
def overview():
    appts   = read(F_APPTS)
    doctors = read(F_DOCTORS)
    patients= read(F_PATIENTS)
    today   = str(date.today())

    return jsonify({
        "total_appointments": len(appts),
        "booked":    sum(1 for a in appts if a.get("Status") == "booked"),
        "completed": sum(1 for a in appts if a.get("Status") == "completed"),
        "cancelled": sum(1 for a in appts if a.get("Status") == "cancelled"),
        "today":     sum(1 for a in appts if str(a.get("Appt_Date",""))[:10] == today
                         and a.get("Status") == "booked"),
        "total_doctors":   len([d for d in doctors  if d.get("Status") == "available"]),
        "total_patients":  len(patients),
        "high_urgency":    sum(1 for a in appts if int(a.get("Urgency") or 0) == 3
                               and a.get("Status") == "booked"),
    })


@analytics_bp.route("/api/analytics/by-specialty")
@login_required
@role_required("admin")
def by_specialty():
    appts = read(F_APPTS)
    count = Counter(a.get("Specialty","Unknown") for a in appts)
    return jsonify([{"specialty": k, "count": v} for k, v in count.most_common()])


@analytics_bp.route("/api/analytics/by-urgency")
@login_required
@role_required("admin")
def by_urgency():
    appts  = read(F_APPTS)
    labels = {1:"Low", 2:"Medium", 3:"High"}
    count  = Counter(int(a.get("Urgency") or 1) for a in appts)
    return jsonify([{"urgency": labels.get(k,str(k)), "level": k, "count": v}
                    for k, v in sorted(count.items())])


@analytics_bp.route("/api/analytics/by-day")
@login_required
@role_required("admin")
def by_day():
    """Appointments per day for the last 14 days."""
    appts = read(F_APPTS)
    today = date.today()
    days  = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    count = Counter(str(a.get("Appt_Date",""))[:10] for a in appts)
    return jsonify([{"date": d, "count": count.get(d, 0)} for d in days])


@analytics_bp.route("/api/analytics/top-doctors")
@login_required
@role_required("admin")
def top_doctors():
    appts = read(F_APPTS)
    count = Counter(a.get("Doctor_Name","") for a in appts if a.get("Doctor_Name"))
    return jsonify([{"doctor": k, "count": v} for k, v in count.most_common(5)])


@analytics_bp.route("/api/analytics/priority-distribution")
@login_required
@role_required("admin")
def priority_dist():
    """Distribution of priority scores 1–10."""
    appts = read(F_APPTS)
    count = Counter(int(a.get("Priority") or 5) for a in appts)
    return jsonify([{"priority": i, "count": count.get(i, 0)} for i in range(1, 11)])
