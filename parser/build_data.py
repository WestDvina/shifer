import json
import re
import sys
from datetime import datetime, timezone

import requests

from scraper import scrape
from extractor import extract_all


P1_PATTERN = re.compile(r'[?&]P1=(\d+)')

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


def validate_link(url):
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            expires = resp.headers.get("expires", "")
            c_len = resp.headers.get("Content-Length", "0")
            return True, expires, int(c_len) if c_len.isdigit() else 0
        return False, "", 0
    except Exception:
        return False, "", 0


def build(iso_answers):
    now = datetime.now(timezone.utc)
    seen = {}

    for answer in iso_answers:
        url = answer["iso_url"]
        if url in seen:
            # Same URL from two origins (e.g. Q&A answer quoting the bot):
            # prefer RuBeRoID authorship — it reflects the live bot pipeline.
            if answer.get("author") == "RuBeRoID" and seen[url].get("author") != "RuBeRoID":
                seen[url]["author"] = "RuBeRoID"
                seen[url]["title"] = answer.get("question_title") or seen[url]["title"]
                seen[url]["question_url"] = answer.get("question_url") or seen[url]["question_url"]
                seen[url]["author_url"] = answer.get("author_url") or seen[url]["author_url"]
            continue

        version = parse_version_from_filename(url)
        if version["lang"] != "Russian":
            continue

        valid, expires_str, size = validate_link(url)

        p1_ts = parse_p1_expiry(url)
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


def main():
    print("Step 1: Scraping MS Q&A...", file=sys.stderr)
    questions = scrape()
    if len(questions) == 0:
        print("ERROR: No questions found — вероятно, Microsoft изменил вёрстку Q&A", file=sys.stderr)
        sys.exit(1)
    print(f"  ISO-related questions: {len(questions)}", file=sys.stderr)

    print("Step 2: Extracting ISO links from answers...", file=sys.stderr)
    iso_answers = extract_all(questions)
    print(f"  Raw ISO links: {len(iso_answers)}", file=sys.stderr)

    print("Step 2b: Fetching RuBeRoID links...", file=sys.stderr)
    rubero = fetch_ruberoID()
    print(f"  RuBeRoID links: {len(rubero)}", file=sys.stderr)
    iso_answers = iso_answers + rubero
    print(f"  Total raw links: {len(iso_answers)}", file=sys.stderr)

    print("Step 3: Validating & deduplicating...", file=sys.stderr)
    data = build(iso_answers)
    valid = sum(1 for d in data if d["is_valid"])
    print(f"  Unique: {len(data)}, Valid: {valid}", file=sys.stderr)

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

    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Written to docs/data.json", file=sys.stderr)


if __name__ == "__main__":
    main()
