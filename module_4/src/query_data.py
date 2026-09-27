"""The 9 required SQL questions and 2 extra questions.

Run from module_4 with: python -m src.query_data
Read QUERIES first. Each dictionary contains one ordinary SQL query.
"""

from .database import connect


QUERIES = [
    {
        "number": 1,
        "question": "How many entries are for Fall 2026?",
        "sql": """
SELECT COUNT(*) FROM applicants
WHERE term ILIKE 'Fall 2026';
""",
        "columns": ["Entries"], "formats": ["count"],
        "explanation": "Count entries whose term is Fall 2026, ignoring letter case.",
    },
    {
        "number": 2,
        "question": "What percentage of classified entries are international?",
        "sql": """
SELECT 100.0 * COUNT(*) FILTER (
    WHERE us_or_international ILIKE 'International'
) / NULLIF(COUNT(*), 0)
FROM applicants
WHERE LOWER(us_or_international) IN ('american', 'international', 'other');
""",
        "columns": ["International"], "formats": ["percent"],
        "explanation": "The denominator includes American, International, and Other. Missing or unrecognized classifications are excluded. Other is not counted as International.",
    },
    {
        "number": 3,
        "question": "What are the average GPA, GRE Quantitative, GRE Verbal, and GRE AW?",
        "sql": """
SELECT AVG(gpa), AVG(gre), AVG(gre_v), AVG(gre_aw)
FROM applicants;
""",
        "columns": ["GPA", "GRE Q", "GRE V", "GRE AW"],
        "formats": ["decimal", "decimal", "decimal", "decimal"],
        "explanation": "Each AVG ignores only its own missing values. An applicant with a GPA but no GRE still contributes to the GPA average. The collected GRE field is used as GRE Quantitative, as requested by the assignment.",
    },
    {
        "number": 4,
        "question": "What is the average GPA of American Fall 2026 applicants?",
        "sql": """
SELECT AVG(gpa) FROM applicants
WHERE term ILIKE 'Fall 2026'
  AND us_or_international ILIKE 'American';
""",
        "columns": ["GPA"], "formats": ["decimal"],
        "explanation": "Filter to American Fall 2026 entries, then average their available GPAs.",
    },
    {
        "number": 5,
        "question": "What percentage of Fall 2025 entries are acceptances?",
        "sql": """
SELECT 100.0 * COUNT(*) FILTER (
    WHERE status ILIKE 'Accepted%'
) / NULLIF(COUNT(*), 0)
FROM applicants
WHERE term ILIKE 'Fall 2025';
""",
        "columns": ["Accepted"], "formats": ["percent"],
        "explanation": "Divide accepted Fall 2025 entries by ALL Fall 2025 entries, including entries with other or missing decisions. NULLIF avoids division by zero.",
    },
    {
        "number": 6,
        "question": "What is the average GPA of accepted Fall 2026 applicants?",
        "sql": """
SELECT AVG(gpa) FROM applicants
WHERE term ILIKE 'Fall 2026'
  AND status ILIKE 'Accepted%';
""",
        "columns": ["GPA"], "formats": ["decimal"],
        "explanation": "Average available GPAs among entries reporting acceptance for Fall 2026.",
    },
    {
        "number": 7,
        "question": "How many Johns Hopkins master's Computer Science entries are there?",
        "sql": r"""
SELECT COUNT(*) FROM applicants
WHERE program ~* '\m(computer\s+science|cs)\M'
  AND program ~* '\m(johns?\s+hopkins|jhu)\M'
  AND LOWER(degree) IN (
      'masters', 'master', 'master''s', 'ms', 'm.s.',
      'msc', 'm.sc.', 'ma', 'm.a.', 'meng', 'm.eng.'
  );
""",
        "columns": ["Entries"], "formats": ["count"],
        "explanation": "Use the original combined program field and degree. Match Johns/John Hopkins or JHU and Computer Science or CS, with common master's degree spellings. No term or acceptance filter is requested here. PostgreSQL ~* means a case-insensitive pattern; \\m and \\M mark word boundaries.",
    },
    {
        "number": 8,
        "question": "How many Fall 2026 CS PhD acceptances are at Georgetown, MIT, Stanford, or Carnegie Mellon (original names)?",
        "sql": r"""
SELECT COUNT(*) FROM applicants
WHERE term ILIKE 'Fall 2026'
  AND status ILIKE 'Accepted%'
  AND LOWER(REPLACE(degree, '.', '')) = 'phd'
  AND program ~* '\m(computer\s+science|cs)\M'
  AND (program ~* '\m(georgetown|stanford|carnegie mellon|cmu)\M'
       OR program ~* '\m(massachusetts institute of technology|mit)\M');
""",
        "columns": ["Entries"], "formats": ["count"],
        "explanation": "Use original program names with common university aliases. Word boundaries prevent MIT from matching inside an unrelated word. Each entry is counted once.",
    },
    {
        "number": 9,
        "question": "Does the previous count change when LLM-generated names are used?",
        "sql": r"""
WITH counts AS (
    SELECT
        COUNT(*) FILTER (
            WHERE program ~* '\m(computer\s+science|cs)\M'
              AND (program ~* '\m(georgetown|stanford|carnegie mellon|cmu)\M'
                   OR program ~* '\m(massachusetts institute of technology|mit)\M')
        ) AS original_count,
        COUNT(*) FILTER (
            WHERE llm_generated_program ~* '\m(computer\s+science|cs)\M'
              AND (
                  llm_generated_university ~* '\m(georgetown|stanford|carnegie mellon|cmu)\M'
                  OR llm_generated_university ~* '\m(massachusetts institute of technology|mit)\M'
              )
        ) AS llm_count
    FROM applicants
    WHERE term ILIKE 'Fall 2026'
      AND status ILIKE 'Accepted%'
      AND LOWER(REPLACE(degree, '.', '')) = 'phd'
)
SELECT original_count, llm_count, llm_count - original_count
FROM counts;
""",
        "columns": ["Original", "LLM", "Difference"],
        "formats": ["count", "count", "count"],
        "explanation": "Keep term, status, and degree unchanged. Compare original names with the two LLM fields. Difference means LLM minus original. Standardization may recover aliases, but model mistakes or changed program labels may also remove or add matches.",
    },
    {
        "number": 10,
        "question": "Extra: How many Fall 2026 entries report each degree?",
        "sql": """
SELECT COALESCE(degree, 'Unknown') AS reported_degree,
       COUNT(*) AS entries
FROM applicants
WHERE term ILIKE 'Fall 2026'
GROUP BY COALESCE(degree, 'Unknown')
ORDER BY entries DESC, reported_degree;
""",
        "columns": ["Degree", "Entries"], "formats": ["text", "count"],
        "explanation": "Group Fall 2026 entries by reported degree. Unknown retains entries without a degree. This shows which degree levels dominate this sample.",
    },
    {
        "number": 11,
        "question": "Extra: How does reported GPA compare between Fall 2026 acceptances and rejections?",
        "sql": """
SELECT LOWER(status) AS decision, COUNT(*) AS entries,
       COUNT(gpa) AS with_gpa, AVG(gpa) AS average_gpa
FROM applicants
WHERE term ILIKE 'Fall 2026'
  AND LOWER(status) IN ('accepted', 'rejected')
GROUP BY LOWER(status)
ORDER BY decision;
""",
        "columns": ["Decision", "Entries", "With GPA", "GPA"],
        "formats": ["text", "count", "count", "decimal"],
        "explanation": "Compare accepted and rejected entries after the loader extracts the decision from the status text. Show GPA coverage alongside averages. These groups are self-selected reports, so a GPA difference does not establish a cause of admission.",
    },
]


def run_queries(database_url=None):
    """Run each handwritten SQL query and return its rows."""
    results = {}
    with connect(database_url) as connection:
        with connection.cursor() as cursor:
            for query in QUERIES:
                cursor.execute(query["sql"])
                results[query["number"]] = cursor.fetchall()
    return results


def format_value(value, kind):
    """Use the same display rules in SQL output, ORM output, and the webpage."""
    if value is None:
        return "N/A"
    if kind == "percent":
        return f"{value:.2f}%"
    if kind == "decimal":
        return f"{value:.2f}"
    if kind == "count":
        return str(int(value))
    return str(value)


def formatted_rows(query, rows):
    """Convert every answer value to readable text, one row at a time."""
    display_rows = []
    for row in rows:
        display_values = []
        # zip pairs each value with its matching display rule.
        for value, kind in zip(row, query["formats"]):
            display_values.append(format_value(value, kind))
        display_rows.append(display_values)
    return display_rows


def print_results(results, title, numbers=None):
    """Print each selected question followed by its labeled answers."""
    print(title)
    for query in QUERIES:
        number = query["number"]
        if numbers is not None and number not in numbers:
            continue
        print(f"\nQ{number}. {query['question']}")
        for row in formatted_rows(query, results[number]):
            labeled_values = []
            for label, value in zip(query["columns"], row):
                labeled_values.append(f"{label}: {value}")
            print(" | ".join(labeled_values))


if __name__ == "__main__":
    print_results(run_queries(), "MODULE 4 - RAW SQL RESULTS")
