import re

def normalize_outward(postcode: str) -> str:
    s = postcode.strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    m = re.match(r"^([A-Z]{1,2}\d[A-Z0-9]?)", s)
    if m:
        return m.group(1)
    m2 = re.match(r"^([A-Z]{1,2})", s)
    return m2.group(1) if m2 else s[:2]
