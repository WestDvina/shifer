import json
import re
import sys
from datetime import datetime, timezone

import requests

from scraper import scrape
from extractor import extract_all


P1_PATTERN = re.compile(r'[?&]P1=(\d+)')


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
            valid_until = datetime.fromtimestamp(
                now.timestamp() + 86400, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

        item = {
            "id": answer.get("question_id", ""),
            "title": answer.get("question_title", ""),
            "question_url": f"https://learn.microsoft.com/ru-ru/answers/questions/{answer.get('question_id', '')}",
            "iso_url": url,
            "author": answer["author"],
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
    print(f"  ISO-related questions: {len(questions)}", file=sys.stderr)

    print("Step 2: Extracting ISO links from answers...", file=sys.stderr)
    iso_answers = extract_all(questions)
    print(f"  Raw ISO links: {len(iso_answers)}", file=sys.stderr)

    print("Step 3: Validating & deduplicating...", file=sys.stderr)
    data = build(iso_answers)
    valid = sum(1 for d in data if d["is_valid"])
    print(f"  Unique: {len(data)}, Valid: {valid}", file=sys.stderr)

    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Written to docs/data.json", file=sys.stderr)


if __name__ == "__main__":
    main()
