"""Quick test for _extract_dialog_activity."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "planner"))

from windowmon_summary import _extract_dialog_activity, classify_entry

test_titles = [
    "Aufgabe erledigt \u2014 WC LEMTWC",
    "Eintrag bearbeiten \u2014 Bearb. Essensplan LEEPEP",
    "Vorgezogene Aktivit\u00e4t erfassen \u2014 Z\u00e4hne putzen GEMTZP",
    "Aufgabe unterbrechen \u2014 Jause fassen LEMTJF",
    "Ungeplante Aktivit\u00e4t erfassen \u2014 Neukauf Mikrowelle WFLEKA",
    "Aufgabe erledigt \u2014 WC LEMTWC (Fs.)",
    "Aufgabe erledigt \u2014 Etwas ohne Code",
    "Aufgabe erledigt",  # old format, no em-dash
]

print("Dialog title parsing test:")
print("=" * 70)
for title in test_titles:
    account, activity = _extract_dialog_activity(title)
    print(f"  Title: {title}")
    print(f"  Result: [{account}] {activity}")
    print()

# Also test full classify_entry with these as windowmon entries
print("Full classify_entry test:")
print("=" * 70)
for title in test_titles:
    entry = {"title": title, "process": "python.exe", "browser": "", "_ts": None}
    account, activity = classify_entry(entry)
    print(f"  Title: {title}")
    print(f"  Result: [{account}] {activity}")
    print()
