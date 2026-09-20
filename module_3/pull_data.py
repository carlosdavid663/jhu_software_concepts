import logging
import time
from pathlib import Path

from sqlalchemy import select

from clean import add_llm_fields, clean_data, save_data
from load_data import insert_applicants
from models import Applicant, Session
from scrape import BASE_URL, USER_AGENT, _download, check_robots, next_page_url, parse_page

FOLDER = Path(__file__).resolve().parent
RUNTIME = FOLDER / "runtime"


def scrape_new_data(existing_urls, report=print, data_dir=RUNTIME):
    """Start at the newest page; stop at a whole page already in the database."""
    robots, delay = check_robots(data_dir=data_dir)
    page_url = BASE_URL + "survey/"
    visited_pages = set()
    seen_urls = set(existing_urls)
    new_rows = []

    while page_url:
        if page_url in visited_pages:
            raise ValueError("The website repeated a page. Collection stopped.")
        if not robots.can_fetch(USER_AGENT, page_url):
            raise ValueError("robots.txt does not allow this page. Collection stopped.")
        time.sleep(delay)  # Respect the site's request spacing, including after robots.txt.
        html = _download(page_url)
        visited_pages.add(page_url)
        page_rows = parse_page(html, page_url)
        if not page_rows:
            break

        for row in page_rows:
            if row.get("url") and row["url"] not in seen_urls:
                new_rows.append(row)
                seen_urls.add(row["url"])
        report(f"Checked {len(visited_pages)} page(s); found {len(new_rows)} new entries.")

        if all(row.get("url") in existing_urls for row in page_rows):
            break
        page_url = next_page_url(html, page_url)

    return new_rows


def pull_new_data(report=print):
    """Return the number inserted and a warning, if LLM names were unavailable."""
    with Session() as session:
        existing_urls = set(session.scalars(select(Applicant.url)).all())

    rows = scrape_new_data(existing_urls, report)
    if not rows:
        return 0, ""

    # Keep the original submission data unchanged. New batches go in runtime/.
    save_data(rows, RUNTIME / "new_raw_data.json")
    report(f"Cleaning {len(rows)} new entries and adding the LLM names. This can take a few minutes.")
    cleaned = clean_data(rows)
    warning = ""
    try:
        applicants = add_llm_fields(cleaned, RUNTIME / "llm_cache.json")
    except Exception:
        # Names are optional. Keep usable entries even if the model fails.
        logging.exception("The LLM could not add names; saving cleaned entries instead.")
        applicants = cleaned
        for applicant in applicants:
            applicant["llm-generated-program"] = None
            applicant["llm-generated-university"] = None
        warning = (
            "LLM names were unavailable. New entries have blank LLM names "
            "and are excluded from the LLM count in Question 9."
        )
        report("LLM names were unavailable. Saving the cleaned entries with blank LLM names.")

    save_data(applicants, RUNTIME / "new_cleaned_data.json")
    inserted, skipped = insert_applicants(applicants)
    return inserted, warning


if __name__ == "__main__":
    inserted, warning = pull_new_data()
    print(f"Added {inserted} new entries.")
    if warning:
        print(warning)
