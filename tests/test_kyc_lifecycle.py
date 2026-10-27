"""
Unit and integration test suite for KYC Onboarding & Evidence Lifecycle Platform.
"""

import unittest
from datetime import date
from src.models import (
    Customer,
    CustomerType,
    KYCRequirement,
    Document,
    RiskRating,
    BeneficialOwner,
    ReviewCase,
    Alert,
    AuditEvent,
    GroundTruthAnomaly,
)
from src.rules import (
    get_default_customer_types,
    get_default_kyc_requirements,
    calculate_customer_completeness,
    evaluate_document_expiry_alert,
    get_periodic_review_interval_days,
)
from src.generator import KYCDataGenerator
from src.reproducibility import test_reproducibility


class TestKYCLifecycle(unittest.TestCase):
    def setUp(self):
        self.reqs = get_default_kyc_requirements()
        self.anchor = date(2026, 10, 26)

    def test_completeness_calculation_full(self):
        """Verifies that an individual with verified passport and utility bill is 100% complete."""
        cust = Customer(
            customer_id="CUS-000001",
            customer_type_code="INDIVIDUAL",
            legal_name="Jane Doe",
            trade_name=None,
            tax_id="US-TX-12345678",
            jurisdiction="US",
            date_of_birth_or_inc="1990-01-01",
            onboarding_status="PENDING",
            completeness_score=0.0,
            created_at="2026-01-01T09:00:00Z",
            updated_at="2026-01-01T09:00:00Z",
        )
        docs = [
            Document(
                document_id="DOC-CUS-000001-001",
                customer_id="CUS-000001",
                document_category="IDENTITY",
                document_type="PASSPORT",
                document_reference_number="P123456",
                issuing_country="US",
                issue_date="2024-01-01",
                expiry_date="2034-01-01",
                document_status="VERIFIED",
                file_hash_sha256="abc",
                created_at="2026-01-01T09:00:00Z",
            ),
            Document(
                document_id="DOC-CUS-000001-002",
                customer_id="CUS-000001",
                document_category="ADDRESS_PROOF",
                document_type="UTILITY_BILL",
                document_reference_number="UB999",
                issuing_country="US",
                issue_date="2026-09-01",
                expiry_date="2026-12-01",
                document_status="VERIFIED",
                file_hash_sha256="def",
                created_at="2026-01-01T09:00:00Z",
            ),
        ]
        score, satisfied, missing = calculate_customer_completeness(
            cust, "LOW", docs, self.reqs, self.anchor
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(len(missing), 0)

    def test_completeness_calculation_expired_doc_discounted(self):
        """Verifies that an expired document does NOT satisfy completeness."""
        cust = Customer(
            customer_id="CUS-000002",
            customer_type_code="INDIVIDUAL",
            legal_name="John Smith",
            trade_name=None,
            tax_id="US-TX-87654321",
            jurisdiction="US",
            date_of_birth_or_inc="1985-05-05",
            onboarding_status="PENDING",
            completeness_score=0.0,
            created_at="2026-01-01T09:00:00Z",
            updated_at="2026-01-01T09:00:00Z",
        )
        docs = [
            Document(
                document_id="DOC-CUS-000002-001",
                customer_id="CUS-000002",
                document_category="IDENTITY",
                document_type="PASSPORT",
                document_reference_number="P99999",
                issuing_country="US",
                issue_date="2015-01-01",
                expiry_date="2025-01-01",  # Expired prior to anchor date 2026-10-26
                document_status="VERIFIED",
                file_hash_sha256="abc",
                created_at="2026-01-01T09:00:00Z",
            )
        ]
        score, satisfied, missing = calculate_customer_completeness(
            cust, "LOW", docs, self.reqs, self.anchor
        )
        self.assertEqual(score, 0.0)
        self.assertIn("IDENTITY", missing)

    def test_document_expiry_alert_thresholds(self):
        """Checks lead-time calculation and severity assigning for document expirations."""
        doc_exp_past = Document(
            document_id="D1", customer_id="C1", document_category="IDENTITY", document_type="PASSPORT",
            document_reference_number="X1", issuing_country="US", issue_date="2020-01-01",
            expiry_date="2026-10-20",  # 6 days past
            document_status="EXPIRED", file_hash_sha256="h1", created_at="2020-01-01"
        )
        res_past = evaluate_document_expiry_alert(doc_exp_past, self.anchor)
        self.assertIsNotNone(res_past)
        self.assertEqual(res_past[0], "DOCUMENT_EXPIRED")
        self.assertEqual(res_past[2], "CRITICAL")

        doc_exp_soon = Document(
            document_id="D2", customer_id="C1", document_category="IDENTITY", document_type="PASSPORT",
            document_reference_number="X2", issuing_country="US", issue_date="2020-01-01",
            expiry_date="2026-11-10",  # 15 days ahead
            document_status="VERIFIED", file_hash_sha256="h2", created_at="2020-01-01"
        )
        res_soon = evaluate_document_expiry_alert(doc_exp_soon, self.anchor)
        self.assertIsNotNone(res_soon)
        self.assertEqual(res_soon[0], "DOCUMENT_EXPIRING_SOON")
        self.assertEqual(res_soon[2], "HIGH")

    def test_generator_starter_and_ground_truth(self):
        """Validates generator output counts and ground truth presence."""
        gen = KYCDataGenerator(seed=20261022, scale_profile="starter")
        gen.generate_all()
        self.assertEqual(len(gen.customers), 400)
        self.assertTrue(len(gen.documents) >= 400)
        self.assertTrue(len(gen.ground_truth) > 0)

        # Check all 5 anomaly types exist in ground truth
        anom_types = set(a.anomaly_type for a in gen.ground_truth)
        expected_types = {
            "EXPIRED_DOC_MARKED_VALID",
            "APPROVED_WITHOUT_MANDATORY_EVIDENCE",
            "UBO_PERCENTAGE_EXCEEDS_100",
            "REVIEW_CLOSED_WITHOUT_RESOLUTION",
            "DUPLICATE_DOCUMENT_CROSS_CUSTOMER",
        }
        self.assertEqual(expected_types.intersection(anom_types), expected_types)

    def test_reproducibility_harness(self):
        """Verifies bit-level reproducibility with fixed seed 20261022."""
        res = test_reproducibility(seed=20261022, profile="starter")
        self.assertTrue(res["is_reproducible"])
        self.assertTrue(res["row_count_match"])
        self.assertTrue(res["file_hash_match"])

    def test_live_pipeline_onboarding_and_auto_approval(self):
        """Tests live onboarding, evidence ingestion, gating, and periodic review scheduling."""
        import tempfile
        import sqlite3
        from src.models import SQL_SCHEMA
        from src.pipeline import LiveOnboardingPipeline, BatchSurveillancePipeline

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db = tf.name

        conn = sqlite3.connect(temp_db)
        conn.executescript(SQL_SCHEMA)
        # Seed types and requirements
        conn.execute("INSERT INTO customer_types VALUES ('INDIVIDUAL', 'Individual', 'Retail person', 0, 0.0)")
        for req in self.reqs:
            conn.execute(
                "INSERT INTO kyc_requirements VALUES (?, ?, ?, ?, ?, ?, ?)",
                (req.requirement_id, req.customer_type_code, req.risk_tier, req.document_category, req.document_type, int(req.is_mandatory), req.validity_period_days)
            )
        conn.commit()
        conn.close()

        pipeline = LiveOnboardingPipeline(temp_db)
        onb_res = pipeline.onboard_new_customer(
            customer_type_code="INDIVIDUAL",
            legal_name="Alice Walker",
            tax_id="US-TX-44556677",
            jurisdiction="US",
            date_of_birth_or_inc="1994-03-20",
        )
        cust_id = onb_res["customer_id"]
        self.assertEqual(onb_res["onboarding_status"], "PENDING")
        self.assertEqual(onb_res["completeness_score"], 0.0)

        # Upload 1st document: IDENTITY
        up1 = pipeline.upload_and_process_evidence(
            customer_id=cust_id,
            document_category="IDENTITY",
            document_type="PASSPORT",
            document_reference_number="P778899",
            issuing_country="US",
            issue_date="2024-01-01",
            expiry_date="2034-01-01",
        )
        self.assertEqual(up1["completeness_score"], 0.5)
        self.assertFalse(up1["auto_approved"])

        # Upload 2nd document: ADDRESS_PROOF -> Triggers Auto-Approval
        up2 = pipeline.upload_and_process_evidence(
            customer_id=cust_id,
            document_category="ADDRESS_PROOF",
            document_type="UTILITY_BILL",
            document_reference_number="UB-112233",
            issuing_country="US",
            issue_date="2026-08-01",
            expiry_date=None,
        )
        self.assertEqual(up2["completeness_score"], 1.0)
        self.assertTrue(up2["auto_approved"])
        self.assertEqual(up2["customer_status"], "APPROVED")
        self.assertIsNotNone(up2["scheduled_review_case"])

        # Clean up temp db
        import os
        if os.path.exists(temp_db):
            os.remove(temp_db)


if __name__ == "__main__":
    unittest.main()
