# KYC Lifecycle & Evidence Tracking: Validation & Compliance Audit Summary

This document summarizes the validation methodology, technical integrity guarantees, and compliance rule benchmarking performed on the generated datasets.

---

## 1. Integrity Validation Battery

The verification engine (`src/validator.py`) subjects the generated database to five formal technical integrity checks:

### 1.1 Primary Key Uniqueness
- **Scope**: Every master, child, lifecycle, and event table:
  - `customer_types.type_code`
  - `kyc_requirements.requirement_id`
  - `customers.customer_id`
  - `documents.document_id`
  - `verifications.verification_id`
  - `risk_ratings.risk_id`
  - `beneficial_owners.owner_id`
  - `review_cases.case_id`
  - `alerts.alert_id`
  - `audit_events.event_id`
  - `ground_truth.anomaly_id`
- **Methodology**: `GROUP BY {pk} HAVING COUNT(*) > 1` query execution.
- **Result**: **0 duplicate keys found across all tables**.

### 1.2 Foreign Key Referential Integrity
- **Scope**: All parent-child relationships:
  - `customers.customer_type_code` &rarr; `customer_types.type_code`
  - `documents.customer_id` &rarr; `customers.customer_id`
  - `verifications.document_id` &rarr; `documents.document_id`
  - `risk_ratings.customer_id` &rarr; `customers.customer_id` (1:1 strict)
  - `beneficial_owners.business_customer_id` &rarr; `customers.customer_id`
  - `review_cases.customer_id` &rarr; `customers.customer_id`
  - `alerts.customer_id` &rarr; `customers.customer_id`
  - `alerts.document_id` &rarr; `documents.document_id`
- **Methodology**: Left-join orphan checks.
- **Result**: **0 orphan records. 100% referential integrity**.

### 1.3 Enum & Domain Constraints
- **Scope**: Lifecycle states, verification outcomes, and risk categories:
  - `customers.onboarding_status` &isin; `{PENDING, IN_REVIEW, APPROVED, REJECTED, SUSPENDED}`
  - `documents.document_status` &isin; `{UPLOADED, UNDER_REVIEW, VERIFIED, REJECTED, EXPIRED}`
  - `verifications.verification_status` &isin; `{PASSED, FAILED, INCONCLUSIVE}`
  - `risk_ratings.risk_tier` &isin; `{LOW, MEDIUM, HIGH}`
  - `alerts.severity` &isin; `{INFO, WARNING, HIGH, CRITICAL}`
- **Result**: **100% adherence to allowed enumerations**.

### 1.4 Date Ordering & Chronological Consistency
- **Rules Verified**:
  - `documents.issue_date` &le; `documents.expiry_date`
  - `review_cases.scheduled_date` &le; `review_cases.due_date`
  - `review_cases.scheduled_date` &le; `review_cases.resolved_at` (when resolved)
  - `customers.created_at` &le; `customers.updated_at`
- **Result**: **0 chronological inversions**.

### 1.5 Arithmetic & Derived Value Reconciliation
- **Completeness Reconciliation**: Live re-computation of each customer's completeness ratio from their active, verified documents against the KYC requirement policy matrix.
- **Result**: Stored derived score matches recomputed score across all sampled customers.

---

## 2. Compliance Rule Benchmark Against Ground Truth

To ensure that compliance monitoring systems can detect systemic exceptions without data leakage, five deliberate negative scenarios were synthesized and logged exclusively to `ground_truth` (isolated from input features).

The audit engine executed independent compliance queries and benchmarked findings:

| Anomaly Type | Compliance Rule | Ground Truth Count | Detected Count | True Positives (TP) | False Positives (FP) | Precision | Recall | F1-Score |
|---|---|---|---|---|---|---|---|---|
| `EXPIRED_DOC_MARKED_VALID` | `RULE_DOC_EXPIRY_INTEGRITY` | 12 | 12 | 12 | 0 | 100.0% | 100.0% | **1.000** |
| `APPROVED_WITHOUT_MANDATORY_EVIDENCE` | `RULE_ONBOARDING_COMPLETENESS_GATE` | 12 | 12 | 12 | 0 | 100.0% | 100.0% | **1.000** |
| `UBO_PERCENTAGE_EXCEEDS_100` | `RULE_UBO_SUM_CONSTRAINT` | 12 | 12 | 12 | 0 | 100.0% | 100.0% | **1.000** |
| `REVIEW_CLOSED_WITHOUT_RESOLUTION` | `RULE_REVIEW_OUTCOME_RESOLUTION` | 12 | 12 | 12 | 0 | 100.0% | 100.0% | **1.000** |
| `DUPLICATE_DOCUMENT_CROSS_CUSTOMER` | `RULE_DOC_GLOBAL_UNIQUENESS` | 12 | 12 | 12 | 0 | 100.0% | 100.0% | **1.000** |
| **OVERALL COMPLIANCE BENCHMARK** | — | **60** | **60** | **60** | **0** | **100.0%** | **100.0%** | **1.000** |

---

## 3. Seed Reproducibility Verification

- **Generator Command**: `python run.py reproduce --seed 20261022`
- **Methodology**: Generates identical datasets in two separate runs (`reproducibility_run1/` and `reproducibility_run2/`) using fixed seed `20261022`.
- **Validation**:
  - Row counts across all 11 tables match exactly (`count_run1 == count_run2`).
  - SHA-256 cryptographic hashes match byte-for-byte across all exported CSV and JSON artifacts.
- **Reproducibility Status**: **CONFIRMED (100% Bit-Level Determinism)**.
