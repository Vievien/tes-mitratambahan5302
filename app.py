from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)

app.secret_key = "bps5302"

# ====================================
# LINK APPS SCRIPT
# ====================================
LINK_UJIAN = "https://script.google.com/macros/s/AKfycbwbiHGi10Sg6ioVTUPgF1BV1xo0XR9Lv7iFV2e1LaJObfgq3SB857DdPzt8mTGHkqBv6A/exec"

# ====================================
# DATABASE USER SEDERHANA
# ====================================
users = {

    "mitra5302": "12345"

}

# ====================================
# LOGIN
# ====================================
@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username] == password:

            session["username"] = username

            return redirect("/ujian")

        return render_template(
            "login.html",
            error="Username atau password salah"
        )

    return render_template("login.html")


# ====================================
# HALAMAN UJIAN
# ====================================
@app.route("/ujian")
def ujian():

    if "username" not in session:
        return redirect("/")

    return render_template(
        "ujian.html",
        username=session["username"],
        link_ujian=LINK_UJIAN
    )


# ====================================
# LOGOUT
# ====================================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ====================================
# RUN
# ====================================
if __name__ == "__main__":
    app.run(debug=True)