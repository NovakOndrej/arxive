# utils.py
import json
import os

# Load translations
with open("translation.json", "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

def t(key, lang="en"):
    return TRANSLATIONS.get(key, {}).get(lang, key)

# Load colors
def get_colors():
    try:
        # This creates a full absolute path to colors.json
        path = os.path.join(os.path.dirname(__file__), "colors.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Color load error:", e)
        return {}

COLORS = get_colors()

COLORS = get_colors()
