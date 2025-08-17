import os
import sqlite3
import json
import feedparser
from datetime import datetime, timedelta
from time import mktime, sleep
from urllib.parse import quote_plus
print('❌ Do not use, does not work! ❌')

# --- CONFIG ---
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manuscript_db.db")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "data", "backfill_checkpoints.json")
ARXIV_API_URL = "http://export.arxiv.org/api/query"
BATCH_SIZE = 200
SEGMENT_LENGTH_DAYS = 8

# --- CATEGORIES ---
SEARCH_CATEGORIES = [
    "astro-ph", "cond-mat.dis-nn", "cond-mat.mes-hall", "cond-mat.mtrl-sci", "cond-mat.other",
    "cond-mat.quant-gas", "cond-mat.soft", "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con",
    "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th", "math-ph", "nlin.AO", "nlin.CD", "nlin.CG",
    "nlin.PS", "nlin.SI", "nucl-ex", "nucl-th", "physics.acc-ph", "physics.ao-ph", "physics.app-ph",
    "physics.atm-clus", "physics.atom-ph", "physics.bio-ph", "physics.chem-ph", "physics.class-ph",
    "physics.comp-ph", "physics.data-an", "physics.ed-ph", "physics.flu-dyn", "physics.gen-ph",
    "physics.geo-ph", "physics.hist-ph", "physics.ins-det", "physics.med-ph", "physics.optics",
    "physics.plasm-ph", "physics.pop-ph", "physics.soc-ph", "physics.space-ph", "quant-ph",
    "math.AC", "math.AG", "math.AP", "math.AT", "math.CA", "math.CO", "math.CT", "math.CV",
    "math.DG", "math.DS", "math.FA", "math.GM", "math.GN", "math.GR", "math.GT", "math.HO",
    "math.IT", "math.KT", "math.LO", "math.MG", "math.MP", "math.NA", "math.NT", "math.OA",
    "math.OC", "math.PR", "math.QA", "math.RA", "math.RT", "math.SG", "math.SP", "math.ST",
    "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL", "cs.CR", "cs.CV", "cs.CY", "cs.DB",
    "cs.DC", "cs.DL", "cs.DM", "cs.DS", "cs.ET", "cs.FL", "cs.GL", "cs.GR", "cs.GT", "cs.HC",
    "cs.IR", "cs.IT", "cs.LG", "cs.LO", "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE", "cs.NI",
    "cs.OH", "cs.OS", "cs.PF", "cs.PL", "cs.RO", "cs.SC", "cs.SD", "cs.SE", "cs.SI", "cs.SY",
    "stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH",
    "q-bio.BM", "q-bio.CB", "q-bio.GN", "q-bio.MN", "q-bio.NC", "q-bio.OT", "q-bio.PE",
    "q-bio.QM", "q-bio.SC", "q-bio.TO",
    "q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF", "q-fin.PM", "q-fin.PR", "q-fin.RM", "q-fin.ST", "q-fin.TR",
    "eess.AS", "eess.IV", "eess.SP", "eess.SY",
    "econ.EM", "econ.GN", "econ.TH"
]

# --- CHECKPOINT UTILS ---
def load_checkpoints():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r") as f:
            return json.load(f)
    return {}

def save_checkpoints(data):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2)

def is_segment_done(checkpoints, category, seg_str):
    return category in checkpoints and seg_str in checkpoints[category]

def mark_segment_done(checkpoints, category, seg_str):
    checkpoints.setdefault(category, []).append(seg_str)
    save_checkpoints(checkpoints)

# --- DATE UTILS ---
def daterange(start_date, end_date, delta=timedelta(days=7)):
    current = start_date
    while current < end_date:
        yield current, min(current + timedelta(days=SEGMENT_LENGTH_DAYS), end_date)
        current += delta

def format_arxiv_date(dt):
    return dt.strftime("%Y%m%d")

# --- FETCH ---
def fetch_arxiv_segment(category, start_date, end_date):
    all_papers = []
    start = 0
    date_filter = f"[{format_arxiv_date(start_date)}0000 TO {format_arxiv_date(end_date)}2359]"
    query = quote_plus(f"cat:{category} AND submittedDate:{date_filter}")

    while True:
        url = (
            f"{ARXIV_API_URL}?search_query={query}"
            f"&start={start}&max_results={BATCH_SIZE}"
            f"&sortBy=submittedDate&sortOrder=ascending"
        )
        print(f"Fetching {category} from {start_date.date()} to {end_date.date()} ({start}–{start + BATCH_SIZE - 1})")
        feed = feedparser.parse(url)

        if not feed.entries:
            break

        for entry in feed.entries:
            published = datetime.fromtimestamp(mktime(entry.published_parsed))
            arxiv_id = entry.id.split('/')[-1]
            title = entry.title.strip().replace('\n', ' ')
            abstract = entry.summary.strip().replace('\n', ' ')
            authors = [a.name for a in entry.authors]
            keywords = [t["term"] for t in entry.tags] if "tags" in entry else []
            link = entry.link

            all_papers.append({
                "id": arxiv_id,
                "title": title,
                "authors": json.dumps(authors),
                "orcids": json.dumps([]),
                "keywords": json.dumps(keywords),
                "abstract": abstract,
                "link": link,
                "published_timestamp": published.isoformat(),
                "added_timestamp": datetime.utcnow().isoformat()
            })

        start += BATCH_SIZE
        sleep(1)

    return all_papers

# --- DB INSERT ---
def insert_papers(papers):
    if not papers:
        return 0

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        new_count = 0
        for paper in papers:
            try:
                cursor.execute("""
                    INSERT INTO manuscripts (
                        id, title, authors, orcids, keywords, abstract,
                        link, published_timestamp, added_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper["id"], paper["title"], paper["authors"], paper["orcids"],
                    paper["keywords"], paper["abstract"], paper["link"],
                    paper["published_timestamp"], paper["added_timestamp"]
                ))
                cursor.execute("""
                    INSERT INTO fts_manuscripts (
                        rowid, title, abstract, keywords, authors
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    paper["id"], paper["title"], paper["abstract"],
                    paper["keywords"], paper["authors"]
                ))
                new_count += 1
            except sqlite3.IntegrityError:
                continue
        conn.commit()
    return new_count

# --- MAIN ---
def backfill(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    checkpoints = load_checkpoints()
    total_added = 0

    for seg_start, seg_end in daterange(start_date, end_date):
        seg_str = f"{seg_start.date()}_{seg_end.date()}"
        for category in SEARCH_CATEGORIES:
            if is_segment_done(checkpoints, category, seg_str):
                continue

            papers = fetch_arxiv_segment(category, seg_start, seg_end)
            added = insert_papers(papers)
            print(f"→ {added} new entries added.")
            total_added += added
            mark_segment_done(checkpoints, category, seg_str)

    print(f"\n✅ Backfill completed. Total new entries: {total_added}")

if __name__ == "__main__":
    backfill("2024-08-01", "2025-08-01")
