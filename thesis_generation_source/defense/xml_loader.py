import os
import random
import xml.etree.ElementTree as ET
 
DATA_PATH = "data/skattemelding-og-mer"
 
 
def parse_xml_file(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
 
        values = []
 
        data = {
            "file": os.path.basename(file_path),
            "orgnr": None,
            "income": None,
            "wealth": None,
            "dividend": None,
            "interest": None,
            "gain": None,
            "deduction": None,
        }
 
        for elem in root.iter():
            text = elem.text
 
            if not text:
                continue
 
            text = text.strip()
 
            try:
                value = float(text)
                values.append(value)
            except:
                continue
 
            tag = elem.tag.split("}")[-1].lower()
 
            # 🔥 FIX: orgnr as string
            if "organisasjonsnummer" in tag:
                data["orgnr"] = text
            elif "formuesverdi" in tag:
                data["wealth"] = value
            elif "utbytte" in tag:
                data["dividend"] = value
            elif "rente" in tag:
                data["interest"] = value
            elif "gevinst" in tag:
                data["gain"] = value
            elif "inntekt" in tag:
                data["income"] = value
            elif "fradrag" in tag:
                data["deduction"] = value
 
        # safer fallback
        if all(data[k] is None for k in ["income", "wealth", "dividend", "interest", "gain", "deduction"]):
            data["income"] = values[0] if len(values) > 0 else None
            data["wealth"] = values[1] if len(values) > 1 else None
            data["dividend"] = values[2] if len(values) > 2 else None
            data["interest"] = values[3] if len(values) > 3 else None
            data["gain"] = values[4] if len(values) > 4 else None
            data["deduction"] = values[5] if len(values) > 5 else None
 
        return data
 
    except Exception:
        return None
 
 
def load_documents():
    documents = []
    all_files = []
 
    # 🔥 collect ALL XML files first
    for root, _, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith(".xml") and not file.startswith("SKE_A-ORDNING"):
                full_path = os.path.join(root, file)
                all_files.append(full_path)
 
    # 🔥 shuffle to avoid bias
    random.shuffle(all_files)
 
    MAX_DOCS = 100  # 🔥 increase diversity
 
    for full_path in all_files:
        parsed = parse_xml_file(full_path)
 
        if parsed and any(
            parsed[key] is not None
            for key in ["income", "wealth", "dividend", "interest", "gain"]
        ):
            documents.append(parsed)
 
        if len(documents) >= MAX_DOCS:
            print(f"Loaded {MAX_DOCS} DIVERSE documents")
            return documents
 
    print(f"Loaded {len(documents)} XML documents")
    return documents