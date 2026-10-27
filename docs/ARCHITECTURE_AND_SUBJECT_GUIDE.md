# Complete Subject Guide & Architecture: KYC Onboarding Evidence, Completeness & Lifecycle Management

This guide explains the domain concepts, regulatory underpinnings, lifecycle state machines, actor responsibilities, and architectural design of the **KYC Onboarding Evidence Tracking and Lifecycle Management System**.

---

## 1. Domain Deep Dive & Subject Explanation

### 1.1 What is KYC & Why Does It Exist?
**Know Your Customer (KYC)** is the foundational regulatory process that banks, fintechs, brokerages, and cryptocurrency institutions use to verify customer identity, understand the customer's financial profile, and assess the risk of money laundering, terrorist financing, and fraud.

Key regulatory frameworks governing this domain include:
- **FATF (Financial Action Task Force) 40 Recommendations**: The global standard for Anti-Money Laundering (AML) and Countering the Financing of Terrorism (CFT).
- **FinCEN Customer Due Diligence (CDD) Final Rule** (USA): Mandates identifying beneficial owners of legal entities.
- **EU 4th, 5th, and 6th Anti-Money Laundering Directives (AMLD)**: Establish public registers of beneficial owners, stringent rules for high-risk third countries, and harmonized sanctions enforcement.
- **USA PATRIOT Act Section 326 (Customer Identification Program - CIP)**: Requires verifying name, date of birth, address, and identification number.

KYC is not a single form submission. It is an **ongoing, stateful lifecycle** comprised of three distinct tiers:
1. **CIP (Customer Identification Program)**: Collecting and verifying baseline identifiers (identity documents, proof of residential/business address, statutory tax numbers).
2. **CDD (Customer Due Diligence)**: Gauging the nature and purpose of customer relationships, screening against sanctions lists and Politically Exposed Persons (PEPs), and determining the customer's risk rating.
3. **EDD (Enhanced Due Diligence)**: Deeper scrutiny applied to high-risk customers, offshore corporate structures, or high-risk jurisdictions, requiring source-of-wealth declarations and senior compliance approval.

---

### 1.2 The Lifecycle of Onboarding Evidence
Evidence follows a strict progression:
1. **Evidence Gathering**: The customer uploads required documents according to their legal structure (e.g., Passport for Individuals; Certificate of Incorporation, Articles of Association, and Register of Directors for Corporates).
2. **Multi-Vector Verification**: Evidence is scrutinized via automated OCR extraction, government database lookups, MRZ (Machine Readable Zone) checksum validation, and manual analyst checks.
3. **Completeness Evaluation**: The system evaluates whether **all mandatory documents** for the customer's type and risk tier have passed verification.
4. **Approval Gating**: An account can **only transition to `APPROVED`** when completeness reaches 100% and risk screening is cleared.
5. **Surveillance & Document Currency**: Documents have expiration dates. The system tracks validity and issues predictive alerts at 90, 60, and 30 days before expiration.
6. **Periodic Reviews**: Ongoing reviews are scheduled based on risk score (e.g., High-risk reviewed every 12 months, Low-risk every 36 months).

---

### 1.3 Primary Actors and System Boundaries

```mermaid
flowchart TD
    subgraph Actors["Primary Actors"]
        CUST["Customer / Account Holder"]
        ANL["Operations Analyst"]
        REV["Risk / Compliance Reviewer"]
        ADM["System Administrator"]
    end

    subgraph CoreSystem["KYC Lifecycle & Evidence Platform"]
        INGEST["Document Ingestion & OCR"]
        ENGINE["Completeness & Rules Engine"]
        RISK["Risk Scoring & Screening"]
        SCHED["Periodic Review Scheduler"]
        ALERT["Expiration & Anomaly Alerts"]
        AUDIT["Immutable Audit Trail Engine"]
    end

    CUST -->|"Uploads Identity & Corporate Evidence"| INGEST
    INGEST -->|"Feeds Validated Documents"| ENGINE
    ENGINE -->|"Evaluates Mandatory Requirements"| RISK
    RISK -->|"Assigns Risk Tier (Low/Med/High)"| SCHED
    SCHED -->|"Triggers Scheduled Reviews & SLA"| ALERT
    
    ANL -->|"Conducts Document Verifications"| INGEST
    ANL -->|"Works Review Cases & Alerts"| ENGINE
    REV -->|"Signs Off EDD & Approves Edge Cases"| RISK
    ADM -->|"Configures Policies & Inspects Logs"| AUDIT

    ENGINE -.->|"Emits State Changes"| AUDIT
    ALERT -.->|"Emits Breach Events"| AUDIT
```

- **Customer / Account Holder**: Submits documents, updates expired credentials, and declares beneficial ownership.
- **Operations Analyst**: First line of defense. Inspects document discrepancies, verifies OCR outputs, matches names, and remediates alerts.
- **Risk / Compliance Reviewer**: Second line of defense. Evaluates high-risk cases, signs off on Enhanced Due Diligence (EDD), and resolves escalations.
- **System Administrator**: Configures KYC policies, manages requirement matrices, runs automated schedulers, and reviews system audit logs.

---

### 1.4 Ultimate Beneficial Ownership (UBO) & Corporate Transparency
Criminal entities frequently use complex holding companies and trusts to conceal illegal wealth. Under global standards:
- Any natural person who ultimately owns or controls **≥25%** of the shares or voting rights in a corporate entity must be identified, verified, and screened against sanctions.
- In higher-risk jurisdictions or PEP-linked entities, the threshold drops to **≥10%**.
- **Sum Constraint**: The total registered ownership percentage cannot exceed **100.0%**. An ownership percentage exceeding 100% represents a severe structural contradiction or fraudulent submission.

---

### 1.5 Immutable Audit Logging
In regulated finance, **traceability is a legal requirement**. Overwriting records destroys evidence.
Our system implements an append-only event sourcing model:
- When a document is verified, the document record updates its state, and an `AuditEvent` is generated recording:
  - `entity_type`: `DOCUMENT`
  - `entity_id`: `DOC-CUS-000001-001`
  - `actor_role`: `OPERATIONS_ANALYST`
  - `old_state`: `UNDER_REVIEW`
  - `new_state`: `VERIFIED`
  - `change_reason`: `MRZ validation and registry check passed`
  - `timestamp`: UTC ISO 8601

---

## 2. Entity-Relationship Model (Core Architecture)

```mermaid
erDiagram
    CUSTOMER_TYPE ||--o{ CUSTOMER : classifies
    CUSTOMER_TYPE ||--o{ KYC_REQUIREMENT : dictates
    CUSTOMER ||--o{ DOCUMENT : owns
    DOCUMENT ||--o{ VERIFICATION : audited_by
    CUSTOMER ||--|| RISK_RATING : evaluated_by
    CUSTOMER ||--o{ BENEFICIAL_OWNER : owns_equity_in
    CUSTOMER ||--o{ REVIEW_CASE : monitored_through
    CUSTOMER ||--o{ ALERT : triggers
    DOCUMENT ||--o{ ALERT : associates_with
    CUSTOMER ||--o{ AUDIT_EVENT : recorded_in

    CUSTOMER_TYPE {
        string type_code PK
        string type_name
        boolean is_business_entity
        float min_ubo_threshold
    }

    CUSTOMER {
        string customer_id PK "CUS-000001"
        string customer_type_code FK
        string legal_name
        string tax_id
        string jurisdiction
        date date_of_birth_or_inc
        string onboarding_status
        float completeness_score
        timestamp created_at
        timestamp updated_at
    }

    KYC_REQUIREMENT {
        string requirement_id PK "REQ-001"
        string customer_type_code FK
        string risk_tier
        string document_category
        string document_type
        boolean is_mandatory
        int validity_period_days
    }

    DOCUMENT {
        string document_id PK "DOC-CUS-000001-001"
        string customer_id FK
        string document_category
        string document_type
        string document_reference_number
        string issuing_country
        date issue_date
        date expiry_date
        string document_status
        string file_hash_sha256
        timestamp created_at
    }

    VERIFICATION {
        string verification_id PK "VRF-2026-000001"
        string document_id FK
        string verifier_actor
        string verification_method
        string verification_status
        string discrepancy_notes
        timestamp verified_at
    }

    RISK_RATING {
        string risk_id PK "RSK-2026-000001"
        string customer_id FK
        int risk_score
        string risk_tier
        string sanctions_screening_status
        string pep_status
        string jurisdiction_risk
        timestamp assessed_at
    }

    BENEFICIAL_OWNER {
        string owner_id PK "UBO-2026-000001"
        string business_customer_id FK
        string first_name
        string last_name
        float ownership_percentage
        string control_type
        boolean is_sanctions_screened
    }

    REVIEW_CASE {
        string case_id PK "REV-CUS-000001-2026"
        string customer_id FK
        string review_type
        string case_status
        string priority
        date scheduled_date
        date due_date
        string resolution_outcome
        timestamp resolved_at
    }

    ALERT {
        string alert_id PK "ALT-2026-000001"
        string customer_id FK
        string document_id FK
        string alert_type
        int lead_time_days
        string severity
        string alert_status
        timestamp created_at
    }

    AUDIT_EVENT {
        string event_id PK "AUD-2026-000001"
        string entity_type
        string entity_id
        string actor_role
        string event_type
        string old_state
        string new_state
        string change_reason
        timestamp timestamp
    }
```

---

## 3. State Machines & Lifecycle Transitions

### 3.1 Customer Onboarding Lifecycle
```mermaid
stateDiagram-v2
    [*] --> PENDING : Application Submitted
    PENDING --> IN_REVIEW : Evidence Ingested
    IN_REVIEW --> APPROVED : Completeness == 1.0 & Verifications Passed & Sanctions Cleared
    IN_REVIEW --> REJECTED : Fraudulent Evidence / Sanctions Hit
    APPROVED --> SUSPENDED : Overdue Review / Expired Critical Evidence / Anomaly
    SUSPENDED --> APPROVED : Remediation Review Completed & Verified
    SUSPENDED --> REJECTED : Offboarded / Failed Remediations
```

### 3.2 Document Lifecycle
```mermaid
stateDiagram-v2
    [*] --> UPLOADED : Document Received
    UPLOADED --> UNDER_REVIEW : In Verification Pipeline
    UNDER_REVIEW --> VERIFIED : Passed OCR & Authority Checks
    UNDER_REVIEW --> REJECTED : Tampered / Mismatch / Illegible
    VERIFIED --> EXPIRED : Current Date > Expiry Date
```

---

## 4. The 5 Deliberately Injected Edge Cases (Negative Scenarios)

In compliance auditing and RegTech AI model testing, the data generator must synthesize real-world failure patterns with separate ground-truth labels. The five mandated edge cases are:

| # | Anomaly Type | Compliance Impact & Manifestation | Target Entity | Expected Validation Rule Flag |
|---|---|---|---|---|
| 1 | `EXPIRED_DOC_MARKED_VALID` | A document whose `expiry_date` is earlier than the system anchor date (2026-10-26) but whose `document_status` is fraudulently or mistakenly set to `VERIFIED`. | `DOCUMENT` | `RULE_DOC_EXPIRY_INTEGRITY` |
| 2 | `APPROVED_WITHOUT_MANDATORY_EVIDENCE` | A customer whose `onboarding_status` is `APPROVED` even though their `completeness_score` is < 1.00 (mandatory documents are missing or rejected). | `CUSTOMER` | `RULE_ONBOARDING_COMPLETENESS_GATE` |
| 3 | `UBO_PERCENTAGE_EXCEEDS_100` | The arithmetic sum of beneficial ownership percentages for a business customer totals > 100.0% (e.g., 115.0%), indicating fraudulent capitalization or faulty registry filing. | `BENEFICIAL_OWNER` | `RULE_UBO_SUM_CONSTRAINT` |
| 4 | `REVIEW_CLOSED_WITHOUT_RESOLUTION` | A periodic review case whose `case_status` is `CLOSED_WITHOUT_RESOLUTION` and `resolution_outcome` is `UNRESOLVED`, yet the customer remains in active `APPROVED` status without remediation. | `REVIEW_CASE` | `RULE_REVIEW_OUTCOME_RESOLUTION` |
| 5 | `DUPLICATE_DOCUMENT_CROSS_CUSTOMER` | The exact same `document_reference_number` and passport/ID is claimed and verified across two entirely unrelated individual customers, indicating synthetic identity theft. | `DOCUMENT` | `RULE_DOC_GLOBAL_UNIQUENESS` |

---

## 5. Architectural Implementation
- **Deterministic ID Generator**: Counter-based padded IDs guaranteed to match reference constraints (`CUS-000001`, `DOC-CUS-000001-001`, `REV-CUS-000001-2026`, `ALT-2026-000001`).
- **Zero-Leakage Ground Truth**: Anomaly labels are written exclusively to `ground_truth.csv` and `ground_truth.json`. Primary data rows carry no labels that would leak ground truth to operational algorithms.
- **Reproducibility Guarantee**: Seeded via Python `random.Random(20261022)`. Running the generator twice produces identical SHA-256 file hashes.
