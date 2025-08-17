from flask import Flask, session, url_for, request, redirect
import os
import sqlite3
from config import USER_DB_PATH, USERS_ROOT
from auth import auth_bp
from filters import filters_bp
from filter_editor import editor_bp
from flask import session
from utils import COLORS



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

