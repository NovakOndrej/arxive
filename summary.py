import os
import re
import time
import sqlite3
import requests

DB_PATH = "data/manuscript_db.db"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# ---- Helpers for model output cleaning (from your testing script) ----
REASONING = re.compile(r"<think>.*?</think>", re.I | re.S)
def clean(text: str) -> str:
    if not text:
        return ""
    tail = text.split("</think>")[-1]
    return REASONING.sub("", tail).strip() or text.strip()

BASE_OPTIONS = {"temperature": 0.2, "top_p": 0.9, "num_predict": 100, "num_ctx": 1024, "seed": 42}

SYSTEM_LIST = (
  "You are a scientific assistant. Extract only the novel contributions of a research abstract. "
  "Output MUST be a single line of comma-separated list of short noun phrases (3–8 words). "
  "Third-person; no background/applications/future work; preserve numerics; no <think>."
)

def summarize_novelty_list(abstract: str, model: str = "gemma3:1b") -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_LIST},
            {"role": "user", "content": f"Abstract:\n{abstract}\n"},
        ],
        "options": BASE_OPTIONS,
        "stream": False,
        "keep_alive": "1h",
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
    if r.status_code == 404:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": SYSTEM_LIST + "\n\nAbstract:\n" + abstract,
                "options": BASE_OPTIONS,
                "stream": False,
                "keep_alive": "1h",
            },
            timeout=60,
        )
    r.raise_for_status()
    data = r.json()
    text = (data.get("message", {}) or {}).get("content") or data.get("response", "")
    return clean(text)

# ---- Main worker ----
MAX_SECONDS = 5 * 60 * 60  # 5 hours
BATCH_SIZE = 50            # number of rows to pull per DB fetch

SELECT_BATCH_SQL = """
SELECT id, abstract
FROM manuscripts
WHERE (summary IS NULL OR TRIM(summary) = '')
  AND abstract IS NOT NULL AND TRIM(abstract) <> ''
  AND added_timestamp >= datetime('now', '-24 hours')
ORDER BY added_timestamp ASC
LIMIT ?;
"""

UPDATE_SQL = "UPDATE manuscripts SET summary = ? WHERE id = ?;"

def fill_summaries():
    start = time.time()
    processed = 0
    failures = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.isolation_level = None  # we'll control transactions manually
        cur = conn.cursor()

        while True:
            # Respect 5-hour wall clock limit
            if time.time() - start >= MAX_SECONDS:
                print("[stop] Reached 5-hour limit.")
                break

            cur.execute(SELECT_BATCH_SQL, (BATCH_SIZE,))
            rows = cur.fetchall()
            if not rows:
                print("[done] No more items to process (within 24h window & empty summaries).")
                break

            # Begin a transaction for this batch
            cur.execute("BEGIN")
            try:
                for mid, abstract in rows:
                    # Check time limit frequently
                    if time.time() - start >= MAX_SECONDS:
                        print("[stop] Reached 5-hour limit mid-batch; committing progress.")
                        break

                    try:
                        summary = summarize_novelty_list(abstract)
                        # If model returns empty, leave the field empty for a future run
                        if summary:
                            cur.execute(UPDATE_SQL, (summary, mid))
                            processed += 1
                            #print(f"[ok] {mid} :: {summary[:80].replace('\\n', ' ')}{'...' if len(summary) > 80 else ''}")
                        else:
                            print(f"[skip-empty] {mid} :: model returned empty summary")
                    except Exception as e:
                        failures += 1
                        print(f"[fail] {mid} :: {e}")

                # Commit whatever we managed in this batch
                conn.commit()

                # Small breather to be nice to the server (adjust as needed)
                time.sleep(0.2)

            except Exception as e:
                # Roll back the batch on unexpected DB errors
                conn.rollback()
                print(f"[rollback] Batch failed: {e}")
                # brief pause before retrying next fetch
                time.sleep(1)

    elapsed = time.time() - start
    print(f"[summary] processed={processed}, failures={failures}, wall={elapsed:.1f}s")

if __name__ == "__main__":
    try:
        fill_summaries()
    except KeyboardInterrupt:
        print("\n[stop] Interrupted by user.")
