"""Collect public GradCafe results with simple functions and saved progress.

Try one page first: python scrape.py --limit 20
Collect separately: python scrape.py --data-dir ../fresh_collection --limit 30020
Read scrape_data() to see the overall collection loop.
"""

import argparse
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from clean import load_data, save_data


FOLDER = Path(__file__).resolve().parent
BASE_URL = "https://www.thegradcafe.com/"
USER_AGENT = "GradCafeCourseProject/1.0"
RESULT_LINK = re.compile(r"/result/\d+/?$")


class _NoRedirects(HTTPRedirectHandler):
    """Do not follow a redirect into a login or verification page."""

    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _download(url):
    """Request a public page once. Any rejection stops the caller."""
    parts = urlparse(url)
    if (parts.scheme != "https" or parts.netloc != "www.thegradcafe.com" or
            parts.path not in ("/robots.txt", "/survey/", "/survey")):
        raise ValueError("Only GradCafe's public results and robots.txt are permitted.")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    opener = build_opener(_NoRedirects())
    with opener.open(request, timeout=60) as response:
        final_url = urlparse(response.url)
        if final_url.hostname != "www.thegradcafe.com":
            raise ValueError("Unexpected redirect. Collection stopped.")
        if final_url.path not in ("/robots.txt", "/survey/", "/survey"):
            raise ValueError("The site redirected away from public results. Stopped.")
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def _robots_parser(text):
    """Combine repeated applicable groups, including the site's two * groups.

    The standard parser otherwise selects just its first matching group.
    A more specific path should be considered before a broad Allow: / rule.
    """
    groups = []
    agents = []
    rules = []
    for line in text.splitlines() + ["User-agent: end-of-file"]:
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif agents:
            rules.append((key, value))

    specific = []
    general = []
    for agents, rules in groups:
        if any(agent != "*" and agent in USER_AGENT.lower() for agent in agents):
            specific.extend(rules)
        elif "*" in agents:
            general.extend(rules)
    selected = specific or general
    paths = [(key, value) for key, value in selected if key in ("allow", "disallow")]
    if any("*" in value or "$" in value for key, value in paths):
        raise ValueError("These robots rules use patterns this simple parser cannot verify. Stopped.")
    paths.sort(key=lambda rule: (len(rule[1]), rule[0] == "allow"), reverse=True)
    other_rules = [(key, value) for key, value in selected if key not in ("allow", "disallow")]
    parser = RobotFileParser()
    parser.parse(["User-agent: *"] + [f"{key}: {value}" for key, value in paths + other_rules])
    return parser


def check_robots(min_delay=5, data_dir=FOLDER):
    """Read the rules, save the evidence, and choose a polite delay."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    url = urljoin(BASE_URL, "robots.txt")
    text = _download(url)
    if "<html" in text.lower() or "user-agent:" not in text.lower():
        raise ValueError("The robots response was not a usable robots.txt file.")
    (data_dir / "robots.txt").write_bytes(text.encode("utf-8"))
    parser = _robots_parser(text)
    results_url = urljoin(BASE_URL, "survey/")
    allowed = parser.can_fetch(USER_AGENT, results_url)
    save_data({"checked_at_utc": datetime.now(timezone.utc).isoformat(),
               "url": url, "user_agent": USER_AGENT,
               "results_url": results_url, "results_allowed": allowed},
              data_dir / "robots_check.json")
    if not allowed:
        raise ValueError("robots.txt disallows these results for this user agent.")
    delay = parser.crawl_delay(USER_AGENT) or 0
    rate = parser.request_rate(USER_AGENT)
    if rate and rate.requests:
        delay = max(delay, rate.seconds / rate.requests)
    return parser, max(2, min_delay, delay)


def _column(headers, *names):
    """Find a column by its heading rather than assuming its position."""
    for name in names:
        if name in headers:
            return headers.index(name)
    raise ValueError(f"Missing column: {names[0]}. Check the saved HTML and update the parser.")


def _match(pattern, text):
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else None


def _parse_entry(main_row, extra_rows, headers, page_url):
    """Read one applicant's table row plus its following detail rows."""
    cells = main_row.find_all("td", recursive=False)
    cell_text = [cell.get_text(" ", strip=True) for cell in cells]
    university = cell_text[_column(headers, "school", "university", "institution")]
    program_cell = cells[_column(headers, "program")]
    program_text = program_cell.get_text(" ", strip=True)
    program_parts = [span.get_text(" ", strip=True) for span in program_cell.find_all("span")]
    if len(program_parts) == 2:
        # The live page has one span for the program and one for the degree.
        program_name, degree = program_parts
    else:
        degree = _match(r"\b(Ph\.?D\.?|Masters?|Master's|MBA|MFA|Other)\b", program_text)
        program_name = re.sub(r"\s*[,·]?\s*\b(Ph\.?D\.?|Masters?|Master's|MBA|MFA|Other)\s*$",
                              "", program_text, flags=re.I).strip()
    program = f"{program_name}, {university}"
    details = " ".join(row.get_text(" ", strip=True) for row in extra_rows)
    # Current badges are divs; older pages used spans. Exclude comment rows
    # so a score mentioned in someone's story is not mistaken for a badge.
    badges = " ".join(row.get_text(" ", strip=True)
                      for row in extra_rows if row.find("p") is None)
    comments = " ".join(p.get_text(" ", strip=True)
                        for row in extra_rows for p in row.find_all("p"))
    link = main_row.find("a", href=RESULT_LINK)
    record_url = urljoin(BASE_URL, link["href"])
    if urlparse(record_url).hostname != "www.thegradcafe.com":
        raise ValueError("Unexpected applicant URL.")

    row = {"program": program, "program_name": program_name, "university": university,
           "comments": comments or None,
           "date_added": cell_text[_column(headers, "date added", "added on", "date")],
           "url": record_url,
           "status": cell_text[_column(headers, "decision", "status")],
           "term": _match(r"\b((?:Fall|Spring|Summer|Winter)\s+\d{4})\b", badges),
           "US/International": _match(r"\b(American|International|Other)\b", badges),
           "Degree": degree,
           "raw_program": program,
           "raw_program_cell": program_text,
           "raw_listing": " ".join(cell_text) + " " + details,
           "source_page": page_url}
    for key, pattern in {"GPA": r"\bGPA\s*:?\s*(\d+(?:\.\d+)?)\b",
                         "GRE": r"\bGRE\s*:?\s*(\d+(?:\.\d+)?)\b",
                         "GRE V": r"\bGRE\s*V\s*:?\s*(\d+(?:\.\d+)?)\b",
                         "GRE AW": r"\bGRE\s*AW\s*:?\s*(\d+(?:\.\d+)?)\b"}.items():
        row[key] = _match(pattern, badges)
    return row


def parse_page(page_html, page_url):
    """Parse the common results-table layout; stop if it is not recognized."""
    soup = BeautifulSoup(page_html, "html.parser")
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if any(message in title for message in ("just a moment", "access denied", "verify")):
        raise ValueError("A verification/block page was returned. Collection stopped.")
    table = None
    for candidate in soup.find_all("table"):
        if candidate.find("a", href=RESULT_LINK):
            table = candidate
            break
    if table is None:
        raise ValueError("No results table found. Stop and inspect the saved page.")
    headers = [" ".join(th.get_text(" ", strip=True).lower().split())
               for th in table.find_all("th")]
    records = []
    main_row = None
    extra_rows = []
    for row in table.find_all("tr"):
        if row.find("a", href=RESULT_LINK):
            if main_row is not None:
                records.append(_parse_entry(main_row, extra_rows, headers, page_url))
            main_row, extra_rows = row, []
        elif main_row is not None:
            extra_rows.append(row)
    if main_row is not None:
        records.append(_parse_entry(main_row, extra_rows, headers, page_url))
    return records


def next_page_url(page_html, current_url):
    """Read the real Next link. Cursor values come from the site, not guesses."""
    soup = BeautifulSoup(page_html, "html.parser")
    for link in soup.find_all("a", href=True):
        label = link.get_text(" ", strip=True).lower()
        if label == "next" or link.get("aria-label", "").lower() == "next":
            url = urljoin(current_url, link["href"])
            parts = urlparse(url)
            if parts.scheme != "https" or parts.hostname != "www.thegradcafe.com" or parts.path.rstrip("/") != "/survey":
                raise ValueError("Unexpected Next link. Collection stopped.")
            return url
    return None


def scrape_data(limit=20, delay_seconds=5, data_dir=FOLDER):
    """Load progress, collect one page at a time, and save after each page."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = data_dir / "raw_applicant_data.json"
    checkpoint_file = data_dir / "scrape_progress.json"
    rows = load_data(data_file) if data_file.exists() else []
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Raw data must be a JSON array of applicant objects.")
    if not all(isinstance(row.get("url"), str) for row in rows):
        raise ValueError("Every saved applicant needs a text URL.")
    seen_urls = {row["url"] for row in rows}
    if len(seen_urls) != len(rows):
        raise ValueError("Saved data contains duplicate applicant URLs.")
    if len(rows) >= limit:
        print(f"Already have {len(rows)} rows; no requests needed.")
        return rows

    if checkpoint_file.exists():
        progress = load_data(checkpoint_file)
        if not isinstance(progress, dict) or "next_page" not in progress or "next_url" not in progress:
            raise ValueError("Invalid checkpoint. Restore it with its matching raw data.")
        if not rows and progress["next_page"] != 1:
            raise ValueError("A checkpoint exists without its matching raw data.")
    else:
        if rows:
            raise ValueError("Raw data exists without scrape_progress.json. Restore the matching "
                             "checkpoint or choose a new --data-dir for a fresh collection.")
        progress = {"next_page": 1, "next_url": urljoin(BASE_URL, "survey")}
        # Save this before the first request, even before any raw data exists.
        save_data(progress, checkpoint_file)

    page_number = progress["next_page"]
    page_url = progress["next_url"]
    if not isinstance(page_number, int) or page_number < 1:
        raise ValueError("The checkpoint has an invalid page number.")
    if page_url is None:
        raise ValueError("The saved collection already reached the final results page.")
    robots, delay = check_robots(delay_seconds, data_dir)
    pages_dir = data_dir / "saved_pages"
    pages_dir.mkdir(exist_ok=True)
    next_request_at = time.monotonic() + delay

    while len(rows) < limit:
        if not robots.can_fetch(USER_AGENT, page_url):
            raise ValueError("robots.txt disallows the next page. Collection stopped.")
        pause = next_request_at - time.monotonic()
        if pause > 0:
            time.sleep(pause)
        next_request_at = time.monotonic() + delay
        page_html = _download(page_url)
        (pages_dir / f"page_{page_number:04d}.html").write_bytes(page_html.encode("utf-8"))
        page_rows = parse_page(page_html, page_url)
        following_url = next_page_url(page_html, page_url)

        previous_count = len(rows)
        for row in page_rows:
            if row["url"] not in seen_urls:
                rows.append(row)
                seen_urls.add(row["url"])
        if len(rows) == previous_count:
            # A stopped run may have saved this page just before its checkpoint.
            saved_here = {row["url"] for row in rows if row.get("source_page") == page_url}
            if not page_rows or any(row["url"] not in saved_here for row in page_rows):
                raise ValueError("This page adds no new applicants. Collection stopped.")

        save_data(rows, data_file)
        page_number += 1
        save_data({"next_page": page_number, "next_url": following_url}, checkpoint_file)
        print(f"Saved {len(rows)} applicants.", flush=True)
        if len(rows) < limit and (following_url is None or following_url == page_url):
            raise ValueError("No new Next link is available. Saved data is kept.")
        page_url = following_url
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="Number of applicants to collect")
    parser.add_argument("--delay", type=float, default=5, help="Minimum seconds between request starts")
    parser.add_argument("--data-dir", type=Path, default=FOLDER, help="Folder for raw data and progress")
    parser.add_argument("--robots-only", action="store_true", help="Check the rules without collecting")
    args = parser.parse_args()
    if args.limit < 1 or args.delay < 2:
        parser.error("Use a positive --limit and a --delay of at least two seconds.")
    data_dir = args.data_dir.expanduser().resolve()
    try:
        if args.robots_only:
            check_robots(args.delay, data_dir)
            print("Saved robots.txt and robots_check.json. Also take screenshot.jpg.")
        else:
            scrape_data(args.limit, args.delay, data_dir)
    except (HTTPError, URLError, OSError, ValueError, IndexError, KeyError) as error:
        parser.exit(1, f"Stopped: {error}\nPreviously saved data is kept.\n")
    except KeyboardInterrupt:
        parser.exit(1, "Stopped. Run the same command to resume completed pages.\n")


if __name__ == "__main__":
    main()
