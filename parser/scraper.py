import re
import sys
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from config import QUESTIONS_URL, LOCALE, FILTER_KEYWORDS, PAGE_SIZE, MAX_PAGES

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_list_page(page=1):
    url = f"{QUESTIONS_URL}/?orderby=createdat&page={page}"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_questions(html):
    soup = BeautifulSoup(html, "lxml")
    questions = []
    for card in soup.select("div.box.margin-bottom-xxs"):
        link_tag = card.select_one("h2.title a")
        if not link_tag:
            continue
        href = link_tag.get("href", "")
        title = link_tag.get_text(strip=True)
        qid_match = re.search(r"/questions/(\d+)", href)
        if not qid_match:
            continue
        qid = qid_match.group(1)

        body_el = card.select_one("p.has-text-wrap")
        body = body_el.get_text(strip=True) if body_el else ""

        badge_el = card.select_one(".badge.badge-success")
        answer_count = 0
        if badge_el:
            txt = badge_el.get_text(strip=True)
            m = re.search(r"(\d+)", txt)
            if m:
                answer_count = int(m.group(1))

        author_els = card.select("[data-test-id='question-details-author']")
        created_at = ""
        if author_els:
            ts_el = author_els[0].select_one("local-time")
            if ts_el:
                created_at = ts_el.get("datetime", "")

        tags = []
        for tag_el in card.select("span.tag span.tag-summary"):
            tags.append(tag_el.get_text(strip=True))

        questions.append({
            "id": qid,
            "title": title,
            "url": f"https://learn.microsoft.com{href}",
            "body": body,
            "answer_count": answer_count,
            "created_at": created_at,
            "tags": tags,
        })
    return questions


def is_iso_request(question):
    text = (question["title"] + " " + question["body"]).lower()
    return any(kw.lower() in text for kw in FILTER_KEYWORDS)


def scrape_list(max_pages=MAX_PAGES):
    all_questions = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for page in range(1, max_pages + 1):
        print(f"  Fetching page {page}...", file=sys.stderr)
        try:
            html = fetch_list_page(page)
        except Exception as e:
            print(f"  Error page {page}: {e}", file=sys.stderr)
            break
        questions = parse_questions(html)
        if not questions:
            print(f"  No questions found", file=sys.stderr)
            break
        all_questions.extend(questions)

        last_date = questions[-1].get("created_at", "")
        if last_date:
            try:
                dt = datetime.fromisoformat(last_date.replace("Z", "+00:00"))
                if dt < cutoff:
                    print(f"  Reached cutoff ({last_date})", file=sys.stderr)
                    break
            except ValueError:
                pass
    return all_questions


def scrape():
    questions = scrape_list()
    iso_questions = [q for q in questions if is_iso_request(q)]
    print(f"  Total questions: {len(questions)}, ISO requests: {len(iso_questions)}", file=sys.stderr)
    return iso_questions


if __name__ == "__main__":
    qs = scrape()
    import json
    print(json.dumps(qs, ensure_ascii=False, indent=2))
