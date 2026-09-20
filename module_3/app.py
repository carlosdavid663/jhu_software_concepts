from datetime import datetime
from threading import Lock, Thread

from flask import Flask, redirect, render_template, url_for

from orm_queries import run_orm_queries
from pull_data import pull_new_data
from query_data import QUERIES, formatted_rows

app = Flask(__name__)

# The background worker and webpage share this small set of values.
# The lock lets only one thread change them at a time.
job_lock = Lock()
state = {"busy": False, "message": "Ready.", "results": {}, "updated": None}


def update_message(message):
    with job_lock:
        state["message"] = message


def refresh_analysis():
    """Called while holding job_lock, so a pull cannot start during refresh."""
    state["results"] = run_orm_queries()
    state["updated"] = datetime.now().strftime("%d %b %Y, %H:%M:%S")


def pull_in_background():
    """Keep the page responsive while the scraper and cleaner run."""
    try:
        inserted, warning = pull_new_data(report=update_message)
        message = f"Pull finished: added {inserted} new entries. Click Update Analysis to refresh the results."
        if warning:
            message += " " + warning
        update_message(message)
    except Exception:
        # Background errors must release the busy flag so the user can try again.
        app.logger.exception("Pull Data failed")
        update_message("Could not finish the pull. See the terminal for details, then try again.")
    finally:
        with job_lock:
            state["busy"] = False


@app.get("/")
def index():
    with job_lock:
        if not state["results"] and not state["busy"]:
            try:
                refresh_analysis()
            except Exception:
                app.logger.exception("Could not read the database")
                state["message"] = "Database unavailable. Check the README setup steps and run load_data.py first."
        current = state.copy()

    cards = []
    for query in QUERIES:
        card = query.copy()
        card["rows"] = formatted_rows(query, current["results"].get(query["number"], []))
        cards.append(card)
    return render_template("index.html", cards=cards, state=current)


@app.post("/pull")
def pull():
    with job_lock:
        if state["busy"]:
            return redirect(url_for("index"))
        state["busy"] = True
        state["message"] = "Pulling new entries. Please wait; this page checks progress every five seconds."
        try:
            Thread(target=pull_in_background, daemon=True).start()
        except Exception:
            state["busy"] = False
            state["message"] = "The background worker could not start. Please try again."
            app.logger.exception("Could not start worker")
    return redirect(url_for("index"))


@app.post("/update")
def update():
    with job_lock:
        if state["busy"]:
            return redirect(url_for("index"))
        try:
            refresh_analysis()
            state["message"] = "Analysis updated from the database."
        except Exception:
            app.logger.exception("Update Analysis failed")
            state["message"] = "Could not update the analysis. Previous results are still shown; check the terminal."
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Use one app process: its lock prevents overlapping pulls. No auto-reloader.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
