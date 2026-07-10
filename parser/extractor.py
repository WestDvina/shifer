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
    suggested = main_entity.get("suggestedAnswer", [])
    if isinstance(suggested, dict):
        suggested = [suggested]

    for answer in suggested:
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

    answers = extract_from_jsonld(html)
    iso_answers = [a for a in answers if a["iso_url"]]
    if not iso_answers:
        return []

    for a in iso_answers:
        a["question_id"] = qid
        a["question_title"] = question["title"]

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
