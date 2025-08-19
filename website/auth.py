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
from datetime import datetime




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

def send_email(to_email, subject, plain_body, html_main_paragraph=None):
    """Send email with styled HTML body and plain fallback."""
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach plain fallback (required)
    msg.attach(MIMEText(plain_body, "plain"))

    # Styled HTML layout
    if html_main_paragraph:
        html_body = f"""
        <html>
          <body style="margin:0; padding:0;">
            <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#FFEECF; padding:20px 0;">
                <tr>
                <td align="center">
                    <table role="presentation" width="96%" style="max-width:600px; background:#fff; border:1px solid #ddd; border-radius:10px; padding:24px; font-family:Segoe UI, sans-serif; color:#4C191B;" cellpadding="0" cellspacing="0">
                    <tr>
                        <td>
                        <h2 style="color:#BE6E46; font-size:20px; margin-bottom:12px;">{subject}</h2>
                        <p style="font-size:15px; line-height:1.6;">{html_main_paragraph}</p>
                        <p style="margin-top:24px; font-size:12px; color:#666;">
                            This email was sent by ArXiv Butler. If you didn’t request this, you can safely ignore it.
                        </p>
                        <div style="text-align:center; font-size:11px; color:#4C191B; margin-top:10px;">
                            © {datetime.now().year} ArXiv Butler
                        </div>
                        </td>
                    </tr>
                    </table>
                </td>
                </tr>
            </table>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

    # Send
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
            html_paragraph = t("email.reset_password_body", lang).format(password=f"<b>{new_pw}</b>")
            
            send_email(email, subject, plain_body=body, html_main_paragraph=html_paragraph)
            flash(t("auth.reset_email_sent", lang))
        except Exception as e:
            import traceback
            print("❌ Failed to send email")
            traceback.print_exc()  # <- this gives full traceback!
            flash(t("auth.email_failed", lang))
            return redirect(request.url)

        return redirect(url_for("auth.login"))

    return render_template('password_reset.html', t=lambda k: t(k, lang), lang=lang)

# ------------------------------------------------------------------ #
# -------------------------- LOGIN --------------------------------- #
# ------------------------------------------------------------------ #
@auth_bp.route("/", methods=["GET", "POST"])
def login():
    lang = session.get("lang", "en")

    if request.method == "POST":
        # Only accept standard HTML form posts; reject bot JSON/XML/etc.
        if request.mimetype not in ("application/x-www-form-urlencoded", "multipart/form-data"):
            current_app.logger.warning("Rejected POST / with mimetype %s", request.mimetype)
            return render_template("login.html", t=lambda k: t(k, lang), lang=lang), 415

        # Never index request.form directly—use .get() and normalize
        form = request.form or {}
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""

        # Validate presence of required fields (turns 500s into clean 400s)
        if not email or not password:
            flash(t("auth.missing_credentials", lang))  # add key to translation.json
            return render_template("login.html", t=lambda k: t(k, lang), lang=lang), 400

        user = get_user(email)
        if user and check_password_hash(user["password"], password):
            # Reduce session fixation risk by clearing before setting
            session.clear()
            session["user"] = user["email"]
            session["user_id"] = user["id"]
            return redirect(url_for("filters.filters_home"))

        # Generic failure message; 401 is appropriate for bad auth
        flash(t("auth.invalid_credentials", lang))
        return render_template("login.html", t=lambda k: t(k, lang), lang=lang), 401

    # GET: render the form
    return render_template("login.html", t=lambda k: t(k, lang), lang=lang)


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


