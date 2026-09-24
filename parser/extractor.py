import html as _html
import json
import re
import sys
import requests
from bs4 import BeautifulSoup
from config import ISO_LINK_PATTERN

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_question_page(url):
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_from_jsonld(html):
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", type="application/ld+json")
    if not script:
        return []
    try:
        data = json.loads(script.string)
    except (json.JSONDecodeError, TypeError):
        return []

    answers = []
    main_entity = data.get("mainEntity", {})

    def extract_from(answer):
        text = _html.unescape(answer.get("text", ""))
        author = answer.get("author", "")
        role = answer.get("authorRole", "")
        iso_urls = re.findall(ISO_LINK_PATTERN, text)
        for url in iso_urls:
            answers.append({
                "author": author,
                "author_role": role,
                "iso_url": url,
            })

    accepted = main_entity.get("acceptedAnswer", [])
    if isinstance(accepted, dict):
        accepted = [accepted]
    for answer in accepted:
        extract_from(answer)

    suggested = main_entity.get("suggestedAnswer", [])
    if isinstance(suggested, dict):
        suggested = [suggested]
    for answer in suggested:
        extract_from(answer)

    return answers


def extract_from_html(html):
    soup = BeautifulSoup(html, "lxml")
    answers = []
    for el in soup.select('[data-test-id^="answer-"]'):
        if el.get("id", "").startswith("answer-"):
            author_el = el.select_one('[data-test-id="answer-author"] a.profile-url')
            author = author_el.get_text(strip=True) if author_el else ""
            role_el = el.select_one('[data-test-id="answer-author"] .has-text-subtle')
            role = role_el.get_text(" ", strip=True) if role_el else ""
            text_el = el.select_one('.content[itemprop="text"]')
            if not text_el:
                continue
            text = _html.unescape(text_el.decode_contents())
            iso_urls = re.findall(ISO_LINK_PATTERN, text)
            for url in iso_urls:
                answers.append({
                    "author": author,
                    "author_role": role,
                    "iso_url": url,
                })
    return answers


def extract_from_question(question):
    qid = question["id"]
    url = question["url"]
    print(f"  Fetching {qid}...", file=sys.stderr)
    try:
        html = fetch_question_page(url)
    except Exception as e:
        print(f"    Error: {e}", file=sys.stderr)
        return []

    answers = extract_from_html(html) + extract_from_jsonld(html)
    iso_answers = []
    seen = set()
    for a in answers:
        u = a["iso_url"]
        if not u or u in seen:
            continue
        seen.add(u)
        a["question_id"] = qid
        a["question_title"] = question["title"]
        iso_answers.append(a)

    if not iso_answers:
        return []

    print(f"    Found {len(iso_answers)} ISO link(s) from {iso_answers[0]['author']}", file=sys.stderr)
    return iso_answers


def extract_all(questions):
    all_answers = []
    for q in questions:
        answers = extract_from_question(q)
        all_answers.extend(answers)
    return all_answers


if __name__ == "__main__":
    questions = json.loads(sys.stdin.read())
    results = extract_all(questions)
    print(json.dumps(results, ensure_ascii=False, indent=2))
