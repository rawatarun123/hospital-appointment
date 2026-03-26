# ============================================================
#  appointments.py — Appointment Booking & Conflict Handling
# ============================================================

from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.excel_db import read, write, next_id, now, F_APPTS, H_APPTS, F_DOCTORS, F_PATIENTS
from backend.auth import login_required, role_required
from backend.scheduler import score_symptoms, compute_priority, assign_best_slot

appointments_bp = Blueprint("appointments", __name__)


def _serialize(appts):
    for a in appts:
        if a.get("Appt_Date"):
            a["Appt_Date"] = str(a["Appt_Date"])[:10]
    return appts


@appointments_bp.route("/api/book", methods=["POST"])
def book():
    """
    Public booking endpoint.
    DAA engine auto-assigns time based on symptoms.
    """
    d = request.get_json()
    for f in ["patient_name","patient_phone","symptoms","doctor_id","appt_date"]:
        if not d.get(f):
            return jsonify({"error": f"Missing field: {f}"}), 400

    did  = str(d["doctor_id"])
    date = str(d["appt_date"])
    age  = d.get("patient_age") or d.get("age")

    # Verify doctor is available
    docs   = read(F_DOCTORS)
    doctor = next((doc for doc in docs
                   if str(doc.get("ID","")) == did and doc.get("Status") == "available"), None)
    if not doctor:
        return jsonify({"error": "Doctor not available"}), 400

    # Conflict check: prevent duplicate booking for same patient+doctor+date
    existing = read(F_APPTS)
    duplicate = next((a for a in existing
                      if str(a.get("Doctor_ID","")) == did
                      and str(a.get("Appt_Date",""))[:10] == date
                      and str(a.get("Patient_Phone","")).strip() == str(d["patient_phone"]).strip()
                      and a.get("Status") not in ("cancelled",)), None)
    if duplicate:
        return jsonify({
            "error": f"You already have an appointment with this doctor on {date} at {duplicate['Appt_Time']}."
        }), 409

    # DAA: run scheduling engine
    urgency  = score_symptoms(d["symptoms"])
    priority = compute_priority(urgency, age)
    slot     = assign_best_slot(did, date, urgency)

    if not slot:
        return jsonify({"error": "No slots available on this date. Try another date or doctor."}), 400

    # Find or create patient record
    patients  = read(F_PATIENTS)
    patient   = next((p for p in patients
                      if str(p.get("Phone","")).strip() == str(d["patient_phone"]).strip()), None)
    patient_id = patient["ID"] if patient else None

    new_appt = {
        "ID":             next_id(existing),
        "Patient_ID":     patient_id,
        "Patient_Name":   d["patient_name"],
        "Patient_Phone":  d["patient_phone"],
        "Doctor_ID":      did,
        "Doctor_Name":    doctor["Name"],
        "Specialty":      doctor["Specialization"],
        "Symptoms":       d["symptoms"],
        "Urgency":        urgency,
        "Appt_Date":      date,
        "Appt_Time":      slot,
        "Priority":       priority,
        "Status":         "booked",
        "Notes":          d.get("notes",""),
        "Created_At":     now()
    }
    existing.append(new_appt)
    write(F_APPTS, H_APPTS, existing)

    labels = {1:"Low", 2:"Medium", 3:"High"}
    return jsonify({
        "id":       new_appt["ID"],
        "doctor":   doctor["Name"],
        "specialty":doctor["Specialization"],
        "date":     date,
        "time":     slot,
        "urgency":  labels[urgency],
        "priority": priority,
        "message":  "Appointment booked successfully!"
    }), 201


@appointments_bp.route("/api/appointments/check")
def check_by_phone():
    phone  = request.args.get("phone","").strip()
    if not phone: return jsonify({"error": "Phone required"}), 400
    appts  = read(F_APPTS)
    result = sorted(
        [{"id":a["ID"],"doctor_name":a["Doctor_Name"],"specialty":a["Specialty"],
          "appt_date":str(a.get("Appt_Date",""))[:10],"appt_time":a["Appt_Time"],
          "urgency":a.get("Urgency",1),"priority":a.get("Priority",5),
          "status":a["Status"],"symptoms":a.get("Symptoms","")}
         for a in appts if str(a.get("Patient_Phone","")).strip() == phone],
        key=lambda x:(x["appt_date"],x["appt_time"])
    )
    return jsonify(result)


@appointments_bp.route("/api/appointments/<int:aid>/cancel", methods=["POST"])
def cancel(aid):
    appts = read(F_APPTS)
    for a in appts:
        if int(a.get("ID") or 0) == aid:
            a["Status"] = "cancelled"; break
    write(F_APPTS, H_APPTS, appts)
    return jsonify({"message": "Appointment cancelled"})


# ── Admin & Doctor routes ─────────────────────────────────
@appointments_bp.route("/api/admin/appointments")
@login_required
@role_required("admin", "doctor")
def admin_list():
    appts = read(F_APPTS)
    df    = request.args.get("date")
    dr    = request.args.get("doctor_id")
    st    = request.args.get("status")
    if df: appts = [a for a in appts if str(a.get("Appt_Date",""))[:10] == df]
    if dr: appts = [a for a in appts if str(a.get("Doctor_ID","")) == dr]
    if st: appts = [a for a in appts if a.get("Status") == st]
    appts.sort(key=lambda x: (-(int(x.get("Priority") or 0)), str(x.get("Appt_Time",""))))
    return jsonify(_serialize(appts))


@appointments_bp.route("/api/admin/appointments/<int:aid>", methods=["PUT"])
@login_required
@role_required("admin", "doctor")
def update_appt(aid):
    d     = request.get_json()
    appts = read(F_APPTS)
    for a in appts:
        if int(a.get("ID") or 0) == aid:
            if "status" in d: a["Status"] = d["status"]
            if "notes"  in d: a["Notes"]  = d["notes"]
            break
    write(F_APPTS, H_APPTS, appts)
    return jsonify({"message": "Updated"})


@appointments_bp.route("/api/admin/appointments/<int:aid>", methods=["DELETE"])
@login_required
@role_required("admin")
def delete_appt(aid):
    appts = [a for a in read(F_APPTS) if int(a.get("ID") or 0) != aid]
    write(F_APPTS, H_APPTS, appts)
    return jsonify({"message": "Deleted"})
