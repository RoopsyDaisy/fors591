import sqlite3
import sys
import os

db_path = "/workspaces/fors591/outputs/assignment5_part1_base/CARB_99/FVSOut.db"

if not os.path.exists(db_path):
    print(f"DB not found: {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables found:", [t[0] for t in tables])

for t in tables:
    name = t[0]
    if "Calib" in name or "CALIB" in name:
        print(f"Found calibration table: {name}")
        cursor.execute(f"SELECT * FROM {name} LIMIT 5")
        rows = cursor.fetchall()
        names = [description[0] for description in cursor.description]
        print(f"Columns: {names}")
        print("Rows:")
        for row in rows:
            print(row)

conn.close()
