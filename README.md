# KYC Onboarding Evidence Tracking & Lifecycle Management Platform

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Reproducibility](https://img.shields.io/badge/Seed-20261022-brightgreen.svg)]()
[![Precision/Recall](https://img.shields.io/badge/Auditor%20F1-100%25-success.svg)]()
[![Zero External Dependencies](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-orange.svg)]()

**tracking customer onboarding evidence, validating document completeness, managing periodic reviews, surveillance of expirations, and auditing compliance anomalies with isolated ground-truth benchmarks**.

---

## 1. Executive Summary & Capabilities

This platform models the regulatory evidence lifecycle of financial institutions under FATF, FinCEN CDD, and EU 5AMLD/6AMLD frameworks:
- **Parent-First Master Data Modeling**: 10 interconnected entities spanning Customers, Customer Types, KYC Requirements, Documents, Verifications, Risk Ratings, Beneficial Owners (UBO), Review Cases, Alerts, and an Immutable Audit Log.
- **Rule-Driven Completeness Engine**: Dynamically scores onboarding readiness (0% to 100%) against regulatory policy matrices tailored to entity type and risk tier.
- **Automated Expiration Surveillance**: Tracks document currency with predictive lead-time alerting (90, 60, 30 days, and expired).
- **Periodic Review Scheduling**: Derives statutory review deadlines based on risk ratings (High: 1 yr, Medium: 2 yrs, Low: 3 yrs).
- **Labelled Anomaly Injection**: Deliberately injects 5 compliance failure edge cases with isolated ground-truth tracking (`ground_truth.csv` / `ground_truth.json`).
- **Cryptographic Reproducibility**: Seeded with PRNG seed `20261022`, ensuring 100% byte-exact reproducibility across runs.
- **Interactive Web Dashboard**: Zero external pip dependencies; powered by Python's standard library `http.server`.

---

## 2. Entity Model & Nomenclature Conventions

| Entity | Primary Key | Description & Cardinality |
| :--- | :--- | :--- |
| **`CustomerType`** | `type_code` (e.g., `INDIVIDUAL`, `CORPORATE`) | Master classification governing required document policies. |
| **`Customer`** | `CUS-000001` to `CUS-008000` | Account holder master profile (`1:N` to docs, reviews, alerts). |
| **`KYCRequirement`** | `REQ-IND-001`, `REQ-CORP-001` | Statutory policy matrix mapping required evidence categories by type and risk. |
| **`Document`** | `DOC-CUS-000001-001` | Evidence item submitted by customer with issue/expiry dates. |
| **`Verification`** | `VRF-2026-000001` | Audit checks performed via OCR, Biometrics, or Analysts. |
| **`RiskRating`** | `RSK-2026-000001` | AML/CFT score (0-100), risk tier (LOW/MED/HIGH), PEP, and sanctions state (`1:1`). |
| **`BeneficialOwner`** | `UBO-2026-000001` | Ultimate Beneficial Ownership equity registry for corporate entities. |
| **`ReviewCase`** | `REV-CUS-000001-2026` | Periodic review workflow tracking review schedules and outcomes. |
| **`Alert`** | `ALT-2026-000001` | Operational surveillance alerts for expiring evidence and overdue reviews. |
| **`AuditEvent`** | `AUD-2026-000001` | Append-only event log capturing all state changes and reasons. |
| **`GroundTruth`** | `ANO-000001` | Isolated reference manifest of deliberate anomalies. |

---

## 3. The 5 Mandated Negative Scenarios (Ground Truth)

The generator synthesizes valid baseline records first, then injects labelled edge cases:
1. **`EXPIRED_DOC_MARKED_VALID`**: A document past its expiration date whose status is fraudulently set to `VERIFIED` (`RULE_DOC_EXPIRY_INTEGRITY`).
2. **`APPROVED_WITHOUT_MANDATORY_EVIDENCE`**: A customer marked `APPROVED` whose completeness score is < 1.00 (`RULE_ONBOARDING_COMPLETENESS_GATE`).
3. **`UBO_PERCENTAGE_EXCEEDS_100`**: Beneficial ownership total percentage exceeds 100.0% (`RULE_UBO_SUM_CONSTRAINT`).
4. **`REVIEW_CLOSED_WITHOUT_RESOLUTION`**: A periodic review case closed as `CLOSED_WITHOUT_RESOLUTION` without definitive outcome (`RULE_REVIEW_OUTCOME_RESOLUTION`).
5. **`DUPLICATE_DOCUMENT_CROSS_CUSTOMER`**: Identical document reference number reused across distinct customers (`RULE_DOC_GLOBAL_UNIQUENESS`).

---

## 4. Quickstart Guide

### 4.1 Generate the Dataset
Generate the baseline target volume (8,000 customers, 20,000 documents, 1,000 business entities, 3,000 review cases) with fixed seed `20261022`:
```powershell
python run.py generate --profile full --seed 20261022
```
*Tip: For quick unit testing, use `--profile starter` (400 customers, 1,000 documents).*

### 4.2 Validate Integrity & Benchmark Compliance Rules
Runs the technical integrity battery (PK uniqueness, FK integrity, Enums, Date ordering, Reconciliation) and benchmarks the compliance auditor against `ground_truth`:
```powershell
python run.py validate
```
Expected output:
```text
Primary Key Uniqueness:      PASS
Foreign Key Integrity:        PASS
Enum & Domain Constraints:    PASS
Date Chronology Ordering:     PASS
Completeness Reconciliation:  PASS

--- COMPLIANCE RULE AUDITOR EVALUATION ---
Evaluated Anomalies:          60
Auditor Precision:            100.00%
Auditor Recall:               100.00%
Auditor F1-Score:             100.00%
```

### 4.3 Verify Step 10 Reproducibility
Runs two independent generation cycles with seed `20261022` and verifies byte-for-byte SHA-256 match and row count equality:
```powershell
python run.py reproduce --seed 20261022
```

### 4.4 Run Unit & Integration Tests
```powershell
python -m unittest discover -s tests
```

### 4.5 Launch Interactive Web Dashboard & REST API
```powershell
python run.py serve
```
Open your browser to: **[http://localhost:8501](http://localhost:8501)**

*(Note: Port 8501 is used by default to prevent conflicts with legacy services like Oracle XE or Apache Tomcat that occupy port 8080. You can also specify any custom port, e.g. `python run.py serve --port 8000`).*

### 4.6 Live Onboarding & Interactive Pipeline CLI

You can execute live operational workflows on the system:

1. **Onboard a New Customer**:
```powershell
python run.py onboard --name "Apex Logistics LLC" --type CORPORATE --tax-id "US-TX-998877" --jurisdiction US --dob 2021-04-12
```

2. **Upload Evidence & Trigger Auto-Approval Gating**:
```powershell
python run.py upload-doc --customer CUS-008001 --category INCORPORATION --doc-type CERTIFICATE_OF_INC --ref INC-882211 --country US --issue 2021-04-12
```
*(As you ingest mandatory documents, the engine recalculates completeness: 25% -> 50% -> 75% -> 100%. Once 100% is reached, the account automatically transitions to `APPROVED` and schedules its first statutory periodic review!)*

3. **Run Daily Scheduled Batch Surveillance**:
```powershell
python run.py batch-surveillance
```

4. **Advance Simulation Clock (Time Machine Engine)**:
```powershell
python run.py advance-time --days 60
```
*(Advances the calendar forward by 60 days, aging documents and review cases to trigger upcoming expiration warnings and escalate overdue reviews!)*

---

## 5. REST API Endpoints

The embedded web server exposes the following JSON endpoints:
- `GET /api/stats`: High-level portfolio KPIs (customers, approval rates, average completeness, alerts, anomalies).
- `GET /api/customers?status=APPROVED&limit=50`: Paginated, filterable customer list with risk ratings.
- `GET /api/customer/<customer_id>`: Comprehensive dossier (customer, risk rating, documents, UBO structure, review cases, alerts, audit events).
- `GET /api/alerts?severity=CRITICAL`: Active surveillance and expiration alerts.
- `GET /api/reviews?status=OPEN`: Periodic review case queue.
- `GET /api/audit`: Append-only event trail of recent state changes.
- `GET /api/compliance-audit`: Real-time benchmark calculating Precision, Recall, and F1-Score against ground truth.

---

## 6. Directory Structure

```text
kyc_onboarding_lifecycle/
├── data/                               # Generated datasets
│   ├── kyc_lifecycle.db                # SQLite database (14 MB)
│   ├── seed_data.sql                   # Full SQL insert dump (23 MB)
│   ├── customers.csv / .json           # 8,000 customers
│   ├── documents.csv / .json           # 20,000 documents
│   ├── verifications.csv / .json       # 20,000 verification records
│   ├── risk_ratings.csv / .json        # 8,000 risk evaluations
│   ├── beneficial_owners.csv / .json   # 2,478 UBO equity owners
│   ├── review_cases.csv / .json        # 3,000 review cases
│   ├── alerts.csv / .json              # Operational alerts
│   ├── audit_events.csv / .json        # Event store
│   └── ground_truth.csv / .json        # Isolated anomaly ground truth
├── docs/                               # Detailed documentation
│   ├── DATA_DICTIONARY.md              # Complete field specs, enums, & constraints
│   ├── ARCHITECTURE_AND_SUBJECT_GUIDE.md # Domain guide & Mermaid architecture diagrams
│   ├── VALIDATION_SUMMARY.md           # Validation methodologies & audit metrics
│   └── SOURCE_MANIFEST.md             # Lawful provenance & zero-PII statement
├── src/                                # Core application source
│   ├── models.py                       # Dataclasses & SQL schema DDL
│   ├── rules.py                        # Compliance rules & completeness calculator
│   ├── generator.py                    # Deterministic synthetic data generator
│   ├── exporter.py                     # CSV, JSON, SQLite, and SQL dumper
│   ├── validator.py                    # Integrity validator & compliance auditor
│   ├── reproducibility.py              # Step 10 double-generation tester
│   ├── web_server.py                   # Embedded REST API & SPA Dashboard
│   └── cli.py                          # Unified CLI entrypoint
├── tests/                              # Unit & integration tests
│   └── test_kyc_lifecycle.py
├── run.py                              # Top-level executable runner
└── README.md                           # Project documentation
```
