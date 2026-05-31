from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime
import os, json, random, gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = "CBT_STABLE_FINAL"

# ===================== GOOGLE SHEETS =====================
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

# ===================== SIMPLE MEMORY =====================
submitted = set()

# ===================== HELPERS =====================
def cari_peserta(username, password):
    data = sheet_peserta.get_all_records()
    for p in data:
        if str(p["Username"]).strip().lower() == username.strip().lower() and str(p["Password"]).strip() == password.strip():
            return p
    return None


def get_soal():
    data = sheet_soal.get_all_records()
    random.shuffle(data)
    return data[:30]


# ===================== LOGIN =====================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        p = cari_peserta(user, pw)

        if not p:
            return render_template("login.html", error="Login gagal")

        if str(p["Status"]).upper() != "AKTIF":
            return render_template("login.html", error="Tidak aktif")

        session["nama"] = p["Nama"]
        session["email"] = p["Email"]

        return redirect("/ujian")

    return render_template("login.html")


# ===================== UJIAN =====================
@app.route("/ujian")
def ujian():
    if "email" not in session:
        return redirect("/")

    soal = get_soal()
    session["soal"] = soal

    return render_template(
        "ujian.html",
        nama=session["nama"],
        email=session["email"],
        questions=soal
    )


# ===================== SUBMIT =====================
@app.route("/submit", methods=["POST"])
def submit():

    if "email" not in session:
        return jsonify({"success": False})

    email = session["email"]

    if email in submitted:
        return jsonify({"success": False, "message": "Sudah submit"})

    submitted.add(email)

    data = request.json.get("answers", [])
    soal = session.get("soal", [])

    map_soal = {str(q["No"]): q for q in soal}

    rows = []
    benar = 0

    for a in data:

        no = str(a["no"])
        jwb = a["jawaban"]

        if no not in map_soal:
            continue

        q = map_soal[no]
        status = "Benar" if jwb == q["Jawaban"] else "Salah"

        if status == "Benar":
            benar += 1

        rows.append([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session["nama"],
            email,
            q["Soal"],
            jwb,
            q["Jawaban"],
            status
        ])

    sheet_jawaban.append_rows(rows)

    nilai = round((benar / 30) * 100)

    session.clear()

    return jsonify({
        "success": True,
        "nilai": nilai,
        "lulus": nilai >= 60
    })


# ===================== RUN =====================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)