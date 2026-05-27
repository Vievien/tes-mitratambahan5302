from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)

app.secret_key = "bps5302"

# ====================================
# LINK APPS SCRIPT
# ====================================
LINK_UJIAN = "https://script.google.com/macros/s/AKfycbwRGTb892O_eRr1dj-dogtaE__Y-BnhXALswwdYuXE51uhSQrQWb0cK2XDUN0oT_-eGMw/exec"

# ====================================
# DATABASE USER SEDERHANA
# ====================================
users = {

    "mitra5302": "tutup5302!?!@#$"

}

# ====================================
# LOADING PAGE
# ====================================
@app.route("/loading")
def loading():

    if "username" not in session:
        return redirect("/")

    return render_template("loading.html")

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

            return redirect("/loading")

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