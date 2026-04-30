from __future__ import annotations

import os
import random
import sys
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Tuple
from uuid import uuid4


MASTER_ROOT = Path(__file__).resolve().parents[2]
THESIS_ROOT = MASTER_ROOT / "thesis_generation_source"

KNOWN_RELATIONSHIPS = [
    ("11111111111", "999888777"),
    ("22222222222", "555444333"),
    ("33333333333", "123123123"),
    ("12345678901", "999888777"),
]

_THESIS_FUNCTIONS: Tuple[Callable[[], Dict[str, Any]], Callable[..., Dict[str, Any]], Callable[[Dict[str, Any]], Dict[str, Any]]] | None = None


@contextmanager
def _temporary_thesis_import_context():
    original_cwd = Path.cwd()
    added_path = False

    if not THESIS_ROOT.exists():
        raise RuntimeError(f"Could not find local thesis generation source at {THESIS_ROOT}")

    thesis_path = str(THESIS_ROOT)
    if thesis_path not in sys.path:
        sys.path.insert(0, thesis_path)
        added_path = True

    os.chdir(THESIS_ROOT)
    try:
        yield
    finally:
        os.chdir(original_cwd)
        if added_path:
            try:
                sys.path.remove(thesis_path)
            except ValueError:
                pass


def _load_thesis_functions() -> Tuple[Callable[[], Dict[str, Any]], Callable[..., Dict[str, Any]], Callable[[Dict[str, Any]], Dict[str, Any]]]:
    global _THESIS_FUNCTIONS

    if _THESIS_FUNCTIONS is not None:
        return _THESIS_FUNCTIONS

    with _temporary_thesis_import_context():
        green_module = import_module("api.green_generator")
        try:
            adversarial_module = import_module("api.adversarial_generator")
            generate_adversarial = adversarial_module.generate_adversarial
            fallback_mutation = adversarial_module.simple_fallback_mutation
        except ModuleNotFoundError as exc:
            if exc.name != "requests":
                raise
            generate_adversarial = _missing_llm_adversary
            fallback_mutation = _local_fallback_mutation

    _THESIS_FUNCTIONS = (
        green_module.generate_green_sample,
        generate_adversarial,
        fallback_mutation,
    )
    return _THESIS_FUNCTIONS


def _missing_llm_adversary(*_: Any, **__: Any) -> Dict[str, Any]:
    raise RuntimeError(
        "The thesis LLM adversarial generator requires the 'requests' package. "
        "Use the fallback generator or install requests in this environment."
    )


def _local_fallback_mutation(submission: Dict[str, Any]) -> Dict[str, Any]:
    mutated = submission.copy()

    for key, value in mutated.items():
        if key in {"file", "orgnr"}:
            continue

        if isinstance(value, (int, float)) or value is None:
            if value is None or value == 0:
                mutated[key] = round(random.uniform(100, 3000), 2)
            else:
                mutated[key] = round(value * random.uniform(1.1, 1.3), 2)

    return mutated


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _scale_tax_value(value: Any, fallback: float) -> float:
    number = _safe_float(value)
    if number is None:
        return fallback

    number = abs(number)
    if number < 10_000:
        number *= 100
    elif number < 100_000:
        number *= 10

    return round(max(number, 1_000), 2)


def _derive_declared_income(sample: Dict[str, Any]) -> float:
    fallback = random.uniform(320_000, 780_000)
    income = sample.get("income")

    if income is None:
        wealth = _safe_float(sample.get("wealth"))
        if wealth:
            income = wealth * random.uniform(0.12, 0.32)

    return _scale_tax_value(income, fallback)


def _derive_declared_expenses(sample: Dict[str, Any], declared_income: float, sample_kind: str) -> float:
    deduction = _safe_float(sample.get("deduction"))
    interest = _safe_float(sample.get("interest")) or 0.0
    gain = _safe_float(sample.get("gain")) or 0.0

    raw_expenses = deduction if deduction is not None else abs(interest) + max(0.0, -gain)
    expenses = _scale_tax_value(raw_expenses, declared_income * random.uniform(0.08, 0.35))

    if sample_kind == "green":
        return round(min(expenses, declared_income * random.uniform(0.08, 0.55)), 2)

    attack_pattern = random.choice(["high_ratio", "extreme_ratio", "subtle_ratio"])
    if attack_pattern == "high_ratio":
        return round(max(expenses, declared_income * random.uniform(1.05, 1.45)), 2)
    if attack_pattern == "extreme_ratio":
        return round(max(expenses, declared_income * random.uniform(2.05, 3.25)), 2)
    return round(max(expenses, declared_income * random.uniform(0.78, 1.08)), 2)


def _identity_for_sample(sample: Dict[str, Any], sample_kind: str) -> Tuple[str, str]:
    if sample_kind == "green":
        return random.choice(KNOWN_RELATIONSHIPS)

    # Keep most adversarial cases contextually valid so routing diversity comes
    # from the financial/pattern signals rather than every sample degenerating
    # into the same identity-mismatch path.
    if random.random() < 0.70:
        return random.choice(KNOWN_RELATIONSHIPS)

    orgnr = str(sample.get("orgnr") or "").strip()
    person_id = f"9{random.randint(10_000_000_00, 99_999_999_99)}"[:11]

    if random.random() < 0.50:
        employer_id = random.choice([employer for _, employer in KNOWN_RELATIONSHIPS])
    else:
        employer_id = orgnr[:9] if len(orgnr) >= 9 else f"8{random.randint(10_000_000, 99_999_999)}"[:9]

    return person_id, employer_id


def _dates_for_sample(sample_kind: str) -> Tuple[str, str]:
    if sample_kind == "adversarial" and random.random() < 0.30:
        return "31.12.2026", "01.01.2026"
    return "01.01.2026", "31.12.2026"


def generate_thesis_sample(sample_kind: str, use_llm_adversary: bool = False) -> Dict[str, Any]:
    generate_green_sample, generate_adversarial, fallback_mutation = _load_thesis_functions()
    green = generate_green_sample()

    if sample_kind == "green":
        return green

    if use_llm_adversary:
        return generate_adversarial(green, max_retries=1)

    return fallback_mutation(green)


def build_generated_gateway_payload(sample_kind: str, use_llm_adversary: bool = False) -> Dict[str, Any]:
    sample_kind = sample_kind if sample_kind in {"green", "adversarial"} else "green"
    thesis_sample = generate_thesis_sample(sample_kind, use_llm_adversary=use_llm_adversary)

    declared_income = _derive_declared_income(thesis_sample)
    declared_expenses = _derive_declared_expenses(thesis_sample, declared_income, sample_kind)
    person_id, employer_id = _identity_for_sample(thesis_sample, sample_kind)
    employment_start, employment_end = _dates_for_sample(sample_kind)
    submission_id = str(uuid4())

    submission = {
        "submission_id": submission_id,
        "person_id": person_id,
        "employer_id": employer_id,
        "declared_income": declared_income,
        "declared_expenses": declared_expenses,
        "employment_start": employment_start,
        "employment_end": employment_end,
        "source": "input_app_generated",
        "generated_label": sample_kind,
        "generated_from": "thesisproject",
        "source_file": thesis_sample.get("file"),
    }

    normalized_payload = {
        "person_id": person_id,
        "employer_id": employer_id,
        "declared_income": declared_income,
        "declared_expenses": declared_expenses,
        "employment_start": employment_start,
        "employment_end": employment_end,
        "raw_payload_keys": sorted(list(submission.keys())),
    }

    return {
        "submission": submission,
        "normalized_payload": normalized_payload,
        "thesis_sample": thesis_sample,
    }
