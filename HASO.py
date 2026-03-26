# ============================================================
#  HASO.py — Hospital Appointment Scheduling Optimizer
# ============================================================

from flask import Flask, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="frontend")
CORS(app)

# ── Register all blueprints ────────────────────────────────
from backend.auth         import auth_bp
from backend.doctors      import doctors_bp
from backend.patients     import patients_bp
from backend.scheduler    import scheduler_bp
from backend.appointments import appointments_bp
from backend.analytics    import analytics_bp

app.register_blueprint(auth_bp)
app.register_blueprint(doctors_bp)
app.register_blueprint(patients_bp)
app.register_blueprint(scheduler_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(analytics_bp)

# ── Serve frontend ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("frontend", path)

# ── Start ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("   H A S O  —  Hospital Appointment Optimizer")
    print("=" * 55)

    # Auto-create Excel files on first run
    from backend.excel_db import setup_all
    print("\n  Initializing Excel storage files…")
    setup_all()

    print("\n  Modules loaded:")
    print("    ✓ auth.py         — Authentication & Role Management")
    print("    ✓ doctors.py      — Doctor Management")
    print("    ✓ patients.py     — Patient Management")
    print("    ✓ scheduler.py    — DAA Scheduling Engine")
    print("    ✓ appointments.py — Booking & Conflict Handling")
    print("    ✓ analytics.py    — Analytics Dashboard")
    print("\n  🌐  Open: http://localhost:5000")
    print("  🔑  Admin:   admin   / admin123")
    print("  👨‍⚕️  Doctor:  drpatel / doc123")
    print("  🧑  Patient: alice   / pat123")
    print("\n  Press Ctrl+C to stop.\n")

    app.run(debug=True, port=5000)
