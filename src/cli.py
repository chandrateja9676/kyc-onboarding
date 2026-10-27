"""
CLI Entrypoint for KYC Lifecycle & Onboarding Evidence Platform.
Provides commands to generate data, run validations, test reproducibility,
execute live onboarding pipelines, run batch surveillance, advance simulation time,
and start the dashboard server.
"""

import argparse
import sys
import os
import json

from src.generator import KYCDataGenerator
from src.exporter import export_dataset_to_all_formats
from src.validator import DatasetValidator
from src.reproducibility import test_reproducibility
from src.web_server import run_server
from src.pipeline import LiveOnboardingPipeline, BatchSurveillancePipeline, TimeMachineEngine


def cmd_generate(args):
    print(f"[*] Starting KYC Synthetic Generation (Profile: {args.profile}, Seed: {args.seed})...")
    gen = KYCDataGenerator(seed=args.seed, scale_profile=args.profile)
    gen.generate_all()
    print(f"    - Customers generated: {len(gen.customers):,}")
    print(f"    - Documents generated: {len(gen.documents):,}")
    print(f"    - Beneficial Owners generated: {len(gen.beneficial_owners):,}")
    print(f"    - Review Cases generated: {len(gen.review_cases):,}")
    print(f"    - Operational Alerts generated: {len(gen.alerts):,}")
    print(f"    - Injected Ground Truth Anomalies: {len(gen.ground_truth):,}")

    outdir = args.outdir
    print(f"[*] Exporting dataset to CSV, JSON, SQLite DB, and SQL script in '{outdir}'...")
    export_dataset_to_all_formats(gen, outdir)
    print("[+] Generation and export completed successfully.")


def cmd_validate(args):
    db_path = args.db
    if not os.path.exists(db_path):
        print(f"[!] Error: Database '{db_path}' not found. Run generate first.")
        sys.exit(1)

    print(f"[*] Running full validation and compliance audit on '{db_path}'...")
    validator = DatasetValidator(db_path)
    report = validator.run_all_validations()
    validator.close()

    print("\n--- VALIDATION RESULTS SUMMARY ---")
    print(f"Primary Key Uniqueness:      {'PASS' if report['primary_keys']['passed'] else 'FAIL'}")
    print(f"Foreign Key Integrity:        {'PASS' if report['foreign_keys']['passed'] else 'FAIL'}")
    print(f"Enum & Domain Constraints:    {'PASS' if report['enum_constraints']['passed'] else 'FAIL'}")
    print(f"Date Chronology Ordering:     {'PASS' if report['date_ordering']['passed'] else 'FAIL'}")
    print(f"Completeness Reconciliation:  {'PASS' if report['derived_reconciliation']['passed'] else 'FAIL'}")

    comp_eval = report["compliance_rule_evaluation"]
    print(f"\n--- COMPLIANCE RULE AUDITOR EVALUATION ---")
    print(f"Evaluated Anomalies:          {comp_eval['total_anomalies_evaluated']}")
    print(f"Auditor Precision:            {comp_eval['overall_precision'] * 100:.2f}%")
    print(f"Auditor Recall:               {comp_eval['overall_recall'] * 100:.2f}%")
    print(f"Auditor F1-Score:             {comp_eval['f1_score'] * 100:.2f}%")

    for anom_type, stats in comp_eval["breakdown"].items():
        print(f"  • {anom_type:<36} | GT: {stats['ground_truth_count']:>2} | TP: {stats['true_positives']:>2} | FP: {stats['false_positives']:>2} | F1: {stats['f1_score']*100:.1f}%")

    if report["overall_passed"]:
        print("\n[+] ALL VALIDATION SUITES PASSED WITH 100% RELIABILITY.")
    else:
        print("\n[!] SOME CHECKS FAILED.")
        sys.exit(1)


def cmd_reproduce(args):
    print(f"[*] Running Step 10: Double-generation reproducibility test (Seed: {args.seed}, Profile: {args.profile})...")
    res = test_reproducibility(seed=args.seed, profile=args.profile)
    print(f"Row Counts Identical:  {'YES' if res['row_count_match'] else 'NO'}")
    print(f"File Hashes Match:     {'YES' if res['file_hash_match'] else 'NO'}")
    print(f"Strict Reproducibility: {'PASS' if res['is_reproducible'] else 'FAIL'}")

    print("\nFile-by-file SHA-256 Digest Verification:")
    for fc in res["file_comparisons"]:
        status_str = "MATCH" if fc["match"] else "MISMATCH"
        print(f"  {fc['file']:<25} [{status_str}] {fc['hash_run1'][:16]}... == {fc['hash_run2'][:16]}...")

    if not res["is_reproducible"]:
        print("[!] Reproducibility check failed.")
        sys.exit(1)
    else:
        print("\n[+] Reproducibility verification confirmed. Exact bit-level consistency across multiple runs.")


def cmd_onboard(args):
    pipeline = LiveOnboardingPipeline(args.db)
    res = pipeline.onboard_new_customer(
        customer_type_code=args.type,
        legal_name=args.name,
        tax_id=args.tax_id,
        jurisdiction=args.jurisdiction,
        date_of_birth_or_inc=args.dob,
        trade_name=args.trade_name,
    )
    print("\n[+] Live Customer Onboarded:")
    print(json.dumps(res, indent=2))


def cmd_upload_doc(args):
    pipeline = LiveOnboardingPipeline(args.db)
    res = pipeline.upload_and_process_evidence(
        customer_id=args.customer,
        document_category=args.category,
        document_type=args.doc_type,
        document_reference_number=args.ref,
        issuing_country=args.country,
        issue_date=args.issue,
        expiry_date=args.expiry,
    )
    print("\n[+] Evidence Ingested & Evaluated:")
    print(json.dumps(res, indent=2))


def cmd_surveillance(args):
    surv = BatchSurveillancePipeline(args.db)
    print(f"[*] Running daily scheduled batch surveillance pipeline...")
    res = surv.run_daily_surveillance()
    print("\n[+] Batch Surveillance Completed:")
    print(json.dumps(res, indent=2))


def cmd_advance_time(args):
    engine = TimeMachineEngine(args.db)
    print(f"[*] Advancing simulation calendar by {args.days} days...")
    res = engine.advance_time(days=args.days)
    print("\n[+] Time Machine Advanced:")
    print(json.dumps(res, indent=2))


def cmd_serve(args):
    print(f"[*] Launching Web Dashboard on port {args.port}...")
    run_server(port=args.port)


def main():
    parser = argparse.ArgumentParser(description="KYC Onboarding & Evidence Lifecycle Platform")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Generate
    p_gen = subparsers.add_parser("generate", help="Generate synthetic KYC dataset")
    p_gen.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed")
    p_gen.add_argument("--profile", choices=["starter", "standard", "full"], default="full", help="Data volume scale profile")
    p_gen.add_argument("--outdir", default="data", help="Output directory for CSV, JSON, SQLite")

    # Validate
    p_val = subparsers.add_parser("validate", help="Validate integrity and run compliance audits")
    p_val.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    # Reproduce
    p_rep = subparsers.add_parser("reproduce", help="Verify seed reproducibility across two runs")
    p_rep.add_argument("--seed", type=int, default=20261022, help="Seed to test")
    p_rep.add_argument("--profile", choices=["starter", "standard", "full"], default="starter", help="Scale profile")

    # Onboard
    p_onb = subparsers.add_parser("onboard", help="Live onboarding of a new customer")
    p_onb.add_argument("--name", required=True, help="Customer legal name")
    p_onb.add_argument("--type", choices=["INDIVIDUAL", "CORPORATE", "TRUST", "PARTNERSHIP"], default="INDIVIDUAL", help="Customer type")
    p_onb.add_argument("--jurisdiction", default="US", help="ISO country code")
    p_onb.add_argument("--tax-id", required=True, help="Tax ID number")
    p_onb.add_argument("--dob", default="1992-05-14", help="Date of birth or incorporation (YYYY-MM-DD)")
    p_onb.add_argument("--trade-name", default=None, help="Optional trade name")
    p_onb.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    # Upload Doc
    p_doc = subparsers.add_parser("upload-doc", help="Live document evidence upload and verification")
    p_doc.add_argument("--customer", required=True, help="Customer ID (e.g., CUS-000001)")
    p_doc.add_argument("--category", choices=["IDENTITY", "ADDRESS_PROOF", "INCORPORATION", "TAX_CERTIFICATE", "UBO_DECLARATION", "FINANCIAL_STATEMENT"], required=True)
    p_doc.add_argument("--doc-type", required=True, help="Specific document type (e.g., PASSPORT, UTILITY_BILL)")
    p_doc.add_argument("--ref", required=True, help="Document reference/serial number")
    p_doc.add_argument("--country", default="US", help="Issuing country")
    p_doc.add_argument("--issue", required=True, help="Issue date (YYYY-MM-DD)")
    p_doc.add_argument("--expiry", default=None, help="Expiry date (YYYY-MM-DD) or None")
    p_doc.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    # Batch Surveillance
    p_surv = subparsers.add_parser("batch-surveillance", help="Execute daily scheduled batch surveillance job")
    p_surv.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    # Advance Time
    p_adv = subparsers.add_parser("advance-time", help="Time Machine: advance simulation clock and trigger surveillance")
    p_adv.add_argument("--days", type=int, default=30, help="Days to advance calendar")
    p_adv.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    # Serve
    p_srv = subparsers.add_parser("serve", help="Run local web dashboard")
    p_srv.add_argument("--port", type=int, default=8501, help="HTTP port (default: 8501)")

    # All
    p_all = subparsers.add_parser("all", help="Generate full dataset, validate, and test reproducibility")
    p_all.add_argument("--seed", type=int, default=20261022, help="Random seed")
    p_all.add_argument("--profile", choices=["starter", "standard", "full"], default="full", help="Data volume scale profile")
    p_all.add_argument("--outdir", default="data", help="Output directory for CSV, JSON, SQLite")
    p_all.add_argument("--db", default="data/kyc_lifecycle.db", help="Path to SQLite database")

    args = parser.parse_args()
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "reproduce":
        cmd_reproduce(args)
    elif args.command == "onboard":
        cmd_onboard(args)
    elif args.command == "upload-doc":
        cmd_upload_doc(args)
    elif args.command == "batch-surveillance":
        cmd_surveillance(args)
    elif args.command == "advance-time":
        cmd_advance_time(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "all":
        cmd_generate(args)
        cmd_validate(args)
        args.profile = "starter"
        cmd_reproduce(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
