import random
from defense.xml_loader import load_documents
 
BASE_DATA = load_documents()
 
 
def vary(value):
    if value is None:
        return None
 
    factor = random.uniform(0.8, 1.3)
    return round(value * factor, 2)
 
 
def maybe_add_noise(value):
    if value is None:
        return None
 
    if random.random() < 0.15:
        return round(value + random.uniform(50, 1500), 2)
 
    return value
 
 
def maybe_make_null(value):
    if value is None:
        return None
 
    if random.random() < 0.15:  # slightly less nulls for realism
        return None
 
    return value
 
 
def generate_green_sample():
    base = random.choice(BASE_DATA)
 
    sample = {
        "file": base["file"],
        "orgnr": base["orgnr"],
 
        "income": maybe_add_noise(vary(base["income"])),
        "wealth": maybe_add_noise(vary(base["wealth"])),
 
        "dividend": maybe_make_null(maybe_add_noise(vary(base["dividend"]))),
        "interest": maybe_make_null(maybe_add_noise(vary(base["interest"]))),
 
        "gain": maybe_add_noise(vary(base["gain"])),
        "deduction": maybe_add_noise(vary(base["deduction"])),
    }
 
    # --- Cross-field realism (stronger but still "normal") ---
 
    # deduction should not exceed income too much
    if sample["income"] and sample["deduction"]:
        if sample["deduction"] > sample["income"] * 1.2:
            sample["deduction"] = round(sample["income"] * random.uniform(0.2, 0.7), 2)
 
    # wealth usually higher than income
    if sample["wealth"] and sample["income"]:
        if sample["wealth"] < sample["income"]:
            sample["wealth"] = round(sample["income"] * random.uniform(1.5, 4), 2)
 
    # gain typically proportional to income
    if sample["gain"] and sample["income"]:
        if sample["gain"] > sample["income"]:
            sample["gain"] = round(sample["income"] * random.uniform(0.1, 0.5), 2)
 
    # interest and dividend should not exceed income in normal cases
    if sample["interest"] and sample["income"]:
        if sample["interest"] > sample["income"]:
            sample["interest"] = round(sample["income"] * random.uniform(0.01, 0.2), 2)
 
    if sample["dividend"] and sample["income"]:
        if sample["dividend"] > sample["income"]:
            sample["dividend"] = round(sample["income"] * random.uniform(0.01, 0.3), 2)
 
    return sample