from flask import Flask, session, url_for, request, redirect
import os
import sqlite3
from config import USER_DB_PATH, USERS_ROOT
from auth import auth_bp, send_email
from filters import filters_bp
from filter_editor import editor_bp
from flask import session
from utils import COLORS
from registration_verification import generate_code, store_verification, verify_code
from flask import render_template, flash
from utils import t, COLORS
from werkzeug.security import generate_password_hash
from datetime import datetime
from flask import current_app



app = Flask(__name__)
app.secret_key = "your_secret_key"

# ----------------------------------
# Ensure the users.db and folders exist
# ----------------------------------
def init_user_db():
    os.makedirs(USERS_ROOT, exist_ok=True)  # Ensure data/users/ exists

    if not os.path.exists(USER_DB_PATH):
        conn = sqlite3.connect(USER_DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        print("[INFO] Created users.db with users table.")
    else:
        print("[INFO] users.db already exists.")

@app.context_processor
def inject_globals():
    return dict(colors=COLORS)

@app.before_request
def ensure_language():
    if 'lang' not in session:
        session['lang'] = 'en'  # default language
        
@app.route("/lang/<lang_code>")
def set_language(lang_code):
    session["lang"] = lang_code
    return redirect(request.referrer or url_for("auth.login"))



@app.route("/register", methods=["GET", "POST"])
def register():
    lang = session.get("lang", "en")

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash(t("auth.passwords_dont_match", lang))
            return redirect(request.url)

        if len(password) < 8:
            flash(t("auth.password_too_short", lang))
            return redirect(request.url)

        # Check if email already exists
        conn = sqlite3.connect(USER_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            flash(t("auth.email_exists", lang))
            return redirect(request.url)
        conn.close()

        # Generate and send code
        code = generate_code()
        store_verification(email, code)

        try:
            subject = t("email.verify_subject", lang)
            body = t("email.verify_body", lang).format(code=code)
            html_paragraph = t("email.verify_body", lang).format(code=f"<b>{code}</b>")
            send_email(email, subject, plain_body=body, html_main_paragraph=html_paragraph)

            session["pending_email"] = email
            session["pending_password"] = password
            flash(t("auth.code_sent", lang))
            return redirect(url_for("verify_registration"))
        except Exception as e:
            import traceback
            print("❌ Failed to send email")
            traceback.print_exc()  # <- this gives full traceback!
            flash(t("auth.email_failed", lang))
            return redirect(request.url)

    return render_template("register.html", t=lambda k: t(k, lang), lang=lang)


@app.route("/verify_registration", methods=["GET", "POST"])
def verify_registration():
    lang = session.get("lang", "en")

    if "pending_email" not in session or "pending_password" not in session:
        flash(t("auth.no_pending_registration", lang))
        return redirect(url_for("register"))

    if request.method == "POST":
        code = request.form["code"].strip()
        email = session["pending_email"]
        password = session["pending_password"]

        if verify_code(email, code):
            pwd_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
            conn = sqlite3.connect(USER_DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, pwd_hash))
            conn.commit()
            user_id = cur.lastrowid
            conn.close()

            os.makedirs(os.path.join(USERS_ROOT, f"user_{user_id}"), exist_ok=True)
            session.pop("pending_email", None)
            session.pop("pending_password", None)
            flash(t("auth.registration_success", lang))
            return redirect(url_for("auth.login"))
        else:
            flash(t("auth.invalid_or_expired_code", lang))

    return render_template("verify_registration.html", t=lambda k: t(k, lang), lang=lang)


# ----------------------------------
# Register Blueprints
# ----------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(filters_bp)
app.register_blueprint(editor_bp)

# ----------------------------------
# Main entry point
# ----------------------------------
if __name__ == "__main__":
    init_user_db()
    app.run(host="0.0.0.0", port=5001, debug=True)

