# ============================================================
#  doctors.py — Doctor Management
# ============================================================

from flask import Blueprint, request, jsonify
from backend.excel_db import read, write, next_id, now, F_DOCTORS, H_DOCTORS, F_APPTS
from backend.auth import login_required, role_required

doctors_bp = Blueprint("doctors", __name__)


def get_all_doctors():
    docs = read(F_DOCTORS)
    for d in docs:
        d["Start_Time"] = str(d.get("Start_Time",""))
        d["End_Time"]   = str(d.get("End_Time",""))
    return docs


@doctors_bp.route("/api/doctors")
def list_doctors():
    spec   = request.args.get("specialty")
    status = request.args.get("status", "available")
    docs   = get_all_doctors()
    result = [d for d in docs if (not status or d.get("Status") == status)
              and (not spec or d.get("Specialization") == spec)]
    return jsonify(result)


@doctors_bp.route("/api/doctors/<int:did>")
def get_doctor(did):
    doc = next((d for d in get_all_doctors() if int(d.get("ID") or 0) == did), None)
    if not doc:
        return jsonify({"error": "Doctor not found"}), 404

    # Attach today's appointment count
    appts = read(F_APPTS)
    from datetime import date
    today = str(date.today())
    doc["today_count"] = sum(
        1 for a in appts
        if str(a.get("Doctor_ID","")) == str(did)
        and str(a.get("Appt_Date",""))[:10] == today
        and a.get("Status") == "booked"
    )
    return jsonify(doc)


@doctors_bp.route("/api/specialties")
def specialties():
    docs  = read(F_DOCTORS)
    specs = sorted({d["Specialization"] for d in docs if d.get("Status") == "available"})
    return jsonify(specs)


@doctors_bp.route("/api/admin/doctors", methods=["POST"])
@login_required
@role_required("admin")
def add_doctor():
    d    = request.get_json()
    docs = read(F_DOCTORS)
    docs.append({
        "ID": next_id(docs), "User_ID": None,
        "Name": d["name"], "Specialization": d["specialization"],
        "Start_Time": d.get("start_time","09:00"),
        "End_Time":   d.get("end_time","17:00"),
        "Slot_Duration": int(d.get("slot_duration",30)),
        "Experience": d.get("experience", 0),
        "Fee": d.get("fee", 300),
        "Status": "available", "Created_At": now()
    })
    write(F_DOCTORS, H_DOCTORS, docs)
    return jsonify({"message": "Doctor added"}), 201


@doctors_bp.route("/api/admin/doctors/<int:did>", methods=["PUT"])
@login_required
@role_required("admin")
def update_doctor(did):
    d    = request.get_json()
    docs = read(F_DOCTORS)
    for doc in docs:
        if int(doc.get("ID") or 0) == did:
            for field in ["Status","Name","Specialization","Start_Time",
                          "End_Time","Slot_Duration","Experience","Fee"]:
                if field in d: doc[field] = d[field]
            break
    write(F_DOCTORS, H_DOCTORS, docs)
    return jsonify({"message": "Updated"})


@doctors_bp.route("/api/admin/doctors/<int:did>", methods=["DELETE"])
@login_required
@role_required("admin")
def remove_doctor(did):
    docs = read(F_DOCTORS)
    for doc in docs:
        if int(doc.get("ID") or 0) == did:
            doc["Status"] = "removed"; break
    write(F_DOCTORS, H_DOCTORS, docs)
    return jsonify({"message": "Doctor removed"})


# Doctor portal — own profile
@doctors_bp.route("/api/doctor/profile")
@login_required
@role_required("doctor","admin")
def doctor_profile():
    uid  = request.user["id"]
    docs = get_all_doctors()
    doc  = next((d for d in docs if str(d.get("User_ID","")) == str(uid)), None)
    if not doc:
        return jsonify({"error": "Doctor profile not found"}), 404
    appts = read(F_APPTS)
    doc["total_patients"] = len({a["Patient_ID"] for a in appts if str(a.get("Doctor_ID","")) == str(doc["ID"])})
    return jsonify(doc)


@doctors_bp.route("/api/doctor/appointments")
@login_required
@role_required("doctor","admin")
def doctor_appointments():
    uid   = request.user["id"]
    docs  = read(F_DOCTORS)
    doc   = next((d for d in docs if str(d.get("User_ID","")) == str(uid)), None)
    if not doc: return jsonify([])
    did   = str(doc["ID"])
    appts = read(F_APPTS)
    df    = request.args.get("date")
    result = [a for a in appts if str(a.get("Doctor_ID","")) == did
              and (not df or str(a.get("Appt_Date",""))[:10] == df)]
    for a in result: a["Appt_Date"] = str(a.get("Appt_Date",""))[:10]
    result.sort(key=lambda x: (x["Appt_Date"], str(x.get("Appt_Time",""))))
    return jsonify(result)
