"""
Export and database initialization module.
Dumps generated entities to CSV, JSON, SQLite database (kyc_lifecycle.db), and SQL seed script.
"""

import os
import csv
import json
import sqlite3
from typing import List, Dict, Any
from src.generator import KYCDataGenerator
from src.models import SQL_SCHEMA


def export_dataset_to_all_formats(generator: KYCDataGenerator, output_dir: str):
    """
    Exports all generated entities to:
    1. CSV files in output_dir
    2. JSON files in output_dir
    3. SQLite database in output_dir/kyc_lifecycle.db
    4. SQL seed script in output_dir/seed_data.sql
    """
    os.makedirs(output_dir, exist_ok=True)

    entity_tables = {
        "customer_types": [e.to_dict() for e in generator.customer_types],
        "kyc_requirements": [e.to_dict() for e in generator.kyc_requirements],
        "customers": [e.to_dict() for e in generator.customers],
        "documents": [e.to_dict() for e in generator.documents],
        "verifications": [e.to_dict() for e in generator.verifications],
        "risk_ratings": [e.to_dict() for e in generator.risk_ratings],
        "beneficial_owners": [e.to_dict() for e in generator.beneficial_owners],
        "review_cases": [e.to_dict() for e in generator.review_cases],
        "alerts": [e.to_dict() for e in generator.alerts],
        "audit_events": [e.to_dict() for e in generator.audit_events],
        "ground_truth": [e.to_dict() for e in generator.ground_truth],
    }

    # 1. Export CSVs
    for table_name, rows in entity_tables.items():
        if not rows:
            continue
        csv_path = os.path.join(output_dir, f"{table_name}.csv")
        headers = list(rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    # 2. Export JSON files
    for table_name, rows in entity_tables.items():
        json_path = os.path.join(output_dir, f"{table_name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

    # 3. SQLite Database export
    db_path = os.path.join(output_dir, "kyc_lifecycle.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Execute DDL
    cur.executescript(SQL_SCHEMA)

    for table_name, rows in entity_tables.items():
        if not rows:
            continue
        headers = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(headers))
        sql = f"INSERT INTO {table_name} ({', '.join(headers)}) VALUES ({placeholders})"
        data = [[row[h] for h in headers] for row in rows]
        cur.executemany(sql, data)

    conn.commit()
    conn.close()

    # 4. SQL Seed Script export
    sql_path = os.path.join(output_dir, "seed_data.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("-- KYC Lifecycle Seed Data Dump\n")
        f.write(SQL_SCHEMA + "\n\n")
        for table_name, rows in entity_tables.items():
            if not rows:
                continue
            headers = list(rows[0].keys())
            f.write(f"-- Inserts for {table_name}\n")
            for row in rows:
                formatted_vals = []
                for h in headers:
                    val = row[h]
                    if val is None:
                        formatted_vals.append("NULL")
                    elif isinstance(val, (int, float)):
                        formatted_vals.append(str(val))
                    else:
                        clean_str = str(val).replace("'", "''")
                        formatted_vals.append(f"'{clean_str}'")
                f.write(f"INSERT INTO {table_name} ({', '.join(headers)}) VALUES ({', '.join(formatted_vals)});\n")
            f.write("\n")
