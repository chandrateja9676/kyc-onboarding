"""
Operational Pipeline Module for KYC Lifecycle & Onboarding Evidence Platform.
Provides:
1. Live Event-Driven Onboarding & Evidence Ingestion Pipeline
2. Live Case Resolution & Document Remediation Pipeline
3. Scheduled Batch Surveillance Engine (Nightly Job Simulation)
4. Time Machine Engine (Advancing Simulation Clock & Executing Scheduled Workflows)
"""

import sqlite3
import hashlib
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.models import (
    Customer,
    Document,
    Verification,
    RiskRating,
    ReviewCase,
    Alert,
    AuditEvent,
    SIMULATION_ANCHOR_DATE,
)
from src.rules import (
    ANCHOR_DATE,
    get_default_kyc_requirements,
    calculate_customer_completeness,
    get_periodic_review_interval_days,
    evaluate_document_expiry_alert,
)


def _get_next_id(cur, table: str, col: str, prefix: str) -> str:
    row = cur.execute(f"SELECT {col} FROM {table} WHERE {col} LIKE '{prefix}%' ORDER BY {col} DESC LIMIT 1").fetchone()
    if row and row[0]:
        num_str = row[0].replace(prefix, "")
        try:
            next_num = int(num_str) + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1
    return f"{prefix}{next_num:06d}"


class LiveOnboardingPipeline:
    """
    Handles live transactional mutations: onboarding new customers,
    ingesting evidence, calculating completeness gates, auto-approvals,
    and persisting immutable audit trails.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def onboard_new_customer(
        self,
        customer_type_code: str,
        legal_name: str,
        tax_id: str,
        jurisdiction: str,
        date_of_birth_or_inc: str,
        trade_name: Optional[str] = None,
        actor_id: str = "SYS_ONBOARDING_PORTAL",
    ) -> Dict[str, Any]:
        """Initiates an onboarding application for a new customer."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Generate deterministic next customer ID
        customer_id = _get_next_id(cur, "customers", "customer_id", "CUS-")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Initial risk assessment
        risk_id = _get_next_id(cur, "risk_ratings", "risk_id", "RSK-2026-")

        # Risk scoring
        base_score = 25
        if jurisdiction in ["CY", "KY"]:
            base_score += 20
        elif jurisdiction in ["PA", "AE"]:
            base_score += 45
        if customer_type_code in ["CORPORATE", "TRUST"]:
            base_score += 15

        risk_tier = "HIGH" if base_score >= 70 else ("MEDIUM" if base_score >= 40 else "LOW")

        # Insert customer
        cur.execute(
            """
            INSERT INTO customers (
                customer_id, customer_type_code, legal_name, trade_name,
                tax_id, jurisdiction, date_of_birth_or_inc, onboarding_status,
                completeness_score, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', 0.0, ?, ?)
            """,
            (customer_id, customer_type_code, legal_name, trade_name, tax_id, jurisdiction, date_of_birth_or_inc, now_str, now_str),
        )

        # Insert risk rating
        cur.execute(
            """
            INSERT INTO risk_ratings (
                risk_id, customer_id, risk_score, risk_tier, rationale,
                sanctions_screening_status, pep_status, jurisdiction_risk,
                assessed_by, assessed_at
            ) VALUES (?, ?, ?, ?, ?, 'CLEARED', 'PEP_CLEAR', ?, 'SYSTEM_RULES_ENGINE', ?)
            """,
            (risk_id, customer_id, base_score, risk_tier, f"Initial evaluation for {jurisdiction} entity", "STANDARD" if base_score < 40 else "ELEVATED", now_str),
        )

        # Audit event
        aud_id = _get_next_id(cur, "audit_events", "event_id", "AUD-2026-")
        cur.execute(
            """
            INSERT INTO audit_events (
                event_id, entity_type, entity_id, actor_role, actor_id,
                event_type, old_state, new_state, change_reason, timestamp
            ) VALUES (?, 'CUSTOMER', ?, 'CUSTOMER', ?, 'CREATED', NULL, 'PENDING', 'New onboarding application registered', ?)
            """,
            (aud_id, customer_id, actor_id, now_str),
        )

        conn.commit()
        conn.close()

        return {
            "customer_id": customer_id,
            "onboarding_status": "PENDING",
            "completeness_score": 0.0,
            "risk_tier": risk_tier,
            "risk_score": base_score,
            "message": f"Customer {customer_id} successfully created in PENDING state.",
        }

    def upload_and_process_evidence(
        self,
        customer_id: str,
        document_category: str,
        document_type: str,
        document_reference_number: str,
        issuing_country: str,
        issue_date: str,
        expiry_date: Optional[str] = None,
        verifier_actor: str = "OPERATIONS_ANALYST",
    ) -> Dict[str, Any]:
        """
        Uploads document, runs verification, recalculates completeness,
        and auto-approves if all mandatory criteria are satisfied.
        """
        conn = self._get_connection()
        cur = conn.cursor()

        cust = cur.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if not cust:
            conn.close()
            raise ValueError(f"Customer {customer_id} not found.")

        # Determine doc index
        existing_docs = cur.execute("SELECT COUNT(*) FROM documents WHERE customer_id = ?", (customer_id,)).fetchone()[0]
        doc_id = f"DOC-{customer_id}-{(existing_docs + 1):03d}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Automated OCR / verification check
        exp_date_obj = datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None
        current_anchor = ANCHOR_DATE

        is_expired = exp_date_obj and exp_date_obj <= current_anchor
        doc_status = "EXPIRED" if is_expired else "VERIFIED"
        vrf_status = "PASSED"

        sha = hashlib.sha256(f"{doc_id}:{document_reference_number}:{customer_id}".encode("utf-8")).hexdigest()

        # Insert document
        cur.execute(
            """
            INSERT INTO documents (
                document_id, customer_id, document_category, document_type,
                document_reference_number, issuing_country, issue_date,
                expiry_date, document_status, file_hash_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, customer_id, document_category, document_type, document_reference_number, issuing_country, issue_date, expiry_date, doc_status, sha, now_str),
        )

        # Insert verification
        vrf_id = _get_next_id(cur, "verifications", "verification_id", "VRF-2026-")
        cur.execute(
            """
            INSERT INTO verifications (
                verification_id, document_id, verifier_actor, verification_method,
                verification_status, discrepancy_notes, verified_at
            ) VALUES (?, ?, ?, 'AUTOMATED_OCR', ?, NULL, ?)
            """,
            (vrf_id, doc_id, verifier_actor, vrf_status, now_str),
        )

        # Recalculate customer completeness
        risk = cur.execute("SELECT risk_tier FROM risk_ratings WHERE customer_id = ?", (customer_id,)).fetchone()
        risk_tier = risk["risk_tier"] if risk else "LOW"

        all_cust_docs = cur.execute("SELECT * FROM documents WHERE customer_id = ?", (customer_id,)).fetchall()
        doc_objects = [
            Document(
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
            for d in all_cust_docs
        ]

        cust_obj = Customer(
            customer_id=cust["customer_id"],
            customer_type_code=cust["customer_type_code"],
            legal_name=cust["legal_name"],
            trade_name=cust["trade_name"],
            tax_id=cust["tax_id"],
            jurisdiction=cust["jurisdiction"],
            date_of_birth_or_inc=cust["date_of_birth_or_inc"],
            onboarding_status=cust["onboarding_status"],
            completeness_score=cust["completeness_score"],
            created_at=cust["created_at"],
            updated_at=cust["updated_at"],
        )

        reqs = get_default_kyc_requirements()
        new_score, satisfied, missing = calculate_customer_completeness(
            cust_obj, risk_tier, doc_objects, reqs, current_anchor
        )

        new_status = cust["onboarding_status"]
        auto_approved = False
        new_review_case_id = None

        # Approval Gating Logic
        if new_score == 1.0 and cust["onboarding_status"] in ["PENDING", "IN_REVIEW"]:
            new_status = "APPROVED"
            auto_approved = True

            # Schedule first periodic review based on risk tier
            interval_days = get_periodic_review_interval_days(risk_tier)
            sched_date = (current_anchor + timedelta(days=interval_days)).isoformat()
            due_date = (current_anchor + timedelta(days=interval_days + 30)).isoformat()
            new_review_case_id = f"REV-{customer_id}-2026"

            cur.execute(
                """
                INSERT OR REPLACE INTO review_cases (
                    case_id, customer_id, review_type, case_status, priority,
                    scheduled_date, due_date, assigned_analyst, resolved_at,
                    resolution_outcome, created_at
                ) VALUES (?, ?, 'PERIODIC_ANNUAL', 'OPEN', ?, ?, ?, 'ANALYST_S_CHEN', NULL, NULL, ?)
                """,
                (new_review_case_id, customer_id, "URGENT" if risk_tier == "HIGH" else "NORMAL", sched_date, due_date, now_str),
            )

        # Update customer
        cur.execute(
            """
            UPDATE customers
            SET completeness_score = ?, onboarding_status = ?, updated_at = ?
            WHERE customer_id = ?
            """,
            (new_score, new_status, now_str, customer_id),
        )

        # Audit event for state mutation
        aud_id = _get_next_id(cur, "audit_events", "event_id", "AUD-2026-")
        reason = f"Evidence {doc_id} verified. Completeness score updated to {new_score * 100:.1f}%."
        if auto_approved:
            reason += " Completeness threshold achieved; account auto-transitioned to APPROVED."

        cur.execute(
            """
            INSERT INTO audit_events (
                event_id, entity_type, entity_id, actor_role, actor_id,
                event_type, old_state, new_state, change_reason, timestamp
            ) VALUES (?, 'DOCUMENT', ?, 'OPERATIONS_ANALYST', ?, 'VERIFICATION_COMPLETED', ?, ?, ?, ?)
            """,
            (aud_id, doc_id, verifier_actor, cust["onboarding_status"], new_status, reason, now_str),
        )

        conn.commit()
        conn.close()

        return {
            "document_id": doc_id,
            "verification_id": vrf_id,
            "verification_status": vrf_status,
            "completeness_score": new_score,
            "satisfied_categories": satisfied,
            "missing_categories": missing,
            "customer_status": new_status,
            "auto_approved": auto_approved,
            "scheduled_review_case": new_review_case_id,
        }

    def resolve_review_case(
        self,
        case_id: str,
        analyst_id: str,
        resolution_outcome: str,
        notes: str = "Annual review completed satisfying CDD policy",
    ) -> Dict[str, Any]:
        """Resolves a periodic review case and updates risk/alerts accordingly."""
        conn = self._get_connection()
        cur = conn.cursor()

        case = cur.execute("SELECT * FROM review_cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            conn.close()
            raise ValueError(f"Review case {case_id} not found.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Update case
        cur.execute(
            """
            UPDATE review_cases
            SET case_status = 'APPROVED', resolution_outcome = ?, assigned_analyst = ?, resolved_at = ?
            WHERE case_id = ?
            """,
            (resolution_outcome, analyst_id, now_str, case_id),
        )

        # Resolve any associated overdue alerts for this customer
        cur.execute(
            """
            UPDATE alerts
            SET alert_status = 'RESOLVED'
            WHERE customer_id = ? AND alert_type = 'PERIODIC_REVIEW_OVERDUE'
            """,
            (case["customer_id"],),
        )

        # Audit event
        aud_id = _get_next_id(cur, "audit_events", "event_id", "AUD-2026-")
        cur.execute(
            """
            INSERT INTO audit_events (
                event_id, entity_type, entity_id, actor_role, actor_id,
                event_type, old_state, new_state, change_reason, timestamp
            ) VALUES (?, 'REVIEW_CASE', ?, 'RISK_COMPLIANCE_REVIEWER', ?, 'STATUS_CHANGED', 'OPEN', 'APPROVED', ?, ?)
            """,
            (aud_id, case_id, analyst_id, f"Review resolved as {resolution_outcome}: {notes}", now_str),
        )

        conn.commit()
        conn.close()

        return {
            "case_id": case_id,
            "new_status": "APPROVED",
            "resolution_outcome": resolution_outcome,
            "message": f"Review case {case_id} resolved with outcome '{resolution_outcome}'.",
        }


class BatchSurveillancePipeline:
    """
    Simulates enterprise nightly batch jobs:
    - Expiration scanner (identifies expiring and expired documents)
    - Periodic review generator (spawns reviews when cycles mature)
    - SLA escalation engine (escalates overdue cases to critical alerts)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run_daily_surveillance(self, current_date: date = ANCHOR_DATE) -> Dict[str, Any]:
        """Executes full daily batch surveillance suite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        date_str = current_date.isoformat()
        now_str = f"{date_str}T04:00:00Z"

        new_alerts_count = 0
        overdue_reviews_count = 0
        new_reviews_scheduled = 0

        # 1. Document Expiration Scan
        docs = cur.execute("SELECT * FROM documents WHERE expiry_date IS NOT NULL").fetchall()
        for d in docs:
            exp_date = datetime.strptime(d["expiry_date"], "%Y-%m-%d").date()
            delta = (exp_date - current_date).days

            # Check if alert already exists for this document
            existing = cur.execute(
                "SELECT alert_id FROM alerts WHERE document_id = ? AND alert_status != 'RESOLVED'",
                (d["document_id"],),
            ).fetchone()

            if not existing:
                eval_res = None
                if delta < 0:
                    eval_res = ("DOCUMENT_EXPIRED", delta, "CRITICAL")
                elif 0 <= delta <= 30:
                    eval_res = ("DOCUMENT_EXPIRING_SOON", delta, "HIGH")
                elif 31 <= delta <= 60:
                    eval_res = ("DOCUMENT_EXPIRING_SOON", delta, "WARNING")
                elif 61 <= delta <= 90:
                    eval_res = ("DOCUMENT_EXPIRING_SOON", delta, "INFO")

                if eval_res:
                    atype, lead, sev = eval_res
                    alt_id = _get_next_id(cur, "alerts", "alert_id", "ALT-2026-")
                    cur.execute(
                        """
                        INSERT INTO alerts (
                            alert_id, customer_id, document_id, alert_type,
                            lead_time_days, severity, alert_status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 'NEW', ?)
                        """,
                        (alt_id, d["customer_id"], d["document_id"], atype, lead, sev, now_str),
                    )
                    new_alerts_count += 1

        # 2. Overdue Review SLA Escalation
        open_cases = cur.execute("SELECT * FROM review_cases WHERE case_status = 'OPEN'").fetchall()
        for rc in open_cases:
            due = datetime.strptime(rc["due_date"], "%Y-%m-%d").date()
            if due < current_date:
                overdue_days = (current_date - due).days
                # Check existing overdue alert
                existing = cur.execute(
                    "SELECT alert_id FROM alerts WHERE customer_id = ? AND alert_type = 'PERIODIC_REVIEW_OVERDUE' AND alert_status != 'RESOLVED'",
                    (rc["customer_id"],),
                ).fetchone()

                if not existing:
                    alt_id = _get_next_id(cur, "alerts", "alert_id", "ALT-2026-")
                    cur.execute(
                        """
                        INSERT INTO alerts (
                            alert_id, customer_id, document_id, alert_type,
                            lead_time_days, severity, alert_status, created_at
                        ) VALUES (?, ?, NULL, 'PERIODIC_REVIEW_OVERDUE', ?, 'CRITICAL', 'NEW', ?)
                        """,
                        (alt_id, rc["customer_id"], -overdue_days, now_str),
                    )
                    # Escalate case priority
                    cur.execute("UPDATE review_cases SET priority = 'URGENT' WHERE case_id = ?", (rc["case_id"],))
                    overdue_reviews_count += 1

        conn.commit()
        conn.close()

        return {
            "surveillance_date": date_str,
            "new_expiration_alerts": new_alerts_count,
            "overdue_cases_escalated": overdue_reviews_count,
            "status": "BATCH_SURVEILLANCE_COMPLETED",
        }


class TimeMachineEngine:
    """
    Enables interactive temporal simulation: advances the clock by N days,
    triggers scheduled surveillance pipelines, and reports changes.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.surveillance = BatchSurveillancePipeline(db_path)

    def advance_time(self, days: int = 30) -> Dict[str, Any]:
        """Simulates advancing the calendar forward by N days."""
        new_anchor = ANCHOR_DATE + timedelta(days=days)
        surv_result = self.surveillance.run_daily_surveillance(current_date=new_anchor)
        return {
            "prior_anchor_date": ANCHOR_DATE.isoformat(),
            "new_anchor_date": new_anchor.isoformat(),
            "days_advanced": days,
            "batch_results": surv_result,
        }
