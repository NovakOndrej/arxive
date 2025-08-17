from flask import Blueprint, session, redirect, url_for, render_template
import os
import json
from config import USERS_ROOT
from utils import t, COLORS

filters_bp = Blueprint("filters", __name__)

@filters_bp.route("/filters")
def filters_home():
    user = session.get("user")
    user_id = session.get("user_id")
    if not user or user_id is None:
        return redirect(url_for("auth.login"))

    user_dir = os.path.join(USERS_ROOT, f"user_{user_id}")
    filters = []

    if os.path.exists(user_dir):
        for file in os.listdir(user_dir):
            if file.startswith("filter_") and file.endswith(".json"):
                name = file[len("filter_"):-len(".json")]
                filters.append(name)

    lang = session.get("lang", "en")
    return render_template('display_filters.html', t=lambda k: t(k, lang), lang=lang, filters=filters)



@filters_bp.route("/filters/new")
def new_filter():
    return redirect(url_for("editor.edit_filter"))

