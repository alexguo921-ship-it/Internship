"""
共享数据层 — 内部系统与外部门户共用同一份文件存储
portal_data/
  ├── appeals.json      申诉记录（双向读写）
  ├── reports.json      能力发展报告（双向读写）
  ├── analytics.json    仅记录外部门户访问
  └── candidates.csv    候选人数据（内部导出，外部只读）
"""

import json, os
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent / "portal_data"
DATA_DIR.mkdir(exist_ok=True)

APPEALS_FILE   = DATA_DIR / "appeals.json"
REPORTS_FILE   = DATA_DIR / "reports.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"
CANDIDATES_FILE= DATA_DIR / "candidates.csv"


def _load(path, default):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ── Appeals ──────────────────────────────────────────────────
def load_appeals():  return _load(APPEALS_FILE, {})
def save_appeals(d): _save(APPEALS_FILE, d)


# ── Reports ──────────────────────────────────────────────────
def load_reports():  return _load(REPORTS_FILE, {})
def save_reports(d): _save(REPORTS_FILE, d)


# ── Analytics（外部门户专用）────────────────────────────────
def load_analytics(): return _load(ANALYTICS_FILE, {"visits": []})

def record_visit(session_id: str, page: str):
    data = load_analytics()
    data["visits"].append({
        "ts":  datetime.now().isoformat(timespec="seconds"),
        "sid": session_id,
        "page": page,
    })
    data["visits"] = data["visits"][-20000:]   # 最多保留 2 万条
    _save(ANALYTICS_FILE, data)

def get_portal_stats(active_minutes: int = 15) -> dict:
    data    = load_analytics()
    visits  = data["visits"]
    today   = datetime.now().date().isoformat()
    cutoff  = (datetime.now() - timedelta(minutes=active_minutes)).isoformat()
    today_v = [v for v in visits if v["ts"][:10] == today]
    recent  = [v for v in visits if v["ts"] >= cutoff]
    active  = len(set(v["sid"] for v in recent))
    return {
        "total":   len(visits),
        "today":   len(today_v),
        "active":  active,
        "visits":  visits,
    }


# ── Candidates CSV（内部写，外部读）────────────────────────
def candidates_exist() -> bool:
    return CANDIDATES_FILE.exists()

def load_candidates():
    import pandas as pd
    if CANDIDATES_FILE.exists():
        return pd.read_csv(CANDIDATES_FILE)
    return None

def save_candidates(df):
    import pandas as pd
    df.to_csv(CANDIDATES_FILE, index=False)


# ── Submissions (外部自主投递) ──────────────────────────────
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"

def load_submissions():  return _load(SUBMISSIONS_FILE, {})
def save_submissions(d): _save(SUBMISSIONS_FILE, d)
