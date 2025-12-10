import sqlite3
import pandas as pd
import sys

db_path = "/workspaces/fors591/outputs/assignment5_part1_base/CARB_99/FVSOut.db"
print(f"Inspecting {db_path}")

try:
    conn = sqlite3.connect(db_path)

    # List all tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    table_names = [t[0] for t in tables]
    print("Tables in DB:", table_names)

    # Check for calibration table and print columns/sample
    found_calib = False
    for table_name in table_names:
        if "Calib" in table_name or "CALIB" in table_name:
            found_calib = True
            print(f"\n--- Table: {table_name} ---")
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            print(df.head())
            print("Columns:", df.columns.tolist())
    
    if not found_calib:
        print("\nNo table with 'Calib' in name found.")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
