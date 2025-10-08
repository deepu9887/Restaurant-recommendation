import json
import os

# Path to your dataset
file_path = os.path.join("data", "restaurants.json")

# Load existing data
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Ensure it's a list
if not isinstance(data, list):
    raise ValueError("restaurants.json is not a list of objects")

# Add new fields with defaults if missing
for r in data:
    if "Mood" not in r: 
        r["Mood"] = "Casual"
    if "Time" not in r: 
        r["Time"] = "Dinner"
    if "Budget" not in r: 
        r["Budget"] = "Medium"
    if "Group" not in r: 
        r["Group"] = "2–4"

# Save back to file
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✅ restaurants.json updated with multi-factor fields (Mood, Time, Budget, Group)")
