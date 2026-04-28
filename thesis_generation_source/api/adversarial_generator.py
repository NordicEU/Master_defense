import json
import os
import random
import re

from ollama import Client

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3")
 
 
def clean_json_string(s):
    """
    Fix common LLM JSON issues
    """
    s = s.replace("None", "null")
    s = re.sub(r"(\d),(?=\d{3}\b)", r"\1", s)
    return s
 
 
def clamp(value, original):
    """
    Ensures values stay within realistic bounds (±50%)
    """
    if not isinstance(value, (int, float)):
        return original
 
    if original is None:
        return value if value < 5000 else 1000
 
    if original == 0:
        return round(max(100, min(3000, value)), 2)
 
    lower = original * 0.5
    upper = original * 1.5
 
    return round(max(lower, min(upper, value)), 2)
 
 
def simple_fallback_mutation(submission):
    """
    Fallback if LLM fails
    """
    mutated = submission.copy()
 
    for key, value in mutated.items():
        if key in ["file", "orgnr"]:
            continue
 
        if isinstance(value, (int, float)) or value is None:
            if value is None or value == 0:
                mutated[key] = round(random.uniform(100, 3000), 2)
            else:
                mutated[key] = round(value * random.uniform(1.1, 1.3), 2)
 
    return mutated
 
 
def generate_adversarial(submission, max_retries=3):
    prompt = f"""
Return ONLY valid JSON.

GOAL:
- Create a fraudulent but plausible financial submission
- Introduce subtle inconsistencies between fields
- Try to bypass simple rule-based detection

STRICT RULES:
- Keep ALL keys exactly as in input
- DO NOT change 'file' or 'orgnr'
- Only modify financial values
- Change at least one field

VALUE RULES:
- All values MUST be plain numbers
- Changes must be based on original values (±10–50%)
- Some inconsistencies are allowed if they appear realistic

- If value is 0 or null:
  → replace with small realistic number (100–3000)

FORMAT RULES:
- Output ONLY JSON
- No explanations, no text

INPUT:
{submission}
"""
    client = Client(host=OLLAMA_HOST)
 
    for _ in range(max_retries):
        try:
            response = client.generate(
                model=MODEL,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.3},
            )
 
            result = response.get("response", "").strip()
 
            if not result:
                continue
 
            print("LLM RAW:", result)
 
            start = result.find("{")
            end = result.rfind("}") + 1
 
            if start == -1 or end == -1:
                continue
 
            json_str = result[start:end]
            json_str = clean_json_string(json_str)
 
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                print("⚠️ Invalid JSON, retrying...")
                continue
 
            if not isinstance(parsed, dict):
                continue
 
            fixed = submission.copy()
 
            for key in fixed:
                if key in parsed:
                    fixed[key] = clamp(parsed[key], submission[key])
 
            # protect critical fields
            fixed["file"] = submission["file"]
            fixed["orgnr"] = submission["orgnr"]
 
            # ensure no None values
            for key, value in fixed.items():
                if key not in ["file", "orgnr"] and value is None:
                    fixed[key] = submission[key]
 
            return fixed
 
        except Exception as e:
            print("Error:", e)
            continue
 
    print("⚠️ Using fallback mutation")
    return simple_fallback_mutation(submission)
