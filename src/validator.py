"""
Comprehensive Validation and Compliance Audit Engine.
Validates:
1. Primary Key Uniqueness
2. Foreign Key Referential Integrity
3. Enum and Domain Constrains
4. Chronological Date Ordering
5. Arithmetic Reconciliation (Completeness scores, UBO percentage)
6. Ground-Truth Anomaly Detection Evaluation (Precision, Recall, F1-Score)
"""

import sqlite3
from typing import Dict, Any, List, Tuple
from datetime import datetime
from src.rules import ANCHOR_DATE, calculate_customer_completeness, get_default_kyc_requirements
from src.models import Customer, Document, SIMULATION_ANCHOR_DATE


class DatasetValidator:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def run_all_validations(self) -> Dict[str, Any]:
        """Runs the entire battery of technical integrity checks and compliance audits."""
        results = {}
        results["primary_keys"] = self.validate_primary_keys()
        results["foreign_keys"] = self.validate_foreign_keys()
        results["enum_constraints"] = self.validate_enum_constraints()
        results["date_ordering"] = self.validate_date_ordering()
        results["derived_reconciliation"] = self.validate_derived_reconciliation()
        results["compliance_rule_evaluation"] = self.evaluate_compliance_rules_against_ground_truth()
        
        # Summary pass/fail
        tech_pass = (
            results["primary_keys"]["passed"]
            and results["foreign_keys"]["passed"]
            and results["enum_constraints"]["passed"]
            and results["date_ordering"]["passed"]
            and results["derived_reconciliation"]["passed"]
        )
        audit_f1 = results["compliance_rule_evaluation"]["f1_score"]
        results["overall_passed"] = tech_pass and (audit_f1 >= 0.95)
        return results

    def validate_primary_keys(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        tables = [
            ("customer_types", "type_code"),
            ("kyc_requirements", "requirement_id"),
            ("customers", "customer_id"),
            ("documents", "document_id"),
            ("verifications", "verification_id"),
            ("risk_ratings", "risk_id"),
            ("beneficial_owners", "owner_id"),
            ("review_cases", "case_id"),
            ("alerts", "alert_id"),
            ("audit_events", "event_id"),
            ("ground_truth", "anomaly_id"),
        ]

        failures = []
        for table, pk in tables:
            query = f"SELECT {pk}, COUNT(*) FROM {table} GROUP BY {pk} HAVING COUNT(*) > 1"
            rows = cur.execute(query).fetchall()
            if rows:
                failures.append({"table": table, "pk": pk, "duplicates": len(rows)})

        return {
            "passed": len(failures) == 0,
            "checked_tables": len(tables),
            "failures": failures,
        }

    def validate_foreign_keys(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        fk_checks = [
            ("customers", "customer_type_code", "customer_types", "type_code"),
            ("kyc_requirements", "customer_type_code", "customer_types", "type_code"),
            ("documents", "customer_id", "customers", "customer_id"),
            ("verifications", "document_id", "documents", "document_id"),
            ("risk_ratings", "customer_id", "customers", "customer_id"),
            ("beneficial_owners", "business_customer_id", "customers", "customer_id"),
            ("review_cases", "customer_id", "customers", "customer_id"),
            ("alerts", "customer_id", "customers", "customer_id"),
        ]

        orphan_records = []
        for child_tbl, child_fk, parent_tbl, parent_pk in fk_checks:
            query = f"""
                SELECT c.{child_fk} FROM {child_tbl} c
                LEFT JOIN {parent_tbl} p ON c.{child_fk} = p.{parent_pk}
                WHERE p.{parent_pk} IS NULL AND c.{child_fk} IS NOT NULL
            """
            orphans = cur.execute(query).fetchall()
            if orphans:
                orphan_records.append({
                    "relationship": f"{child_tbl}.{child_fk} -> {parent_tbl}.{parent_pk}",
                    "orphan_count": len(orphans),
                })

        return {
            "passed": len(orphan_records) == 0,
            "checked_relationships": len(fk_checks),
            "orphan_records": orphan_records,
        }

    def validate_enum_constraints(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        enum_specs = [
            ("customers", "onboarding_status", ["PENDING", "IN_REVIEW", "APPROVED", "REJECTED", "SUSPENDED"]),
            ("documents", "document_status", ["UPLOADED", "UNDER_REVIEW", "VERIFIED", "REJECTED", "EXPIRED"]),
            ("verifications", "verification_status", ["PASSED", "FAILED", "INCONCLUSIVE"]),
            ("risk_ratings", "risk_tier", ["LOW", "MEDIUM", "HIGH"]),
            ("alerts", "severity", ["INFO", "WARNING", "HIGH", "CRITICAL"]),
        ]

        violations = []
        for tbl, col, allowed in enum_specs:
            placeholders = ", ".join([f"'{v}'" for v in allowed])
            query = f"SELECT {col}, COUNT(*) FROM {tbl} WHERE {col} NOT IN ({placeholders}) GROUP BY {col}"
            rows = cur.execute(query).fetchall()
            if rows:
                violations.append({"table": tbl, "column": col, "invalid_values": [r[0] for r in rows]})

        return {
            "passed": len(violations) == 0,
            "violations": violations,
        }

    def validate_date_ordering(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        date_checks = [
            (
                "documents",
                "issue_date <= expiry_date",
                "SELECT document_id, issue_date, expiry_date FROM documents WHERE expiry_date IS NOT NULL AND issue_date > expiry_date",
            ),
            (
                "review_cases",
                "scheduled_date <= due_date",
                "SELECT case_id, scheduled_date, due_date FROM review_cases WHERE scheduled_date > due_date",
            ),
            (
                "customers",
                "created_at <= updated_at",
                "SELECT customer_id, created_at, updated_at FROM customers WHERE created_at > updated_at",
            ),
        ]

        chronology_errors = []
        for tbl, rule, sql in date_checks:
            rows = cur.execute(sql).fetchall()
            if rows:
                chronology_errors.append({"table": tbl, "rule": rule, "count": len(rows)})

        return {
            "passed": len(chronology_errors) == 0,
            "errors": chronology_errors,
        }

    def validate_derived_reconciliation(self) -> Dict[str, Any]:
        """Verifies that stored customer completeness scores match live re-computation."""
        cur = self.conn.cursor()
        reqs = get_default_kyc_requirements()

        # Fetch sample of 100 customers and all their documents
        customers_raw = cur.execute("SELECT * FROM customers LIMIT 100").fetchall()
        cust_ids = [c["customer_id"] for c in customers_raw]
        placeholders = ", ".join(["?"] * len(cust_ids))

        docs_raw = cur.execute(f"SELECT * FROM documents WHERE customer_id IN ({placeholders})", cust_ids).fetchall()
        risk_raw = cur.execute(f"SELECT customer_id, risk_tier FROM risk_ratings WHERE customer_id IN ({placeholders})", cust_ids).fetchall()
        risk_map = {r["customer_id"]: r["risk_tier"] for r in risk_raw}

        docs_by_cust: Dict[str, List[Document]] = {}
        for d in docs_raw:
            doc_obj = Document(
                document_id=d["document_id"],
                customer_id=d["customer_id"],
                document_category=d["document_category"],
                document_type=d["document_type"],
                document_reference_number=d["document_reference_number"],
                issuing_country=d["issuing_country"],
                issue_date=d["issue_date"],
                expiry_date=d["expiry_date"],
                document_status=d["document_status"],
                file_hash_sha256=d["file_hash_sha256"],
                created_at=d["created_at"],
            )
            docs_by_cust.setdefault(d["customer_id"], []).append(doc_obj)

        mismatches = []
        for c in customers_raw:
            cust_obj = Customer(
                customer_id=c["customer_id"],
                customer_type_code=c["customer_type_code"],
                legal_name=c["legal_name"],
                trade_name=c["trade_name"],
                tax_id=c["tax_id"],
                jurisdiction=c["jurisdiction"],
                date_of_birth_or_inc=c["date_of_birth_or_inc"],
                onboarding_status=c["onboarding_status"],
                completeness_score=c["completeness_score"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
            )
            risk_tier = risk_map.get(c["customer_id"], "LOW")
            recomputed_score, _, _ = calculate_customer_completeness(
                cust_obj, risk_tier, docs_by_cust.get(c["customer_id"], []), reqs, ANCHOR_DATE
            )
            if abs(recomputed_score - c["completeness_score"]) > 0.001:
                mismatches.append({
                    "customer_id": c["customer_id"],
                    "stored": c["completeness_score"],
                    "recomputed": recomputed_score,
                })

        return {
            "passed": len(mismatches) == 0,
            "checked_customers": len(customers_raw),
            "mismatches": mismatches,
        }

    def evaluate_compliance_rules_against_ground_truth(self) -> Dict[str, Any]:
        """
        Executes audit inspection queries for the 5 compliance rules,
        then benchmarks detected violations against the ground_truth table.
        """
        cur = self.conn.cursor()

        # 1. Query Rule 1: Expired doc marked verified
        r1_sql = f"""
            SELECT document_id FROM documents
            WHERE expiry_date IS NOT NULL AND expiry_date < '{SIMULATION_ANCHOR_DATE}' AND document_status = 'VERIFIED'
        """
        detected_r1 = set(r[0] for r in cur.execute(r1_sql).fetchall())

        # 2. Query Rule 2: Customer approved with missing mandatory evidence
        r2_sql = """
            SELECT customer_id FROM customers
            WHERE onboarding_status = 'APPROVED' AND completeness_score < 1.0
        """
        detected_r2 = set(r[0] for r in cur.execute(r2_sql).fetchall())

        # 3. Query Rule 3: UBO sum > 100%
        r3_sql = """
            SELECT business_customer_id FROM beneficial_owners
            GROUP BY business_customer_id
            HAVING ROUND(SUM(ownership_percentage), 2) > 100.0
        """
        detected_r3 = set(r[0] for r in cur.execute(r3_sql).fetchall())

        # 4. Query Rule 4: Review closed without resolution
        r4_sql = """
            SELECT case_id FROM review_cases
            WHERE case_status = 'CLOSED_WITHOUT_RESOLUTION' OR resolution_outcome = 'UNRESOLVED'
        """
        detected_r4 = set(r[0] for r in cur.execute(r4_sql).fetchall())

        # 5. Query Rule 5: Duplicate document reference across distinct customers
        r5_sql = """
            SELECT d1.document_id FROM documents d1
            JOIN documents d2 ON d1.document_reference_number = d2.document_reference_number
                AND d1.customer_id <> d2.customer_id
                AND d1.document_id > d2.document_id
        """
        detected_r5 = set(r[0] for r in cur.execute(r5_sql).fetchall())

        # Fetch Ground Truth table entries
        gt_rows = cur.execute("SELECT anomaly_type, primary_entity_id FROM ground_truth").fetchall()
        gt_by_type: Dict[str, set] = {}
        for r in gt_rows:
            gt_by_type.setdefault(r["anomaly_type"], set()).add(r["primary_entity_id"])

        eval_breakdown = {}
        total_tp = 0
        total_fp = 0
        total_fn = 0

        rule_pairs = [
            ("EXPIRED_DOC_MARKED_VALID", detected_r1),
            ("APPROVED_WITHOUT_MANDATORY_EVIDENCE", detected_r2),
            ("UBO_PERCENTAGE_EXCEEDS_100", detected_r3),
            ("REVIEW_CLOSED_WITHOUT_RESOLUTION", detected_r4),
            ("DUPLICATE_DOCUMENT_CROSS_CUSTOMER", detected_r5),
        ]

        for anom_type, detected_set in rule_pairs:
            gt_set = gt_by_type.get(anom_type, set())
            tp = len(detected_set.intersection(gt_set))
            fp = len(detected_set - gt_set)
            fn = len(gt_set - detected_set)

            prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
            rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
            f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 1.0

            total_tp += tp
            total_fp += fp
            total_fn += fn

            eval_breakdown[anom_type] = {
                "ground_truth_count": len(gt_set),
                "detected_count": len(detected_set),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": prec,
                "recall": rec,
                "f1_score": f1,
            }

        overall_prec = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 1.0
        overall_rec = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 1.0
        overall_f1 = round(2 * overall_prec * overall_rec / (overall_prec + overall_rec), 4) if (overall_prec + overall_rec) > 0 else 1.0

        return {
            "overall_precision": overall_prec,
            "overall_recall": overall_rec,
            "f1_score": overall_f1,
            "total_anomalies_evaluated": total_tp + total_fn,
            "breakdown": eval_breakdown,
        }
