"""Collect, clean and load new records; model failures preserve usable data."""
import logging
import time
from pathlib import Path

from .database import connect

from .clean import add_llm_fields, clean_data, save_data
from .load_data import insert_applicants
from .paths import PROJECT_FOLDER
from .scrape import BASE_URL, USER_AGENT, _download, check_robots, next_page_url, parse_page

RUNTIME = PROJECT_FOLDER / "runtime"


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
        page_html = _download(page_url)
        visited_pages.add(page_url)
        page_rows = parse_page(page_html, page_url)
        if not page_rows:
            break

        for row in page_rows:
            if row.get("url") and row["url"] not in seen_urls:
                new_rows.append(row)
                seen_urls.add(row["url"])
        report(f"Checked {len(visited_pages)} page(s); found {len(new_rows)} new entries.")

        # A whole page of existing entries means we have caught up.
        whole_page_already_saved = True
        for applicant in page_rows:
            if applicant.get("url") not in existing_urls:
                whole_page_already_saved = False
                break
        if whole_page_already_saved:
            break
        page_url = next_page_url(page_html, page_url)

    return new_rows


def prepare_applicants(database_url=None, report=print, data_dir=None):
    """Return cleaned rows and a warning if the optional model is unavailable."""
    if data_dir is None:
        data_dir = RUNTIME
    data_dir = Path(data_dir)
    with connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT url FROM applicants")
            # A set stores unique values and makes URL lookups straightforward.
            existing_urls = set()
            for database_row in cursor.fetchall():
                existing_urls.add(database_row[0])

    rows = scrape_new_data(existing_urls, report, data_dir)
    if not rows:
        return [], ""

    # Keep the original submission data unchanged. New batches go in runtime/.
    save_data(rows, data_dir / "new_raw_data.json")
    report(f"Cleaning {len(rows)} new entries and adding the LLM names. This can take a few minutes.")
    cleaned = clean_data(rows)
    warning = ""
    try:
        applicants = add_llm_fields(cleaned, data_dir / "llm_cache.json")
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

    save_data(applicants, data_dir / "new_cleaned_data.json")
    return applicants, warning


def pull_new_data(report=print, database_url=None):
    """Complete a pull and return the number inserted plus any model warning."""
    applicants, warning = prepare_applicants(database_url, report)
    inserted, skipped = insert_applicants(applicants, database_url)
    return inserted, warning


if __name__ == "__main__":
    inserted, warning = pull_new_data()
    print(f"Added {inserted} new entries.")
    if warning:
        print(warning)
