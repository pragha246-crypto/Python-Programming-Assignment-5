import csv
import io

RAW = """station,date,pm25
Adyar,2026-10-01,48
Adyar,2026-10-02,NA
Adyar,2026-10-03,
Guindy,2026-10-01,95
Guindy,2026-10-02,-5
Guindy,2026-10-03,121
"""

def load_clean(text):
    """Return (station, date, pm25) tuples for valid, non-negative readings only."""
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        value = row["pm25"].strip()
        if value == "" or value.upper() == "NA":
            continue
        pm25 = float(value)
        if pm25 < 0:
            continue
        rows.append((row["station"], row["date"], pm25))
    return rows

def min_max(values):
    """Scale values to 0-1 using min-max scaling, rounded to 3 decimals."""
    values = list(values)
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return [0.0 for _ in values]
    return [round((value - minimum) / (maximum - minimum), 3) for value in values]

clean = load_clean(RAW)
print(clean)
print(min_max([pm for _, _, pm in clean]))
