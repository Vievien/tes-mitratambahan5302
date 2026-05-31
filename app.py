from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    jsonify
)

from datetime import datetime

import os
import json
import random

import gspread

from google.oauth2.service_account import Credentials


app = Flask(__name__)

app.secret_key = "SE2026_MITRA_TAMBAHAN"


# =====================================
# GOOGLE SHEETS
# =====================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

google_creds = json.loads(
    os.environ["GOOGLE_CREDENTIALS"]
)

creds = Credentials.from_service_account_info(
    google_creds,
    scopes=SCOPES
)

gc = gspread.authorize(creds)

spreadsheet = gc.open_by_key("1UaKV5QPMtk_YW_5aRWzoyy5s2w8Xq0Hf43L5iw88Dd0")

sheet_peserta = spreadsheet.worksheet("Peserta")
sheet_soal = spreadsheet.worksheet("Soal")
sheet_jawaban = spreadsheet.worksheet("Jawaban")

def get_peserta():

    return sheet_peserta.get_all_records()


def cari_peserta(username, password):

    peserta = get_peserta()

    for p in peserta:

        if (
            str(p["Username"]).strip().lower()
            ==
            username.strip().lower()
        ) and (
            str(p["Password"]).strip()
            ==
            password.strip()
        ):

            return p

    return None

def cek_kesempatan_ujian(email):

    data = sheet_jawaban.get_all_records()

    email = email.strip().lower()

    peserta_rows = []

    for row in data:

        if (
            str(row["Email"])
            .strip()
            .lower()
            ==
            email
        ):
            peserta_rows.append(row)

    if len(peserta_rows) == 0:

        return {
            "boleh": True,
            "sisa": 2
        }

    grouped = {}

    for row in peserta_rows:

        timestamp = str(
            row["Timestamp"]
        )

        if timestamp not in grouped:
            grouped[timestamp] = []

        grouped[timestamp].append(row)

    attempts = list(grouped.keys())

    total_submit = len(attempts)

    latest_time = sorted(
        attempts,
        reverse=True
    )[0]

    latest_data = grouped[latest_time]

    benar = 0

    for row in latest_data:

        if row["Status"] == "Benar":
            benar += 1

    nilai = round(
        (benar / 30) * 100
    )

    if nilai >= 60:

        return {
            "boleh": False,
            "pesan":
            "Anda sudah lulus ujian dan tidak dapat mengikuti ujian kembali."
        }

    if nilai < 60 and total_submit >= 2:

        return {
            "boleh": False,
            "pesan":
            "Kesempatan ujian ulang Anda telah habis."
        }

    return {
        "boleh": True,
        "sisa": 2 - total_submit
    }

def get_random_questions():

    data = sheet_soal.get_all_records()

    seen = set()

    unique = []

    for row in data:

        soal = (
            str(row["Soal"])
            .strip()
            .lower()
        )

        if soal in seen:
            continue

        seen.add(soal)

        unique.append(row)

    random.shuffle(unique)

    selected = unique[:30]

    return selected

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        peserta = cari_peserta(
            username,
            password
        )

        if not peserta:

            return render_template(
                "login.html",
                error="Username atau password salah"
            )

        status = str(
            peserta["Status"]
        ).strip().upper()

        if status != "AKTIF":

            return render_template(
                "login.html",
                error="Status peserta tidak aktif"
            )

        cek = cek_kesempatan_ujian(
            peserta["Email"]
        )

        if not cek["boleh"]:

            return render_template(
                "login.html",
                error=cek["pesan"]
            )

        session["nama"] = peserta["Nama"]

        session["email"] = peserta["Email"]

        return redirect("/ujian")

    return render_template("login.html")

@app.route("/ujian")
def ujian():

    if "nama" not in session:
        return redirect("/")

    questions = get_random_questions()

    session["questions"] = questions

    return render_template(
        "ujian.html",
        nama=session["nama"],
        email=session["email"],
        questions=questions
    )

@app.route("/submit", methods=["POST"])
def submit():

    if "nama" not in session:
        return jsonify({
            "success": False
        })

    nama = session["nama"]
    email = session["email"]

    questions = session.get("questions", [])

    if not questions:

        return jsonify({
            "success": False,
            "message": "Data soal tidak ditemukan"
        })

    answers = request.json.get(
        "answers",
        []
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    soal_map = {}

    for q in questions:

        soal_map[str(q["No"])] = q

    rows = []

    benar = 0

    for item in answers:

        no = str(item["no"])

        jawaban_peserta = item["jawaban"]

        if no not in soal_map:
            continue

        q = soal_map[no]

        jawaban_benar = str(
            q["Jawaban"]
        ).strip()

        status = (
            "Benar"
            if jawaban_peserta == jawaban_benar
            else "Salah"
        )

        if status == "Benar":
            benar += 1

        rows.append([

            timestamp,

            nama,

            email,

            q["Soal"],

            jawaban_peserta,

            jawaban_benar,

            status

        ])

    if rows:

        sheet_jawaban.append_rows(rows)

    nilai = round(
        (benar / 30) * 100
    )

    lulus = nilai >= 60

    session.clear()

    return jsonify({

        "success": True,

        "nilai": nilai,

        "lulus": lulus

    })


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

