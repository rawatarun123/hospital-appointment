# ============================================================
#  auth.py — User Authentication & Role Management
#  Roles: admin, doctor, patient
# ============================================================

import hashlib, jwt
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from backend.excel_db import read, write, next_id, now, F_USERS, H_USERS

auth_bp = Blueprint("auth", __name__)
SECRET  = "haso_secret_2026"


# ── Helpers ───────────────────────────────────────────────
def sha(p): return hashlib.sha256(p.encode()).hexdigest()

def make_token(user):
    return jwt.encode(
        {"id": user["ID"], "username": user["Username"],
         "role": user["Role"], "name": user["Name"],
         "exp": datetime.utcnow() + timedelta(hours=10)},
        SECRET, algorithm="HS256"
    )

def decode_token(token):
    return jwt.decode(token, SECRET, algorithms=["HS256"])


# ── Auth decorators ────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        token = request.headers.get("Authorization","").replace("Bearer ","")
        if not token:
            return jsonify({"error": "Login required"}), 401
        try:
            request.user = decode_token(token)
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return f(*a, **kw)
    return wrap


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrap(*a, **kw):
            if request.user.get("role") not in roles:
                return jsonify({"error": f"Access denied. Required: {roles}"}), 403
            return f(*a, **kw)
        return wrap
    return decorator


# ── Routes ────────────────────────────────────────────────
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    d     = request.get_json()
    users = read(F_USERS)
    user  = next((u for u in users
                  if u["Username"] == d.get("username","").strip().lower()
                  and u["Status"] == "active"), None)
    if not user or user["Password"] != sha(d.get("password","")):
        return jsonify({"error": "Wrong username or password"}), 401
    return jsonify({
        "token": make_token(user),
        "user":  {"id":user["ID"],"name":user["Name"],
                  "role":user["Role"],"username":user["Username"]}
    })


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    """Public registration — creates a patient account."""
    d     = request.get_json()
    users = read(F_USERS)
    if any(u["Username"] == d.get("username","").lower() for u in users):
        return jsonify({"error": "Username already exists"}), 400

    from backend.patients import create_patient_record
    new_id = next_id(users)
    users.append({
        "ID": new_id, "Username": d["username"].lower(),
        "Password": sha(d["password"]), "Role": "patient",
        "Name": d["name"], "Email": d.get("email",""),
        "Phone": d.get("phone",""), "Status": "active", "Created_At": now()
    })
    write(F_USERS, H_USERS, users)
    create_patient_record(new_id, d)
    return jsonify({"message": "Account created. Please log in."}), 201


@auth_bp.route("/api/auth/me")
@login_required
def me():
    return jsonify({"user": request.user})


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    d     = request.get_json()
    users = read(F_USERS)
    for u in users:
        if u["ID"] == request.user["id"]:
            if u["Password"] != sha(d.get("old_password","")):
                return jsonify({"error": "Old password incorrect"}), 400
            u["Password"] = sha(d["new_password"])
            break
    write(F_USERS, H_USERS, users)
    return jsonify({"message": "Password changed"})


# ── Admin: manage all users ───────────────────────────────
@auth_bp.route("/api/admin/users")
@login_required
@role_required("admin")
def get_users():
    users = read(F_USERS)
    for u in users: u.pop("Password", None)   # never expose hash
    return jsonify(users)


@auth_bp.route("/api/admin/users/<int:uid>", methods=["PUT"])
@login_required
@role_required("admin")
def update_user(uid):
    d     = request.get_json()
    users = read(F_USERS)
    for u in users:
        if int(u.get("ID") or 0) == uid:
            u["Status"] = d.get("status", u["Status"])
            u["Role"]   = d.get("role",   u["Role"])
            break
    write(F_USERS, H_USERS, users)
    return jsonify({"message": "Updated"})
