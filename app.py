from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
import os, json, random, hashlib
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = "bps5302!"

KKM = 60
MAX_ATTEMPT_GAGAL = 2

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

# =========================
# CBT PRO MAX MEMORY
# =========================
active_tokens = {}
submitted_keys = set()
last_seen = {}

user_status = {}
# format:
# email = {
#   "attempt": 0,
#   "passed": False
# }

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
    raw = email + ua + str(datetime.now())
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
            return render_template("login.html", error="Tidak aktif")

        ua = request.headers.get("User-Agent", "")
        token = generate_token(peserta["Email"], ua)

        session["nama"] = peserta["Nama"]
        session["email"] = peserta["Email"]
        session["token"] = token

        active_tokens[token] = True

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
# HEARTBEAT
# =========================
@app.route("/heartbeat", methods=["POST"])
def heartbeat():

    if "token" not in session:
        return jsonify({"success": False})

    last_seen[session["token"]] = datetime.now()

    return jsonify({"success": True})


# =========================
# SUBMIT (ANTI DUPLICATE GLOBAL)
# =========================
@app.route("/submit", methods=["POST"])
def submit():

    if "token" not in session:
        return jsonify({"success": False})

    email = session["email"]
    token = session["token"]

    status = user_status.get(email, {"attempt": 0, "passed": False})

# kalau sudah lulus → blok total
    if status["passed"]:
        return jsonify({"success": False, "message": "Anda sudah lulus, tidak bisa mengulang ujian"})

    submitted_keys.add(key)

    questions = session.get("questions", [])
    answers = request.json.get("answers", [])

    soal_map = {str(q["No"]): q for q in questions}

    rows = []
    benar = 0

    for a in answers:

        no = str(a["no"])
        jawaban = a["jawaban"]

        if no not in soal_map:
            continue

        q = soal_map[no]

        status = "Benar" if jawaban == q["Jawaban"] else "Salah"

        if status == "Benar":
            benar += 1

        rows.append([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session["nama"],
            email,
            q["Soal"],
            jawaban,
            q["Jawaban"],
            status
        ])

    sheet_jawaban.append_rows(rows)

    nilai = round((benar / 30) * 100)
    lulus = nilai >= 60

    status["attempt"] += 1

if lulus:
    status["passed"] = True
else:
    if status["attempt"] >= MAX_ATTEMPT_GAGAL:
        status["passed"] = False

user_status[email] = status

    session.clear()
    active_tokens.pop(token, None)

    return jsonify({
    "success": True,
    "nilai": nilai,
    "lulus": lulus,
    "attempt": status["attempt"],
    "max_attempt": MAX_ATTEMPT_GAGAL
})


# =========================
# FORCE LOGOUT
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