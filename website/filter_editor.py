import os
import json
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import sqlite3
from flask import Blueprint, request, redirect, url_for, render_template, session, flash, jsonify
from datetime import datetime, timedelta
from config import USERS_ROOT, MAIN_DB_PATH, USER_DB_PATH
from utils import t, COLORS
import sqlite3

def build_fts_query_from_filter(filter_data):
    groups = filter_data.get("keyword_groups", [])
    if not groups:
        return None
    return " AND ".join(["(" + " OR ".join(group) + ")" for group in groups])

editor_bp = Blueprint("editor", __name__)

@editor_bp.route("/filters/edit", methods=["GET", "POST"])
@editor_bp.route("/filters/edit/<filter_name>", methods=["GET", "POST"])
def edit_filter(filter_name=None):
    if "user" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    user_dir = os.path.join(USERS_ROOT, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)

    old_filter, filter_path = {}, None
    if filter_name:
        filter_path = os.path.join(user_dir, f"filter_{filter_name}.json")
        if os.path.exists(filter_path):
            with open(filter_path, "r", encoding="utf-8") as f:
                old_filter = json.load(f)

    # ------------- POST: Save filter ------------- #
    if request.method == "POST" and "check" not in request.form:
        name = request.form.get("name") or filter_name
        if not name:
            flash("Filter name is required.")
            return redirect(request.url)

        keyword_groups = []
        for i in range(6):
            keywords = request.form.getlist(f"keyword_group_{i}")
            if keywords:
                quoted = [f'"{kw}"' for kw in keywords if kw.strip()]
                if quoted:
                    keyword_groups.append(quoted)

        new_filter = {
            "filter_type": "keyword",
            "keyword_groups": keyword_groups
        }

        if old_filter != new_filter:
            new_filter["last_scan"] = (datetime.now() - timedelta(days=365*20)).isoformat()
        else:
            new_filter["last_scan"] = old_filter.get("last_scan", "")

        save_path = os.path.join(user_dir, f"filter_{name}.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(new_filter, f, ensure_ascii=False, indent=2)

        # ------------- NEW: Save language to users.db ------------- #
        lang = session.get("lang", "en")
        with sqlite3.connect(USER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user_id))
            conn.commit()

        return redirect(url_for("filters.filters_home"))

    # ------------- GET: Load form ------------- #
    raw_groups = old_filter.get("keyword_groups", [[]] + [[] for _ in range(5)])
    unquoted_groups = [[kw.strip('"') for kw in group] for group in raw_groups]

    data = {
        "filter_type": "keyword",
        "keyword_groups": unquoted_groups
    }

    lang = session.get("lang", "en")
    return render_template('filter_editor.html', t=lambda k: t(k, lang), lang=lang, filter_name=filter_name or "", **data)

@editor_bp.route("/filters/delete/<filter_name>", methods=["POST"])
def delete_filter(filter_name):
    if "user" not in session:
        return redirect(url_for("auth.login"))
    user_dir = os.path.join(USERS_ROOT, f"user_{session['user_id']}")
    path = os.path.join(user_dir, f"filter_{filter_name}.json")
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("filters.filters_home"))

@editor_bp.route("/filters/check", methods=["POST"])
def test_filter():
    filter_data = {
        "filter_type": "keyword",
        "keyword_groups": []
    }

    for i in range(6):
        keywords = request.form.getlist(f"keyword_group_{i}")
        if keywords:
            quoted = [f'"{kw}"' for kw in keywords if kw.strip()]
            if quoted:
                filter_data["keyword_groups"].append(quoted)

    fts_query = build_fts_query_from_filter(filter_data)
    if not fts_query:
        print("[DEBUG] No valid FTS query could be built.")
        return jsonify({"matches": 0, "titles": []})

    with sqlite3.connect(MAIN_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title FROM manuscripts_fts
            WHERE manuscripts_fts MATCH ?
        """, (fts_query,))
        titles = [row["title"] for row in cursor.fetchall() if "title" in row.keys()]

    count = len(titles)
    sample_titles = titles[:5]

    return jsonify({
        "matches": count,
        "titles": sample_titles
    })
