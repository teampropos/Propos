"""Merge emails from terminal_log.txt into leads.csv."""
import csv
import re

LOG_FILE = "/Users/benmcgahan/Desktop/propos/terminal_log.txt"
CSV_FILE = "/Users/benmcgahan/Desktop/propos/leads.csv"

# Parse emails from log — format: "EMAIL: business_name → email@domain.com"
email_map = {}
pattern = re.compile(r"EMAIL:\s+(.+?)\s+→\s+(\S+)")

with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = pattern.search(line)
        if m:
            name = m.group(1).strip().lower()
            email = m.group(2).strip()
            email_map[name] = email

print(f"Parsed {len(email_map)} emails from log")

# Load CSV
with open(CSV_FILE, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames

# Merge emails
updated = 0
already_had = 0
for row in rows:
    name = row.get("business_name", "").strip().lower()
    if name in email_map:
        if row.get("email"):
            already_had += 1
        else:
            row["email"] = email_map[name]
            updated += 1

print(f"Updated {updated} rows with new emails")
print(f"{already_had} rows already had emails (skipped)")
print(f"{len(email_map) - updated - already_had} log emails didn't match any CSV row")

# Write back
with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("Done. leads.csv updated.")
