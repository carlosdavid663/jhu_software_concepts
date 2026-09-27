"""Connect the webpage buttons to the data and database functions.

Read create_app first, then analysis, pull, and update.
Run from module_4 with: python -m src.app
"""
import os
from datetime import datetime, timezone
from threading import Lock, Thread

from flask import Flask, current_app, jsonify, render_template

from .load_data import insert_applicants
from .orm_queries import run_orm_queries
from .pull_data import prepare_applicants
from .query_data import QUERIES, formatted_rows


def create_app(config=None, *, scraper=None, loader=None, query=None, runner=None):
    """Build a new website with its own settings and progress information.

    The optional functions let tests replace slow work with small examples.
    For example, scraper() returns rows and loader(rows) saves those rows.
    Normal users can call create_app() without providing any of them.
    """
    web_app = Flask(__name__)
    web_app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")
    web_app.config["PULL_SYNCHRONOUS"] = False
    if config is not None:
        web_app.config.update(config)

    # A dictionary stores information that the page and data worker share.
    page_state = {
        "busy": False,
        "message": "Ready.",
        "results": {},
        "updated": None,
        "error": False,
        "warning": "",
    }
    web_app.extensions["gradcafe"] = {
        "state": page_state,
        "lock": Lock(),
        "scraper": scraper,
        "loader": loader,
        "query": query,
        "runner": runner,
    }

    # A route connects a website address to the function that handles it.
    web_app.add_url_rule("/", view_func=analysis)
    web_app.add_url_rule("/analysis", view_func=analysis)
    web_app.add_url_rule("/pull-data", view_func=pull, methods=["POST"])
    web_app.add_url_rule("/update-analysis", view_func=update, methods=["POST"])
    web_app.add_url_rule("/pull", view_func=pull, methods=["POST"])
    web_app.add_url_rule("/update", view_func=update, methods=["POST"])
    return web_app


def start_worker(job):
    """Run a job in the background so the webpage can still respond."""
    background_thread = Thread(target=job, daemon=True)
    background_thread.start()


def update_message(web_app, message):
    """Change the progress message while holding the shared lock."""
    app_data = web_app.extensions["gradcafe"]
    # Only one thread can enter a block protected by this lock at a time.
    with app_data["lock"]:
        app_data["state"]["message"] = message


def collect_rows(web_app):
    """Use a test scraper if provided; otherwise collect real new entries."""
    app_data = web_app.extensions["gradcafe"]
    scraper_function = app_data["scraper"]
    if scraper_function is not None:
        return scraper_function()

    # The collector calls this short function when its progress changes.
    def report_progress(message):
        update_message(web_app, message)

    applicants, warning = prepare_applicants(
        web_app.config["DATABASE_URL"], report=report_progress
    )
    with app_data["lock"]:
        app_data["state"]["warning"] = warning
    return applicants


def save_rows(web_app, applicants):
    """Use a test loader if provided; otherwise write to PostgreSQL."""
    loader_function = web_app.extensions["gradcafe"]["loader"]
    if loader_function is not None:
        return loader_function(applicants)
    return insert_applicants(applicants, web_app.config["DATABASE_URL"])


def refresh_analysis(web_app):
    """Read new answers, then replace the old answers only after success.

    The calling route holds the lock so a pull cannot start during this work.
    """
    app_data = web_app.extensions["gradcafe"]
    query_function = app_data["query"]
    if query_function is not None:
        new_results = query_function()
    else:
        new_results = run_orm_queries(web_app.config["DATABASE_URL"])

    page_state = app_data["state"]
    page_state["results"] = new_results
    page_state["updated"] = datetime.now(timezone.utc).isoformat()


def run_pull(web_app):
    """Collect and save entries. Return True on success and False on failure."""
    app_data = web_app.extensions["gradcafe"]
    page_state = app_data["state"]
    try:
        applicants = collect_rows(web_app)
        inserted_count, skipped_count = save_rows(web_app, applicants)
        message = (
            f"Pull finished: added {inserted_count} entries; skipped {skipped_count}. "
            "Click Update Analysis. " + page_state["warning"]
        )
        update_message(web_app, message)
        return True
    except Exception:
        # Save details in the server log and show a short message on the page.
        web_app.logger.exception("Pull Data failed")
        with app_data["lock"]:
            page_state["error"] = True
            page_state["message"] = "Could not finish the pull. Check the server log."
        return False
    finally:
        # finally runs on both success and failure, including before a return.
        with app_data["lock"]:
            page_state["busy"] = False


def analysis():
    """Handle GET /analysis: prepare the answers and display the HTML page."""
    web_app = current_app
    app_data = web_app.extensions["gradcafe"]
    page_state = app_data["state"]

    with app_data["lock"]:
        if not page_state["results"] and not page_state["busy"]:
            try:
                refresh_analysis(web_app)
            except Exception:
                web_app.logger.exception("Database unavailable")
                page_state["message"] = "Database unavailable. Check DATABASE_URL and load the data."
        page_snapshot = page_state.copy()

    answer_cards = []
    for question in QUERIES:
        question_number = question["number"]
        answer_rows = page_snapshot["results"].get(question_number, [])
        card = question.copy()
        card["rows"] = formatted_rows(question, answer_rows)
        answer_cards.append(card)

    return render_template("index.html", cards=answer_cards, state=page_snapshot)


def pull():
    """Handle the Pull Data button. Return 409 if a pull is already running."""
    # A background thread needs the actual app, not Flask's request shortcut.
    web_app = current_app._get_current_object()
    app_data = web_app.extensions["gradcafe"]
    page_state = app_data["state"]

    with app_data["lock"]:
        if page_state["busy"]:
            return jsonify(busy=True), 409
        page_state["busy"] = True
        page_state["error"] = False
        page_state["warning"] = ""
        page_state["message"] = "Pulling new entries. Please wait."

    try:
        if web_app.config["PULL_SYNCHRONOUS"]:
            # Tests can finish the job immediately instead of starting a thread.
            pull_succeeded = run_pull(web_app)
            if pull_succeeded:
                return jsonify(ok=True), 200
            return jsonify(ok=False), 500

        # The runner expects a function it can call later, without arguments.
        def background_job():
            run_pull(web_app)

        runner_function = app_data["runner"]
        if runner_function is None:
            runner_function = start_worker
        runner_function(background_job)
    except Exception:
        web_app.logger.exception("Could not start worker")
        with app_data["lock"]:
            page_state["busy"] = False
            page_state["error"] = True
            page_state["message"] = "Could not start the pull. Please try again."
        return jsonify(ok=False), 500

    # 202 means the request was accepted and the background work has started.
    return jsonify(ok=True), 202


def update():
    """Handle Update Analysis. Keep the old answers if the database fails."""
    web_app = current_app
    app_data = web_app.extensions["gradcafe"]
    page_state = app_data["state"]

    with app_data["lock"]:
        if page_state["busy"]:
            return jsonify(busy=True), 409
        try:
            refresh_analysis(web_app)
            page_state["message"] = "Analysis updated from the database."
        except Exception:
            web_app.logger.exception("Update Analysis failed")
            page_state["message"] = "Could not update the analysis. Previous results are still shown."
            return jsonify(ok=False), 500
    return jsonify(ok=True), 200


if __name__ == "__main__":
    website = create_app()
    website.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
