from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime, timedelta, timezone
import os, json, random, hashlib
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = "tesmit5302!"

# =========================
# CONFIG
# =========================
KKM = 60
MAX_ATTEMPT_GAGAL = 2
WITA = timezone(timedelta(hours=8))

# =========================
# GOOGLE SHEETS
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_key("1UaKV5QPMtk_YW_5aRWzoyy5s2w8Xq0Hf43L5iw88Dd0")

sheet_peserta = spreadsheet.worksheet("Peserta")
sheet_soal = spreadsheet.worksheet("Soal")
sheet_jawaban = spreadsheet.worksheet("Jawaban")
sheet_status = spreadsheet.worksheet("StatusUser")

# =========================
# MEMORY
# =========================
active_tokens = {}
submitted_once = set()

# =========================
# STATUS SHEET
# =========================
def get_status(email):
    data = sheet_status.get_all_records()
    for r in data:
        if str(r["Email"]).strip().lower() == email.strip().lower():
            return {
                "attempt": int(r["Attempt"]),
                "passed": str(r["Passed"]).upper() == "TRUE",
                "device": str(r.get("DeviceID", ""))
            }
    return {"attempt": 0, "passed": False, "device": ""}


def save_status(email, attempt, passed, device_id):
    data = sheet_status.get_all_records()

    for i, r in enumerate(data):
        if str(r["Email"]).strip().lower() == email.strip().lower():
            sheet_status.update_cell(i+2, 2, attempt)
            sheet_status.update_cell(i+2, 3, str(passed))
            sheet_status.update_cell(i+2, 4, device_id)
            return

    sheet_status.append_row([email, attempt, passed, device_id])


# =========================
# HELPERS
# =========================
def cari_peserta(username, password):
    data = sheet_peserta.get_all_records()
    for p in data:
        if (
            str(p["Username"]).strip().lower() == username.strip().lower()
            and str(p["Password"]).strip() == password.strip()
        ):
            return p
    return None


def generate_token(email, ua):
    raw = email + ua + str(datetime.now(WITA))
    return hashlib.sha256(raw.encode()).hexdigest()


def get_random_questions():
    data = sheet_soal.get_all_records()

    seen = set()
    unique = []

    for r in data:
        soal = str(r["Soal"]).strip().lower()
        if soal in seen:
            continue
        seen.add(soal)
        unique.append(r)

    random.shuffle(unique)
    return unique[:30]


# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        peserta = cari_peserta(username, password)

        if not peserta:
            return render_template("login.html", error="Login gagal")

        if str(peserta["Status"]).upper() != "AKTIF":
            return render_template("login.html", error="Akun tidak aktif")

        email = peserta["Email"]
        status = get_status(email)

        ua = request.headers.get("User-Agent", "")
        device_id = hashlib.sha256(ua.encode()).hexdigest()

        # ❌ lulus
        if status["passed"]:
            return render_template("login.html", error="Sudah lulus, tidak bisa login lagi")

        # ❌ gagal max
        if status["attempt"] >= MAX_ATTEMPT_GAGAL:
            return render_template("login.html", error="Kesempatan ujian sudah habis")

        # 🔐 anti 2 device
        if status["device"] and status["device"] != device_id:
            return render_template("login.html", error="Akun sudah digunakan di device lain")

        session["nama"] = peserta["Nama"]
        session["email"] = email
        session["token"] = generate_token(email, ua)
        session["device_id"] = device_id

        active_tokens[session["token"]] = True

        return redirect("/ujian")

    return render_template("login.html")


# =========================
# UJIAN
# =========================
@app.route("/ujian")
def ujian():

    if "token" not in session:
        return redirect("/")

    token = session["token"]

    if token not in active_tokens:
        return redirect("/")

    questions = get_random_questions()
    session["questions"] = questions

    return render_template(
        "ujian.html",
        nama=session["nama"],
        email=session["email"],
        token=token,
        questions=questions
    )


# =========================
# SUBMIT
# =========================
@app.route("/submit", methods=["POST"])
def submit():

    if "token" not in session:
        return jsonify({"success": False})

    email = session["email"]
    token = session["token"]
    device_id = session["device_id"]

    if token in submitted_once:
        return jsonify({"success": False, "message": "Sudah submit"})

    submitted_once.add(token)

    status = get_status(email)

    if status["passed"]:
        return jsonify({"success": False, "message": "Sudah lulus"})

    questions = session.get("questions", [])
    answers = request.json.get("answers", [])

    soal_map = {str(q["No"]): q for q in questions}

    benar = 0
    rows = []

    for a in answers:

        no = str(a["no"])
        jawaban = a["jawaban"]

        if no not in soal_map:
            continue

        q = soal_map[no]

        ok = jawaban == q["Jawaban"]

        if ok:
            benar += 1

        rows.append([
            datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S"),
            session["nama"],
            email,
            q["Soal"],
            jawaban,
            q["Jawaban"],
            "Benar" if ok else "Salah"
        ])

    sheet_jawaban.append_rows(rows)

    nilai = round((benar / 30) * 100)
    lulus = nilai >= KKM

    status["attempt"] += 1

    if lulus:
        status["passed"] = True

    save_status(email, status["attempt"], status["passed"], device_id)

    session.clear()
    active_tokens.pop(token, None)

    return jsonify({
        "success": True,
        "nilai": nilai,
        "lulus": lulus,
        "attempt": status["attempt"],
        "kkm": KKM
    })


# =========================
# LOGOUT
# =========================
@app.route("/force_logout", methods=["POST"])
def force_logout():
    token = session.get("token")
    if token:
        active_tokens.pop(token, None)
    session.clear()
    return jsonify({"success": True})


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)