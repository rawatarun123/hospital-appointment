# ============================================================
#  patients.py — Patient Management
# ============================================================

from flask import Blueprint, request, jsonify
from backend.excel_db import read, write, next_id, now, F_PATIENTS, H_PATIENTS, F_APPTS
from backend.auth import login_required, role_required

patients_bp = Blueprint("patients", __name__)


def create_patient_record(user_id, data):
    """Called after registration to create patient profile."""
    patients = read(F_PATIENTS)
    patients.append({
        "ID": next_id(patients), "User_ID": user_id,
        "Name": data.get("name",""), "Age": data.get("age"),
        "Phone": data.get("phone",""), "Email": data.get("email",""),
        "Blood_Group": data.get("blood_group",""), "Medical_History": "",
        "Status": "active", "Created_At": now()
    })
    write(F_PATIENTS, H_PATIENTS, patients)


@patients_bp.route("/api/admin/patients")
@login_required
@role_required("admin", "doctor")
def list_patients():
    return jsonify(read(F_PATIENTS))


@patients_bp.route("/api/admin/patients/<int:pid>")
@login_required
@role_required("admin", "doctor")
def get_patient(pid):
    patients = read(F_PATIENTS)
    patient  = next((p for p in patients if int(p.get("ID") or 0) == pid), None)
    if not patient: return jsonify({"error": "Not found"}), 404

    appts = read(F_APPTS)
    patient["appointments"] = [
        {"id":a["ID"],"doctor":a["Doctor_Name"],"date":str(a.get("Appt_Date",""))[:10],
         "time":a["Appt_Time"],"status":a["Status"]}
        for a in appts if str(a.get("Patient_ID","")) == str(pid)
    ]
    return jsonify(patient)


@patients_bp.route("/api/admin/patients/<int:pid>", methods=["PUT"])
@login_required
@role_required("admin")
def update_patient(pid):
    d        = request.get_json()
    patients = read(F_PATIENTS)
    for p in patients:
        if int(p.get("ID") or 0) == pid:
            for field in ["Status","Medical_History","Blood_Group"]:
                if field in d: p[field] = d[field]
            break
    write(F_PATIENTS, H_PATIENTS, patients)
    return jsonify({"message": "Updated"})


# Patient self-profile
@patients_bp.route("/api/patient/profile")
@login_required
@role_required("patient","admin")
def patient_profile():
    uid      = request.user["id"]
    patients = read(F_PATIENTS)
    patient  = next((p for p in patients if str(p.get("User_ID","")) == str(uid)), None)
    if not patient: return jsonify({"error": "Profile not found"}), 404
    return jsonify(patient)


@patients_bp.route("/api/patient/profile", methods=["PUT"])
@login_required
@role_required("patient")
def update_own_profile():
    d        = request.get_json()
    uid      = request.user["id"]
    patients = read(F_PATIENTS)
    for p in patients:
        if str(p.get("User_ID","")) == str(uid):
            for field in ["Age","Phone","Email","Blood_Group","Medical_History"]:
                if field in d: p[field] = d[field]
            break
    write(F_PATIENTS, H_PATIENTS, patients)
    return jsonify({"message": "Profile updated"})


@patients_bp.route("/api/patient/appointments")
@login_required
@role_required("patient","admin")
def patient_appointments():
    uid      = request.user["id"]
    patients = read(F_PATIENTS)
    patient  = next((p for p in patients if str(p.get("User_ID","")) == str(uid)), None)
    if not patient: return jsonify([])

    appts  = read(F_APPTS)
    result = [a for a in appts if str(a.get("Patient_ID","")) == str(patient["ID"])]
    for a in result: a["Appt_Date"] = str(a.get("Appt_Date",""))[:10]
    result.sort(key=lambda x: (x["Appt_Date"], str(x.get("Appt_Time",""))))
    return jsonify(result)
