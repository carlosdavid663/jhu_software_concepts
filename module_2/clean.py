import argparse
import hashlib
import html
import json
import re
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

FOLDER = Path(__file__).resolve().parent


def load_data(filename):
    """Read one JSON file. Missing files are reported instead of hidden."""
    with open(filename, encoding="utf-8-sig") as file:
        return json.load(file)


def save_data(data, filename):
    """Write valid JSON, replacing the old file only after writing succeeds."""
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = filename.with_suffix(filename.suffix + ".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write("\n")

    # A reader or sync client can briefly lock the destination on Windows.
    # Retry only this local atomic replacement, never a website request.

    for attempt in range(10):
        try:
            temporary_file.replace(filename)
            break

        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2 * (attempt + 1))


def _clean_text(value):
    """Remove HTML and extra spaces. Use None for an empty value."""

    if value is None:
        return None
    value = html.unescape(str(value))

    if re.search(r"</?[a-zA-Z][^>]*>", value):
        value = BeautifulSoup(value, "html.parser").get_text(" ")
    return " ".join(value.split()) or None


def _number(value):

    """Turn a label such as 'GPA 3.88' into a number."""
    text = _clean_text(value)

    if text is None:
        return None
    match = re.search(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", text)

    return float(match.group()) if match else None


def _date(value):
    """Convert a complete date. Do not guess a year for a partial date."""

    if not value:
        return None

    value = re.sub(r"^Added on\s+", "", value, flags=re.I)

    for date_format in ("%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def clean_data(rows):
    """Return new dictionaries; do not change the original input rows."""
    if not isinstance(rows, list):
        raise ValueError("Input must be a JSON array of applicant objects.")

    cleaned_rows = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each applicant must be a dictionary.")
        cleaned = row.copy()  # Keep the original input unchanged.

        # Preserve the original combined label, including its original spelling.
        original_program = row.get("program")
        if original_program is not None and not isinstance(original_program, str):
            raise ValueError("Each program value must be text or null.")
        cleaned["program"] = original_program
        cleaned["raw_program"] = row.get("raw_program", original_program)
        program, separator, university = (original_program or "").partition(",")
        cleaned["program_name"] = _clean_text(row.get("program_name") or program)
        cleaned["university"] = _clean_text(row.get("university") or university)

        for field in ("comments", "date_added", "url", "status", "term",
                      "US/International", "Degree"):
            cleaned[field] = _clean_text(row.get(field))
        if (cleaned["Degree"] or "").lower() in ("master", "masters", "master's"):
            cleaned["Degree"] = "Masters"
        if (cleaned["Degree"] or "").lower().replace(".", "") == "phd":
            cleaned["Degree"] = "PhD"

        # Keep the original metric too, so the conversion can be checked later.
        for field in ("GPA", "GRE", "GRE V", "GRE AW"):
            cleaned["raw_" + field] = row.get("raw_" + field, row.get(field))
            cleaned[field] = _number(row.get(field))

        status = cleaned["status"] or ""
        decision = re.match(r"(Accepted|Rejected|Wait\s*listed|Interview)", status, re.I)
        cleaned["decision"] = decision.group(1).title() if decision else None
        if cleaned["decision"] in ("Waitlisted", "Wait Listed"):
            cleaned["decision"] = "Wait listed"
        date_match = re.search(r"\bon\s+(.+)$", status, re.I)
        decision_date = date_match.group(1).strip() if date_match else None
        cleaned["decision_date"] = decision_date
        cleaned["acceptance_date"] = decision_date if cleaned["decision"] == "Accepted" else None
        cleaned["rejection_date"] = decision_date if cleaned["decision"] == "Rejected" else None
        cleaned["date_added_iso"] = _date(cleaned["date_added"])
        cleaned["decision_date_iso"] = _date(decision_date)

        term_match = re.fullmatch(r"(Fall|Spring|Summer|Winter)\s+(\d{4})",
                                 cleaned["term"] or "", re.I)
        cleaned["start_semester"] = term_match.group(1).title() if term_match else None
        cleaned["start_year"] = int(term_match.group(2)) if term_match else None
        cleaned_rows.append(cleaned)

    return cleaned_rows


def _cache_fingerprint():
    """Do not reuse old answers after changing the model, prompt, or lists."""
    from llm_hosting.app import MODEL_FILE, MODEL_REPO, MODEL_REVISION
    digest = hashlib.sha256()
    for name in ("app.py", "canon_programs.txt", "canon_universities.txt"):
        digest.update((FOLDER / "llm_hosting" / name).read_bytes())
    digest.update(json.dumps([MODEL_REPO, MODEL_FILE, MODEL_REVISION]).encode())
    return digest.hexdigest()


def add_llm_fields(rows, cache_file):
    """Use the supplied model helper once per distinct input, one at a time."""
    from llm_hosting.app import standardize_program
    cache_file = Path(cache_file)
    saved = load_data(cache_file) if cache_file.exists() else {}
    fingerprint = _cache_fingerprint()
    if not isinstance(saved, dict):
        raise ValueError("The model cache must be a dictionary.")
    cache = saved.get("results", {}) if saved.get("fingerprint") == fingerprint else {}
    if not isinstance(cache, dict):
        raise ValueError("The model cache results must be a dictionary.")

    extended_rows = []
    new_names = 0
    try:
        for row in rows:
            program = row.get("program") or ""
            program_name = row.get("program_name")
            university = row.get("university")
            key = json.dumps((program, program_name, university), ensure_ascii=False)
            if key not in cache:
                result = standardize_program(program, source_program=program_name,
                                             source_university=university)
            else:
                result = cache[key]
            if not isinstance(result, dict):
                raise ValueError("The model result must be a dictionary.")
            for field in ("standardized_program", "standardized_university"):
                if not isinstance(result.get(field), str) or not result[field].strip():
                    raise ValueError("The model returned an empty or invalid name.")
            if key not in cache:
                result["method"] = "local_tinyllama"
                cache[key] = result
                new_names += 1
                if new_names % 10 == 0:
                    save_data({"fingerprint": fingerprint, "results": cache}, cache_file)
            # Add the two names to a copy; leave every original field in place.
            extended = row.copy()
            extended["llm-generated-program"] = result["standardized_program"]
            extended["llm-generated-university"] = result["standardized_university"]
            extended_rows.append(extended)
            if len(extended_rows) % 100 == 0:
                print(f"Processed {len(extended_rows)} of {len(rows)} applicants.", flush=True)
    finally:
        # Keep completed answers even if the model or user stops the run.
        save_data({"fingerprint": fingerprint, "results": cache}, cache_file)
    print(f"Used the model for {new_names} new program/university pairs.")
    return extended_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON file to read")
    parser.add_argument("--output", type=Path, help="JSON file to write")
    parser.add_argument("--llm", action="store_true", help="Add the two model-generated names")
    args = parser.parse_args()
    input_name = "applicant_data.json" if args.llm else "raw_applicant_data.json"
    output_name = "llm_extend_applicant_data.json" if args.llm else "applicant_data.json"
    input_file = args.input or FOLDER / input_name
    output_file = args.output or FOLDER / output_name
    if input_file.resolve() == output_file.resolve():
        parser.error("Use different input and output files to preserve the source.")
    try:
        rows = clean_data(load_data(input_file))
        if not rows:
            raise ValueError("The input has no applicant rows.")
        if args.llm:
            rows = add_llm_fields(rows, FOLDER / "llm_cache.json")
        save_data(rows, output_file)
        print(f"Saved {len(rows)} applicants to {output_file}")
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(1, f"Could not finish: {error}\n")
    except KeyboardInterrupt:
        parser.exit(1, "Stopped. Completed model answers are saved; rerun to continue.\n")


if __name__ == "__main__":
    main()
