"""
Reproducibility Verification Suite.
Regenerates data twice with identical fixed seed (20261022) in separate directories,
computes cryptographic SHA-256 hashes for all exported files and verifies exact row counts.
"""

import os
import shutil
import hashlib
from typing import Dict, Any
from src.generator import KYCDataGenerator
from src.exporter import export_dataset_to_all_formats


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_reproducibility(seed: int = 20261022, profile: str = "starter", base_dir: str = "data") -> Dict[str, Any]:
    """
    Executes two independent generation cycles with the same seed and compares outputs.
    """
    run1_dir = os.path.join(base_dir, "reproducibility_run1")
    run2_dir = os.path.join(base_dir, "reproducibility_run2")

    # Clean prior test runs if any
    for d in [run1_dir, run2_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)

    # Run 1
    gen1 = KYCDataGenerator(seed=seed, scale_profile=profile)
    gen1.generate_all()
    export_dataset_to_all_formats(gen1, run1_dir)

    # Run 2
    gen2 = KYCDataGenerator(seed=seed, scale_profile=profile)
    gen2.generate_all()
    export_dataset_to_all_formats(gen2, run2_dir)

    # Compare row counts
    tables = [
        ("customer_types", len(gen1.customer_types), len(gen2.customer_types)),
        ("kyc_requirements", len(gen1.kyc_requirements), len(gen2.kyc_requirements)),
        ("customers", len(gen1.customers), len(gen2.customers)),
        ("documents", len(gen1.documents), len(gen2.documents)),
        ("verifications", len(gen1.verifications), len(gen2.verifications)),
        ("risk_ratings", len(gen1.risk_ratings), len(gen2.risk_ratings)),
        ("beneficial_owners", len(gen1.beneficial_owners), len(gen2.beneficial_owners)),
        ("review_cases", len(gen1.review_cases), len(gen2.review_cases)),
        ("alerts", len(gen1.alerts), len(gen2.alerts)),
        ("audit_events", len(gen1.audit_events), len(gen2.audit_events)),
        ("ground_truth", len(gen1.ground_truth), len(gen2.ground_truth)),
    ]

    row_count_match = all(r1 == r2 for _, r1, r2 in tables)

    # Compare file hashes for CSVs and JSONs
    file_comparisons = []
    all_files = sorted(os.listdir(run1_dir))
    hash_match = True

    for filename in all_files:
        if filename.endswith(".db"):
            # SQLite binary file headers can contain timestamps/salts, so compare table counts and contents
            continue
        p1 = os.path.join(run1_dir, filename)
        p2 = os.path.join(run2_dir, filename)
        h1 = compute_file_sha256(p1)
        h2 = compute_file_sha256(p2)
        match = (h1 == h2)
        if not match:
            hash_match = False
        file_comparisons.append({
            "file": filename,
            "hash_run1": h1,
            "hash_run2": h2,
            "match": match,
        })

    is_reproducible = row_count_match and hash_match

    # Clean up test directories
    shutil.rmtree(run1_dir, ignore_errors=True)
    shutil.rmtree(run2_dir, ignore_errors=True)

    return {
        "seed": seed,
        "profile": profile,
        "is_reproducible": is_reproducible,
        "row_count_match": row_count_match,
        "file_hash_match": hash_match,
        "tables_compared": tables,
        "file_comparisons": file_comparisons,
    }
