import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

from scraper import scrape
from extractor import extract_all


P1_PATTERN = re.compile(r'[?&]P1=(\d+)')

# Links live ~24h; history older than this is dead weight (extra CDN HEADs,
# slower runs, noise on the site). 5 days is plenty.
MAX_HISTORY_DAYS = 5


def _history_cutoff():
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(days=MAX_HISTORY_DAYS)


def _parse_ts(value):
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

RUFUS_LINKS_URL = "https://raw.githubusercontent.com/WestDvina/rufus-RuBeRoID/main/iso_links.json"
RUFUS_SOURCE_URL = "https://github.com/WestDvina/rufus-RuBeRoID/blob/main/iso_links.json"


def fetch_ruberoID():
    try:
        resp = requests.get(RUFUS_LINKS_URL, timeout=20,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  RuBeRoID fetch error: {e}", file=sys.stderr)
        return []

    links = data.get("links", {}) if isinstance(data, dict) else {}
    published = data.get("published_at")
    ttl = data.get("ttl_hours")
    answers = []
    for url in links.values():
        if not isinstance(url, str) or "microsoft.com" not in url:
            continue
        answers.append({
            "iso_url": url,
            "author": "RuBeRoID",
            "author_role": "bot",
            "author_url": "https://github.com/WestDvina/rufus-RuBeRoID",
            "question_id": "",
            "question_title": "Ссылки от бота RuBeRoID",
            "question_url": RUFUS_SOURCE_URL,
            "published_at": published,
            "ttl_hours": ttl,
        })
    return answers


def parse_p1_expiry(url):
    m = P1_PATTERN.search(url)
    if m:
        try:
            ts = int(m.group(1))
            if ts > 1700000000:
                return ts
        except ValueError:
            pass
    return None


def parse_version_from_filename(url):
    fname = url.split("/")[-1].split("?")[0].lower()
    info = {"os": "windows", "build": "", "lang": "", "arch": ""}

    if "win11" in fname or "windows11" in fname:
        info["os"] = "win11"
    elif "win10" in fname or "windows10" in fname:
        info["os"] = "win10"

    m = re.search(r'(2[23456]h2)', fname)
    if m:
        info["build"] = m.group(1).upper()
    else:
        BUILD_TO_H2 = {
            "26300": "26H2",
            "26200": "25H2",
            "26100": "24H2",
            "22631": "23H2",
            "22621": "22H2",
            "22000": "21H2",
            "19045": "22H2",
            "19044": "21H2",
            "19043": "21H1",
            "19042": "20H2",
            "19041": "2004",
        }
        b = re.search(r'(2\d{4}|19\d{4})', fname)
        if b and b.group(1) in BUILD_TO_H2:
            info["build"] = BUILD_TO_H2[b.group(1)]

    if "russian" in fname or "ru-ru" in fname:
        info["lang"] = "Russian"
    elif "english" in fname or "en-us" in fname or "english" in fname.split("_"):
        info["lang"] = "English"
    else:
        info["lang"] = "Russian"

    if "x64" in fname or "amd64" in fname:
        info["arch"] = "x64"
    elif "x86" in fname or "x32" in fname:
        info["arch"] = "x86"
    elif "arm64" in fname:
        info["arch"] = "arm64"

    return info


def validate_link(url, attempts=2):
    """HEAD-check with retries. Returns (state, expires, size).

    state True = alive (200), False = definitely dead (404/410),
    None = unknown (timeout/403/429/5xx after retries) — caller must
    preserve the previous status instead of flipping to invalid.
    """
    for i in range(attempts):
        try:
            resp = requests.head(url, timeout=8, allow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                expires = resp.headers.get("expires", "")
                c_len = resp.headers.get("Content-Length", "0")
                return True, expires, int(c_len) if c_len.isdigit() else 0
            if resp.status_code in (404, 410):
                return False, "", 0
            # Other statuses (403/429/5xx): transient, retry.
        except Exception:
            pass  # timeout/DNS: transient, retry.
        if i < attempts - 1:
            time.sleep(3)
    return None, "", 0


def build(iso_answers):
    now = datetime.now(timezone.utc)
    seen = {}

    for answer in iso_answers:
        url = answer["iso_url"]
        if url in seen:
            # Identical signed URLs (= same issuance event) from two origins:
            # keep the first attribution (Q&A answers come first), since the
            # bot/CI merely republished a link minted for that question.
            continue

        version = parse_version_from_filename(url)
        if version["lang"] != "Russian":
            continue

        p1_ts = parse_p1_expiry(url)
        now_ts = now.timestamp()
        expired = bool(p1_ts) and now_ts > p1_ts + 3600

        if expired:
            # P1 already in the past: the signature is cryptographically
            # dead, so there is nothing to confirm on the CDN. Fast path
            # for the majority of historical links (no network call).
            valid, size, expires_str = False, 0, ""
        else:
            valid, expires_str, size = validate_link(url)
            if valid is None:
                # Transient failure (timeout/403/429/5xx): preserve previous
                # status instead of flipping a live link to invalid.
                valid = bool(answer.get("was_valid", False))
                size = answer.get("was_size") or 0
                if valid:
                    print(f"  {url[:60]}...: HEAD inconclusive, keeping previous valid status",
                          file=sys.stderr)

        if p1_ts:
            valid_until = datetime.fromtimestamp(p1_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif valid and expires_str:
            try:
                expires_dt = datetime.strptime(
                    expires_str.replace("GMT", "").strip(),
                    "%a, %d %b %Y %H:%M:%S"
                )
                valid_until = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                valid_until = ""
        else:
            valid_until = ""

        if valid and not valid_until:
            published = answer.get("published_at")
            ttl = answer.get("ttl_hours")
            if published and ttl:
                valid_until = datetime.fromtimestamp(
                    published + ttl * 3600, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                valid_until = datetime.fromtimestamp(
                    now.timestamp() + 86400, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")

        item = {
            "id": answer.get("question_id", ""),
            "title": answer.get("question_title", ""),
            "question_url": answer.get("question_url") or
                f"https://learn.microsoft.com/ru-ru/answers/questions/{answer.get('question_id', '')}",
            "iso_url": url,
            "author": answer["author"],
            "author_url": answer.get("author_url") or
                answer.get("answer_url") or
                answer.get("question_url") or
                f"https://learn.microsoft.com/ru-ru/answers/questions/{answer.get('question_id', '')}",
            "version": version,
            "is_valid": valid,
            "size_bytes": size,
            "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "valid_until": valid_until,
        }
        seen[url] = item

    return list(seen.values())


def load_previous_answers():
    """Previous docs/data.json entries as fallback candidates.

    Q&A support no longer shares direct links, so fresh answers dry up.
    Re-feeding previous URLs keeps history (re-validated in build()).
    """
    try:
        with open("docs/data.json", encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  No previous data.json: {e}", file=sys.stderr)
        return []
    if not isinstance(prev, list):
        return []
    cutoff = _history_cutoff()
    out = []
    for e in prev:
        if not isinstance(e, dict) or ".iso" not in str(e.get("iso_url", "")):
            continue
        ts = _parse_ts(e.get("valid_until"))
        if ts is not None and ts < cutoff:
            continue  # older than MAX_HISTORY_DAYS: dead weight
        out.append({
            "iso_url": e["iso_url"],
            "author": e.get("author", ""),
            "author_url": e.get("author_url", ""),
            "question_id": e.get("id", ""),
            "question_title": e.get("title", ""),
            "question_url": e.get("question_url", ""),
            "was_valid": bool(e.get("is_valid")),
            "was_size": e.get("size_bytes") or 0,
        })
    print(f"  Previous entries reused: {len(out)}", file=sys.stderr)
    return out


def main():
    print("Step 1: Scraping MS Q&A (best-effort)...", file=sys.stderr)
    try:
        questions = scrape()
    except Exception as e:
        print(f"  WARNING: scrape failed, continuing without Q&A: {e}", file=sys.stderr)
        questions = []
    if len(questions) == 0:
        print("  WARNING: no ISO questions (layout change or support stopped sharing links)", file=sys.stderr)
    else:
        print(f"  ISO-related questions: {len(questions)}", file=sys.stderr)

    print("Step 2: Extracting ISO links from answers...", file=sys.stderr)
    iso_answers = extract_all(questions)
    print(f"  Raw ISO links: {len(iso_answers)}", file=sys.stderr)

    print("Step 2b: Fetching RuBeRoID links (canonical source)...", file=sys.stderr)
    rubero = fetch_ruberoID()
    print(f"  RuBeRoID links: {len(rubero)}", file=sys.stderr)
    iso_answers = iso_answers + rubero

    print("Step 2c: Reusing previous data.json entries...", file=sys.stderr)
    iso_answers = iso_answers + load_previous_answers()
    print(f"  Total raw links: {len(iso_answers)}", file=sys.stderr)

    print("Step 3: Validating & deduplicating...", file=sys.stderr)
    data = build(iso_answers)
    valid = sum(1 for d in data if d["is_valid"])
    print(f"  Unique: {len(data)}, Valid: {valid}", file=sys.stderr)

    if len(data) == 0:
        # Never wipe a non-empty file: keep serving stale data over nothing.
        print("ERROR: nothing to write (all sources empty), keeping previous data.json", file=sys.stderr)
        sys.exit(1)

    def sort_key(d):
        is_invalid = not d["is_valid"]
        ts = 0.0
        if d.get("valid_until"):
            try:
                ts = datetime.fromisoformat(d["valid_until"].rstrip("Z")).timestamp()
            except ValueError:
                ts = 0.0
        return (is_invalid, -ts)
    data.sort(key=sort_key)

    # Prune history: no consumer needs entries older than MAX_HISTORY_DAYS
    # (the site hides everything expired >1h ago; Rufus reads iso_links.json).
    cutoff = _history_cutoff()
    before = len(data)
    data = [d for d in data
            if d.get("is_valid") or (_parse_ts(d.get("valid_until")) or cutoff) >= cutoff]
    print(f"  Pruned {before - len(data)} entries older than {MAX_HISTORY_DAYS}d", file=sys.stderr)

    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Written to docs/data.json", file=sys.stderr)


if __name__ == "__main__":
    main()
