# auth.py  – secure password storage / verification
from flask import Blueprint, request, redirect, url_for, render_template_string, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from config import USER_DB_PATH, USERS_ROOT
import smtplib
import secrets
from email.message import EmailMessage
from utils import t, COLORS
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import render_template


auth_bp = Blueprint("auth", __name__)

load_dotenv()  # ensures .env values are loaded

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = os.getenv("GMAIL_ADRESS")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# ------------------------------------------------------------------ #
# Helper: fetch (email, hashed_pwd, id)  --------------------------- #
# ------------------------------------------------------------------ #
def get_user(email: str):
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT email, password, id FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return row  # None if not found

def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)

# ------------------------------------------------------------------ #
# --------------------- PASSWORD RESET ----------------------------- #
# ------------------------------------------------------------------ #

@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    lang = session.get("lang", "en")

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = get_user(email)

        if not user:
            flash(t("auth.email_not_found", lang))
            return redirect(request.url)

        new_pw = secrets.token_urlsafe(8)  # generates 11-char safe password
        new_hash = generate_password_hash(new_pw)

        conn = sqlite3.connect(USER_DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = ? WHERE email = ?", (new_hash, email))
        conn.commit()
        conn.close()

        try:
            subject = t("email.reset_password_subject", lang)
            body    = t("email.reset_password_body", lang).format(password=new_pw)

            send_email(
                to_email=email,
                subject=subject,
                body=body
            )
            flash(t("auth.reset_email_sent", lang))
        except Exception as e:
            print(e)
            flash(t("auth.email_failed", lang))

        return redirect(url_for("auth.login"))

    return render_template('password_reset.html', t=lambda k: t(k, lang), lang=lang)

# ------------------------------------------------------------------ #
# -------------------------- LOGIN --------------------------------- #
# ------------------------------------------------------------------ #
@auth_bp.route("/", methods=["GET", "POST"])
def login():
    lang = session.get("lang", "en")

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        user = get_user(email)
        if user and check_password_hash(user["password"], password):
            session["user"] = user["email"]
            session["user_id"] = user["id"]
            return redirect(url_for("filters.filters_home"))

        flash(t("auth.invalid_credentials", lang))  # Optional: localized message

    return render_template("login.html", t=lambda k: t(k, lang), lang=lang)



# ------------------------------------------------------------------ #
# ------------------------- REGISTER ------------------------------- #
# ------------------------------------------------------------------ #
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email           = request.form["email"].strip().lower()
        password        = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(request.url)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.")
            return redirect(request.url)

        pwd_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

        conn = sqlite3.connect(USER_DB_PATH)
        cur  = conn.cursor()
        try:
            # ❶ insert WITHOUT the id column
            cur.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, pwd_hash)
            )
            conn.commit()

            # ❷ retrieve autogenerated id
            new_id = cur.lastrowid

            # ❸ create user directory
            os.makedirs(os.path.join(USERS_ROOT, f"user_{new_id}"), exist_ok=True)

            flash("Registration successful! Please log in.")
            return redirect(url_for("auth.login"))

        except sqlite3.IntegrityError as e:
            if "email" in str(e).lower():
                flash("Email already registered.")
            else:
                flash("Registration failed (database error).")

        finally:
            conn.close()

    lang = session.get("lang", "en")
    return render_template('register.html', t=lambda k: t(k, lang), lang=lang)



# ------------------------------------------------------------------ #
# -------------------------- LOGOUT -------------------------------- #
# ------------------------------------------------------------------ #
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

# ------------------------------------------------------------------ #
# --------------------- CHANGE PASSWORD ---------------------------- #
# ------------------------------------------------------------------ #

@auth_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    lang = session.get("lang", "en")

    if request.method == "POST":
        current = request.form["current_password"]
        new     = request.form["new_password"]
        confirm = request.form["confirm_password"]

        user = get_user(session["user"])
        if not user or not check_password_hash(user["password"], current):
            flash(t("auth.incorrect_current_password", lang))
            return redirect(request.url)

        if new != confirm:
            flash(t("auth.passwords_dont_match", lang))
            return redirect(request.url)

        if len(new) < 8:
            flash(t("auth.password_too_short", lang))
            return redirect(request.url)

        new_hash = generate_password_hash(new, method="pbkdf2:sha256", salt_length=16)
        conn = sqlite3.connect(USER_DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, session["user_id"]))
        conn.commit()
        conn.close()

        flash(t("auth.password_changed_successfully", lang))
        return redirect(url_for("filters.filters_home"))

    return render_template('password_change.html', t=lambda k: t(k, lang), lang=lang)


