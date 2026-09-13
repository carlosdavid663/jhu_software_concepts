# Mini LLM Standardizer - adapted instructor starter

For the assignment workflow, follow [`../readme.txt`](../readme.txt) and run
`clean.py --llm` from `module_2`. The beginner cleaner processes one input
at a time and saves answers for reuse. The interfaces below are optional;
they are not needed to follow the two assignment scripts.

TinyLlama 1.1B Chat Q4_K_M runs locally through llama-cpp-python and adds:

- `llm-generated-program`
- `llm-generated-university`

The original row fields remain in the output. The first inference downloads
approximately 669 MB of model weights; subsequent runs reuse the local file.
Model and canonical-list paths resolve relative to `app.py`. The tested
dependencies, pinned model revision, changes, and limitations are documented
in the parent README. Keep this folder inside `module_2`, because its
`requirements.txt` references the parent dependency file.

## Local setup and API

Create and activate the Python environment described in the parent README.
From `module_2/llm_hosting`, install dependencies and start the optional API:

```text
python -m pip install -r requirements.txt
python app.py --serve
```

The server listens on `127.0.0.1:8000`. It loads the model on the first
standardization request. In another PowerShell window in this folder:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/standardize -Method Post -ContentType 'application/json' -Body (Get-Content -LiteralPath sample_data.json -Raw)
```

The API accepts an array of applicant objects, or an object containing a
`rows` array, and returns an object with a `rows` array.
When present, separate `program_name` and `university` fields are used as
source context, so commas within a program name do not split it incorrectly.
These optional fields and `program` must be text or null.

## Command-line output

Use `--json` to produce the single JSON array required by the assignment:

```text
python app.py --file ../applicant_data.json --out ../llm_extend_applicant_data.json --json
```

The original JSON Lines mode remains available for other uses:

```text
python app.py --file sample_data.json --out sample_output.jsonl
```

JSON Lines output is not a substitute for the required JSON-array file.
Input and output must be different files. JSON-array output cannot be appended.

## Configuration

- `MODEL_REPO`: `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`
- `MODEL_FILE`: `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`
- `MODEL_REVISION`: `52e7645ba7c309695bec7ac98f4f005b139cf465`
- `N_THREADS`: the smaller of four or the available CPU count by default;
  caps both decoding and prompt-processing threads
- `N_CTX`: 2048
- `N_GPU_LAYERS`: 0 (CPU)
- `PORT`: 8000 for the optional local server

Model suggestions pass through the supplied spelling/abbreviation rules and
canonical matching, followed by source checks that protect unfamiliar names
and campus distinctions. The tiny model remains imperfect; see the observed
edge cases in the parent README. Both supplied canonical lists and
`sample_data.json` remain unchanged.
