import os
import smtplib
import sqlite3
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# --- Configuration ---
DEBUG = False
DEBUG_SAMPLE_USER_ID = "1"
DEBUG_SAMPLE_LIMIT = 4

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "data", "users")
USERS_DB = os.path.join(SCRIPT_DIR, "data", "users.db")
TRANSLATION_PATH = os.path.join(SCRIPT_DIR, "website", "translation.json")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

load_dotenv()
EMAIL_FROM = os.getenv("GMAIL_ADRESS")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# --- Load translation ---
with open(TRANSLATION_PATH, "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

def t(key, lang):
    return TRANSLATIONS.get(key, {}).get(lang, key)

# --- Data access ---
def get_users():
    users = {}
    if not os.path.isfile(USERS_DB):
        print("❌ users.db not found.")
        return users
    with sqlite3.connect(USERS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, lang FROM users")
        for uid, email, lang in cursor.fetchall():
            users[str(uid)] = {"email": email, "lang": (lang or "en")}
    return users

def _matches_db_path(user_id):
    return os.path.join(BASE_DIR, f"user_{user_id}", "matches.db")

def get_new_matches_grouped(user_id):
    db_path = _matches_db_path(user_id)
    if not os.path.isfile(db_path):
        return {}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manuscripts WHERE label = 'new'")
        rows = cursor.fetchall()

    grouped = {}
    for row in rows:
        source_filter = row["source_filter"] if "source_filter" in row.keys() else "unknown"
        grouped.setdefault(source_filter, []).append({
            "title": row["title"],
            "link": row["link"],
            "abstract": row["abstract"]
        })
    return grouped

def get_recent_any_label_grouped(user_id, limit=4):
    """Fetch up to `limit` most recent entries regardless of label, grouped by source_filter."""
    db_path = _matches_db_path(user_id)
    if not os.path.isfile(db_path):
        return {}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Try to sort by published_timestamp if present, else added_timestamp, else rowid
        # Using datetime() on text ISO8601 sorts correctly; fallback to rowid
        cur.execute("""
            SELECT title, link, abstract,
                   CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('manuscripts') WHERE name='source_filter')
                        THEN source_filter ELSE 'unknown' END AS source_filter,
                   CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('manuscripts') WHERE name='published_timestamp')
                        THEN published_timestamp ELSE NULL END AS published_timestamp,
                   CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('manuscripts') WHERE name='added_timestamp')
                        THEN added_timestamp ELSE NULL END AS added_timestamp,
                   rowid
            FROM manuscripts
            ORDER BY
              CASE WHEN published_timestamp IS NOT NULL THEN datetime(published_timestamp) END DESC,
              CASE WHEN added_timestamp IS NOT NULL THEN datetime(added_timestamp) END DESC,
              rowid DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()

    grouped = {}
    for row in rows:
        sf = row["source_filter"] if row["source_filter"] else "unknown"
        grouped.setdefault(sf, []).append({
            "title": row["title"],
            "link": row["link"],
            "abstract": row["abstract"]
        })
    return grouped

def mark_all_old(user_id):
    if DEBUG:  # don't touch labels during debug dry-runs
        return
    db_path = _matches_db_path(user_id)
    if not os.path.isfile(db_path):
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE manuscripts SET label = 'old' WHERE label = 'new'")
        conn.commit()

# --- Email formatting ---
def format_email_plain(grouped, lang):
    total = sum(len(v) for v in grouped.values())
    lines = []
    # Intro + link
    lines.append(f"{t('email.manage_filters', lang)} https://arxivbutler.com/\n")
    lines.append(t("email.intro", lang))
    lines.append("")
    # Summary
    lines.append(f"{t('email.found_matches', lang).format(count=total)}")
    if total > 10:
        lines.append(t("email.too_many_matches", lang))
    lines.append("")
    # Body
    for filter_name, matches in grouped.items():
        lines.append(f"{t('email.filter_name', lang)}: {filter_name}")
        for m in matches:
            lines.append(f"• {m['title']}\n{m['link']}")
            if total <= 10:
                lines.append(m.get("abstract", ""))
            lines.append("")
        lines.append("")
    # Disclaimer
    lines.append(t("email.disclaimer", lang))
    return "\n".join(lines)

def format_email_html(grouped, lang):
    total = sum(len(v) for v in grouped.values())
    manage_link = "https://arxivbutler.com/"

    intro_html = f"""
      <p style="margin:0 0 12px 0; line-height:1.5; color:#4C191B;">
        {t('email.intro', lang)}
      </p>
      <p style="margin:0 0 16px 0; line-height:1.5;">
        <a href="{manage_link}" style="color:#05668D; text-decoration:none; font-weight:600;">
          {t('email.manage_filters', lang)}
        </a>
      </p>
    """

    summary_html = f"""
      <p style="margin:0 0 12px 0; font-weight:600; color:#4C191B;">
        {t('email.found_matches', lang).format(count=total)}
      </p>
      {('<p style="margin:0 0 12px 0; color:#BE6E46;">' + t('email.too_many_matches', lang) + '</p>') if total > 10 else ''}
    """

    sections = []
    for filter_name, matches in grouped.items():
        items = []
        for m in matches:
            abstract_block = ""
            if total <= 10 and m.get("abstract"):
                abstract_block = f"""
                  <div style="margin-top:8px; font-size:13px; color:#4C191B; line-height:1.45;">
                    {m['abstract']}
                  </div>
                """
            items.append(f"""
              <tr>
                <td style="padding:12px 16px; border:1px solid rgba(76,25,27,0.2);">
                  <div style="font-size:15px; font-weight:600; margin-bottom:4px; line-height:1.35;">
                    <a href="{m['link']}" style="color:#05668D; text-decoration:none;">{m['title']}</a>
                  </div>
                  <div style="font-size:12px; color:#666; word-break:break-word;">
                    <a href="{m['link']}" style="color:#666; text-decoration:none;">{m['link']}</a>
                  </div>
                  {abstract_block}
                </td>
              </tr>
            """)
        section_html = f"""
          <tr>
            <td style="padding-top:6px; padding-bottom:6px;">
              <div style="font-weight:700; margin:14px 0 8px 0; font-size:16px; color:#4C191B;">
                {t('email.filter_name', lang)}: {filter_name}
              </div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
                {''.join(items)}
              </table>
            </td>
          </tr>
        """
        sections.append(section_html)

    disclaimer_html = f"""
      <p style="margin:18px 0 0 0; font-size:12px; color:#4C191B; line-height:1.5;">
        {t('email.disclaimer', lang)}
      </p>
    """

    outer = f"""
    <html>
      <body style="margin:0; padding:0; background:#FFEECF;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FFEECF; padding:16px 0;">
          <tr>
            <td align="center">
              <table role="presentation" width="96%" style="max-width:700px; background:#ffffff; border:1px solid rgba(76,25,27,0.2); border-radius:8px; overflow:hidden;" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:16px 20px; background:#BE6E46; color:#fff; font-weight:700; font-size:18px;">
                    {t('email.subject', lang)}
                  </td>
                </tr>
                <tr>
                  <td style="padding:18px 20px;">
                    {intro_html}
                    {summary_html}
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse; margin-top:6px;">
                      {''.join(sections)}
                    </table>
                    {disclaimer_html}
                  </td>
                </tr>
              </table>
              <div style="color:#4C191B; font-size:11px; margin-top:10px;">
                © {datetime.now().year} ArXiv Butler
              </div>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    return outer

# --- Email sending ---
def send_email(to_email, subject, plain_body, html_body):
    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach plain text first (fallback), then HTML
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)

# --- Main flow ---
def main():
    print("📬 Notifier running...")
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Missing email credentials.")
        return

    users = get_users()

    # In DEBUG, restrict to one sample user and pull any 4 most recent entries (any label)
    if DEBUG:
        if DEBUG_SAMPLE_USER_ID not in users:
            print(f"❌ DEBUG: user id {DEBUG_SAMPLE_USER_ID} not found in users.db")
            return
        users = {DEBUG_SAMPLE_USER_ID: users[DEBUG_SAMPLE_USER_ID]}

    for user_id, info in users.items():
        email = info["email"]
        lang = info["lang"]

        if DEBUG:
            grouped = get_recent_any_label_grouped(user_id, limit=DEBUG_SAMPLE_LIMIT)
        else:
            grouped = get_new_matches_grouped(user_id)

        if not grouped:
            print(f"ℹ️  No matches for {email}")
            continue

        subject = t("email.subject", lang)
        plain = format_email_plain(grouped, lang)
        html = format_email_html(grouped, lang)

        if DEBUG:
            print(f"--- EMAIL (PLAIN) to {email} ---\n{plain}\n--- END PLAIN ---\n")
            print(f"--- EMAIL (HTML) to {email} ---\n{html}\n--- END HTML ---\n")
            # Still send to see rendering in a real client during debug
            send_email(email, subject, plain, html)
            print(f"✅ DEBUG email sent to {email} (max {DEBUG_SAMPLE_LIMIT} entries, any label)")
        else:
            send_email(email, subject, plain, html)
            mark_all_old(user_id)
            print(f"✅ Email sent to {email}")

if __name__ == "__main__":
    main()
