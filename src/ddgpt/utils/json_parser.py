import json
import re

def extract_json_block(text: str) -> str:
    """
    Extract the largest JSON object from text.
    Handles markdown, extra text, etc.
    """
    # remove markdown fences
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # find first {...} block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return match.group(0)

    raise ValueError("No JSON object found")


def fix_common_json_issues(raw: str) -> str:
    """
    Fix common JSON formatting issues from LLMs.
    """
    # single → double quotes
    raw = raw.replace("'", '"')

    # remove trailing commas
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    return raw


def try_parse_json(raw: str):
    """
    Attempt multiple parsing strategies.
    """
    try:
        return json.loads(raw)
    except Exception:
        pass

    # try fixing common issues
    try:
        fixed = fix_common_json_issues(raw)
        return json.loads(fixed)
    except Exception:
        pass

    raise ValueError("Failed to parse JSON")


def safe_parse_json(text: str) -> dict:
    """
    Full robust pipeline:
    1. extract JSON
    2. clean it
    3. parse it
    """
    raw = extract_json_block(text)
    return try_parse_json(raw)