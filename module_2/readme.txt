MODULE 2 - WEB SCRAPING
======================

Name: Carlos David Arredondo Vazquez
Email: Carredo3@jh.edu
GitHub repository SSH URL:
git@github.com:carlosdavid663/jhu_software_concepts.git
Assignment: Module 2 - Assignment: Web Scraping

HOW THIS PROJECT WORKS
----------------------
The assignment collects at least 30,000 entries BEFORE cleaning.
This project already contains 30,020 collected entries and their finished
cleaned/model outputs. You do not need to collect them again to view them.

One applicant is a Python dictionary. The dataset is a list of dictionaries.
The three data files show the three steps:

  raw_applicant_data.json         Original collected records.
  applicant_data.json             Records after ordinary cleaning.
  llm_extend_applicant_data.json  Cleaned records plus two model-generated names.

START READING THE CODE HERE
---------------------------
1. clean.py: load_data() opens a JSON file.
2. clean.py: clean_data() loops through the applicants and cleans each copy.
3. clean.py: save_data() writes the result to another JSON file.
4. scrape.py: scrape_data() visits results pages and saves the applicants.

The small functions starting with _ help with one part of those steps.
The larger llm_hosting/app.py is the supplied model code with documented
fixes. clean.py calls its standardize_program() function as a helper.
The submitted scripts use ordinary loops and process one step at a time.

SETUP
-----
Use 64-bit Python 3.12 (tested). The PDF permits Python 3.10 or newer.
Put module_2 inside your course folder. From that parent folder, run:

  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r module_2/requirements.txt
  cd module_2

Run the remaining commands from module_2. On macOS/Linux, replace
..\.venv\Scripts\python.exe with ../.venv/bin/python.

CLEAN THE INCLUDED DATA
clean.py

This reads raw_applicant_data.json and writes applicant_data.json.
The original file stays unchanged. Empty values become null, score strings
become numbers, and HTML/extra spaces are removed from cleaned text. Raw
fields are retained. Complete dates are formatted consistently; a missing
year is never guessed. Program and university fields stay separate so a
comma inside a name does not split it incorrectly.

REFERENCES
----------
Assignment: free task.pdf. Starter: llm_hosting-1-1.zip.
https://docs.python.org/3/library/urllib.request.html
https://www.crummy.com/software/BeautifulSoup/bs4/doc/
https://huggingface.co/docs/huggingface_hub/package_reference/file_download
https://llama-cpp-python.readthedocs.io/en/latest/
