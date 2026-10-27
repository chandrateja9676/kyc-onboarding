# KYC Lifecycle & Onboarding Evidence Tracking: Data Dictionary

This document provides the definitive data dictionary for the Customer Onboarding Evidence Tracking, Completeness Validation, and Lifecycle Review System. Every field, primary key, foreign key, cardinality, allowed enumeration, unit, uniqueness rule, and validation constraint is detailed below.

---

## 1. Master Entity: `CustomerType`
Defines the legal constitution of a customer entity and governs the applicable KYC requirement profile.

- **Storage Table**: `customer_types`
- **Cardinality**: `1:N` to `customers`, `1:N` to `kyc_requirements`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `type_code` | TEXT (PK) | Required | `INDIVIDUAL`, `CORPORATE`, `TRUST`, `PARTNERSHIP` | Unique | ISO identifier code representing the legal structure. Primary key. |
| `type_name` | TEXT | Required | E.g. `"Individual / Natural Person"`, `"Corporation / Limited Company"` | Unique | Human-readable name of customer classification. |
| `description` | TEXT | Required | Free text description | Non-unique | Explanatory description of legal entity type. |
| `is_business_entity`| BOOLEAN | Required | `0` (False), `1` (True) | Non-unique | Flags if entity requires Ultimate Beneficial Ownership (UBO) structure. |
| `min_ubo_threshold` | REAL | Required | `0.10` to `0.25` (Default `0.25` = 25%) | Non-unique | Regulatory threshold above which beneficial owners must be registered. |

---

## 2. Core Entity: `Customer`
Master record representing the account applicant or existing customer.

- **Storage Table**: `customers`
- **Cardinality**: `1:N` to `documents`, `1:1` to `risk_ratings`, `1:N` to `review_cases`, `1:N` to `beneficial_owners`, `1:N` to `alerts`, `1:N` to `audit_events`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | TEXT (PK) | Required | Pattern: `^CUS-\d{6}$` (e.g., `CUS-000001`) | Unique | Immutable, zero-padded identifier. Primary key. |
| `customer_type_code`| TEXT (FK) | Required | Must exist in `customer_types.type_code` | Non-unique | Foreign key referencing legal classification. |
| `legal_name` | TEXT | Required | Non-empty string (e.g., "Apex Logistics LLC") | Non-unique | Official registered name matching statutory records. |
| `trade_name` | TEXT | Optional | String or `NULL` | Non-unique | "Doing Business As" (DBA) trade name. |
| `tax_id` | TEXT | Required | Pattern alphanumeric 9-12 chars (e.g., `EIN-98421092`) | Unique (except deliberate fraud edge cases) | National or federal tax identification number. |
| `jurisdiction` | TEXT | Required | ISO 3166-1 alpha-2 (e.g., `US`, `GB`, `DE`, `SG`, `CY`) | Non-unique | Country of domicile/tax incorporation. |
| `date_of_birth_or_inc`| DATE | Required | ISO 8601 `YYYY-MM-DD` | Non-unique | Must be before current system date. Must be age >= 18 for individuals. |
| `onboarding_status`| TEXT | Required | `PENDING`, `IN_REVIEW`, `APPROVED`, `REJECTED`, `SUSPENDED` | Non-unique | Lifecycle state. Approved requires 100% completeness unless an edge case. |
| `completeness_score`| REAL | Required | `0.00` to `1.00` (computed derived metric) | Non-unique | Ratio of satisfied mandatory requirements to total mandatory requirements. |
| `created_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Initial record creation timestamp. |
| `updated_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Must be >= `created_at`. |

---

## 3. Policy Entity: `KYCRequirement`
Compliance policy matrix defining required onboarding evidence documents based on customer type and risk tier.

- **Storage Table**: `kyc_requirements`
- **Cardinality**: `N:1` to `customer_types`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `requirement_id` | TEXT (PK) | Required | Pattern: `^REQ-\d{3}$` (e.g., `REQ-001`) | Unique | Primary key identifier for policy rule. |
| `customer_type_code`| TEXT (FK) | Required | Must exist in `customer_types.type_code` | Non-unique | Target legal customer constitution. |
| `risk_tier` | TEXT | Required | `ALL`, `LOW`, `MEDIUM`, `HIGH` | Non-unique | Applicable risk tier for enhanced vs standard due diligence. |
| `document_category` | TEXT | Required | `IDENTITY`, `ADDRESS_PROOF`, `INCORPORATION`, `TAX_CERTIFICATE`, `UBO_DECLARATION`, `FINANCIAL_STATEMENT` | Non-unique | Logical grouping of evidence. |
| `document_type` | TEXT | Required | `PASSPORT`, `DRIVERS_LICENSE`, `NATIONAL_ID`, `UTILITY_BILL`, `BANK_STATEMENT`, `ARTICLES_OF_INCORPORATION`, `CERTIFICATE_OF_INC`, `REGISTER_OF_DIRECTORS`, `W9_W8BEN`, `AUDITED_FINANCIALS` | Non-unique | Specific document type satisfying this requirement. |
| `is_mandatory` | BOOLEAN | Required | `0` (False), `1` (True) | Non-unique | If true, customer cannot be legitimately APPROVED without this evidence. |
| `validity_period_days`| INTEGER | Optional | `30` to `3650` (e.g. 90 days for utility bills, 3650 for passports) | Non-unique | Maximum allowed age of document from issue to onboarding. |

---

## 4. Evidence Entity: `Document`
Physical or digital evidence submitted by or on behalf of a customer.

- **Storage Table**: `documents`
- **Cardinality**: `N:1` to `customers`, `1:N` to `verifications`, `1:N` to `alerts`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `document_id` | TEXT (PK) | Required | Pattern: `^DOC-CUS-\d{6}-\d{3}$` (e.g., `DOC-CUS-000001-001`) | Unique | Immutable, customer-scoped deterministic key. Primary key. |
| `customer_id` | TEXT (FK) | Required | Must exist in `customers.customer_id` | Non-unique | Parent customer who owns this evidence. |
| `document_category` | TEXT | Required | Matches `KYCRequirement.document_category` | Non-unique | Functional category of submitted proof. |
| `document_type` | TEXT | Required | Matches `KYCRequirement.document_type` | Non-unique | Specific type of document submitted. |
| `document_reference_number` | TEXT | Required | Alphanumeric (e.g. `P8920192A`, `REG-2023-9941`) | Unique per doc type (except cross-customer fraud case) | Official serial number printed on document. |
| `issuing_country` | TEXT | Required | ISO 3166-1 alpha-2 (e.g., `US`, `GB`, `DE`) | Non-unique | State or authority that issued the document. |
| `issue_date` | DATE | Required | ISO 8601 `YYYY-MM-DD` | Non-unique | Must be <= `created_at`. |
| `expiry_date` | DATE | Optional | ISO 8601 `YYYY-MM-DD` or `NULL` | Non-unique | If present, must be > `issue_date`. If < system date, document is expired. |
| `document_status` | TEXT | Required | `UPLOADED`, `UNDER_REVIEW`, `VERIFIED`, `REJECTED`, `EXPIRED` | Non-unique | Current document validation lifecycle status. |
| `file_hash_sha256` | TEXT | Required | 64-character hex string | Non-unique | Cryptographic hash of digital evidence file for tamper detection. |
| `created_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Time document was ingested into repository. |

---

## 5. Verification Bridge Entity: `Verification`
Detailed verification audit performed on a document by automated engines or compliance officers.

- **Storage Table**: `verifications`
- **Cardinality**: `N:1` to `documents`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `verification_id`| TEXT (PK) | Required | Pattern: `^VRF-2026-\d{6}$` (e.g., `VRF-2026-000001`) | Unique | Primary key. |
| `document_id` | TEXT (FK) | Required | Must exist in `documents.document_id` | Non-unique | Document evaluated during verification. |
| `verifier_actor`| TEXT | Required | `SYSTEM`, `OPERATIONS_ANALYST`, `COMPLIANCE_OFFICER` | Non-unique | Actor performing the check. |
| `verification_method` | TEXT | Required | `AUTOMATED_OCR`, `BIOMETRIC_LIVENESS`, `MANUAL_DOCUMENT_CHECK`, `GOVERNMENT_REGISTRY_API` | Non-unique | Technique or integration applied. |
| `verification_status` | TEXT | Required | `PASSED`, `FAILED`, `INCONCLUSIVE` | Non-unique | Verification outcome. |
| `discrepancy_notes` | TEXT | Optional | Detailed text or `NULL` if passed | Non-unique | Notes on name mismatch, tampered image, MRZ error. |
| `verified_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Must be >= `document.created_at`. |

---

## 6. Risk Entity: `RiskRating`
Risk evaluation model scoring anti-money laundering and counter-terrorist financing exposure.

- **Storage Table**: `risk_ratings`
- **Cardinality**: `1:1` to `customers`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `risk_id` | TEXT (PK) | Required | Pattern: `^RSK-2026-\d{6}$` (e.g., `RSK-2026-000001`) | Unique | Primary key. |
| `customer_id` | TEXT (FK) | Required | Must exist in `customers.customer_id` | Unique (1:1)| Target customer. |
| `risk_score` | INTEGER | Required | Range `0` to `100` | Non-unique | Composite numerical score derived from factors. |
| `risk_tier` | TEXT | Required | `LOW` (0-39), `MEDIUM` (40-69), `HIGH` (70-100) | Non-unique | Governs periodic review interval and KYC requirement intensity. |
| `sanctions_screening_status` | TEXT | Required | `CLEARED`, `POTENTIAL_MATCH`, `CONFIRMED_HIT` | Non-unique | OFAC/UN/EU sanction screening state. |
| `pep_status` | TEXT | Required | `PEP_CLEAR`, `PEP_DOMESTIC`, `PEP_FOREIGN` | Non-unique | Politically Exposed Person status. |
| `jurisdiction_risk` | TEXT | Required | `STANDARD`, `ELEVATED`, `FATF_GREYLIST`, `SANCTIONED` | Non-unique | Country risk index. |
| `assessed_by` | TEXT | Required | `SYSTEM_ENGINE`, `RISK_ANALYST_01`, `COMPLIANCE_LEAD` | Non-unique | Auditor or automated system. |
| `assessed_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Assessment date. |

---

## 7. Structure Entity: `BeneficialOwner` (UBO)
Captures individual shareholders or key controllers owning or directing business entities.

- **Storage Table**: `beneficial_owners`
- **Cardinality**: `N:1` to `customers` (business entity), `N:1` optional to `customers` (individual)

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `owner_id` | TEXT (PK) | Required | Pattern: `^UBO-2026-\d{6}$` (e.g., `UBO-2026-000001`) | Unique | Primary key. |
| `business_customer_id` | TEXT (FK) | Required | Must exist in `customers.customer_id` | Non-unique | Parent corporate/trust customer. |
| `first_name` | TEXT | Required | String | Non-unique | Given name of individual controller. |
| `last_name` | TEXT | Required | String | Non-unique | Surname of individual controller. |
| `date_of_birth` | DATE | Required | ISO 8601 `YYYY-MM-DD` | Non-unique | Age must be >= 18. |
| `nationality` | TEXT | Required | ISO 3166-1 alpha-2 | Non-unique | Citizenship. |
| `ownership_percentage` | REAL | Required | `0.01` to `100.00` | Non-unique | Direct or indirect equity percentage. |
| `control_type` | TEXT | Required | `DIRECT_SHAREHOLDER`, `INDIRECT_SHAREHOLDER`, `EXECUTIVE_DIRECTOR`, `SENIOR_MANAGING_OFFICIAL` | Non-unique | Form of governance/control. |
| `is_sanctions_screened` | BOOLEAN | Required | `0` (False), `1` (True) | Non-unique | Confirmation of sanctions screening. |
| `created_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Timestamp of ownership declaration. |

---

## 8. Workflow Entity: `ReviewCase`
Governs initial onboarding reviews, ongoing periodic reviews, and event-driven remediation.

- **Storage Table**: `review_cases`
- **Cardinality**: `N:1` to `customers`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `case_id` | TEXT (PK) | Required | Pattern: `^REV-CUS-\d{6}-\d{4}$` (e.g., `REV-CUS-000001-2026`) | Unique | Primary key. Scoped to customer and cycle year. |
| `customer_id` | TEXT (FK) | Required | Must exist in `customers.customer_id` | Non-unique | Customer under review. |
| `review_type` | TEXT | Required | `INITIAL_ONBOARDING`, `PERIODIC_ANNUAL`, `TRIGGER_EVENT`, `REMEDIATION` | Non-unique | Reason for review initiation. |
| `case_status` | TEXT | Required | `OPEN`, `IN_PROGRESS`, `PENDING_CUSTOMER_ACTION`, `ESCALATED`, `APPROVED`, `CLOSED_WITHOUT_RESOLUTION` | Non-unique | Current workflow lifecycle state. |
| `priority` | TEXT | Required | `LOW`, `NORMAL`, `HIGH`, `URGENT` | Non-unique | Operational handling priority. |
| `scheduled_date` | DATE | Required | ISO 8601 `YYYY-MM-DD` | Non-unique | Date case was scheduled to commence. |
| `due_date` | DATE | Required | ISO 8601 `YYYY-MM-DD` | Non-unique | SLA deadline. Must be >= `scheduled_date`. |
| `assigned_analyst`| TEXT | Optional | E.g. `ANALYST_J_DOE`, `ANALYST_K_PATEL` | Non-unique | Assigned investigator. |
| `resolved_at` | TIMESTAMP| Optional | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` or `NULL` | Non-unique | Completion timestamp. Must be >= case creation. |
| `resolution_outcome` | TEXT | Optional | `APPROVED`, `RESTRICTED`, `OFFBOARDED`, `UNRESOLVED` | Non-unique | Final decision. `APPROVED` requires completeness. |
| `created_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Record creation timestamp. |

---

## 9. Surveillance Entity: `Alert`
Operational alerts for expiring evidence, overdue reviews, and compliance anomalies.

- **Storage Table**: `alerts`
- **Cardinality**: `N:1` to `customers`, `N:1` optional to `documents`

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `alert_id` | TEXT (PK) | Required | Pattern: `^ALT-2026-\d{6}$` (e.g., `ALT-2026-000001`) | Unique | Primary key. |
| `customer_id` | TEXT (FK) | Required | Must exist in `customers.customer_id` | Non-unique | Customer linked to alert. |
| `document_id` | TEXT (FK) | Optional | Must exist in `documents.document_id` or `NULL` | Non-unique | Document linked to expiration alert. |
| `alert_type` | TEXT | Required | `DOCUMENT_EXPIRING_SOON`, `DOCUMENT_EXPIRED`, `PERIODIC_REVIEW_OVERDUE`, `UBO_THRESHOLD_DEFICIT`, `VERIFICATION_FAILED` | Non-unique | Reason for triggering alert. |
| `lead_time_days` | INTEGER | Required | `-365` to `90` (e.g., 90, 60, 30, 0, or negative if overdue) | Non-unique | Days remaining until expiration / days overdue. |
| `severity` | TEXT | Required | `INFO`, `WARNING`, `HIGH`, `CRITICAL` | Non-unique | Priority tier for remediation. |
| `alert_status` | TEXT | Required | `NEW`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED` | Non-unique | Operational resolution status. |
| `created_at` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Alert generation timestamp. |
| `acknowledged_at`| TIMESTAMP| Optional | ISO 8601 or `NULL` | Non-unique | Timestamp an analyst opened the alert. |

---

## 10. Audit Trail Entity: `AuditEvent`
Immutable log of all lifecycle events, state transitions, approvals, and anomalies.

- **Storage Table**: `audit_events`
- **Cardinality**: Immutable log; references all core entities

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | TEXT (PK) | Required | Pattern: `^AUD-2026-\d{6}$` (e.g., `AUD-2026-000001`) | Unique | Monotonically incrementing event ID. Primary key. |
| `entity_type` | TEXT | Required | `CUSTOMER`, `DOCUMENT`, `VERIFICATION`, `RISK_RATING`, `BENEFICIAL_OWNER`, `REVIEW_CASE`, `ALERT` | Non-unique | Target entity table. |
| `entity_id` | TEXT | Required | Valid ID of referenced entity | Non-unique | Primary key of target entity. |
| `actor_role` | TEXT | Required | `CUSTOMER`, `OPERATIONS_ANALYST`, `RISK_COMPLIANCE_REVIEWER`, `SYSTEM_ADMIN` | Non-unique | Role executing the mutation. |
| `actor_id` | TEXT | Required | User identifier (e.g. `SYS_SCHEDULER`, `USR_ANALYST_42`) | Non-unique | Specific actor ID. |
| `event_type` | TEXT | Required | `CREATED`, `STATUS_CHANGED`, `VERIFICATION_COMPLETED`, `EXPIRY_FLAGGED`, `ALERT_GENERATED`, `ANOMALY_DETECTED` | Non-unique | Lifecycle action taken. |
| `old_state` | TEXT | Optional | String or `NULL` | Non-unique | Prior state before change. |
| `new_state` | TEXT | Required | String | Non-unique | Updated state after change. |
| `change_reason` | TEXT | Required | Descriptive explanation | Non-unique | Compliance audit justification. |
| `timestamp` | TIMESTAMP| Required | ISO 8601 `YYYY-MM-DDTHH:MM:SSZ` | Non-unique | Exact clock time of occurrence. |

---

## 11. Ground Truth Anomaly Manifest: `GroundTruth`
Isolated validation reference storing deliberate anomalies injected for evaluation.

- **Storage Table**: `ground_truth` (and exported separately to `ground_truth.csv` and `ground_truth.json`)
- **Isolation Rule**: **Must never be joined or leaked into input features or operational decision models.**

| Field Name | Type | Req/Opt | Allowed Values / Format | Uniqueness | Validation Rule & Business Meaning |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `anomaly_id` | TEXT (PK) | Required | Pattern: `^ANO-\d{6}$` (e.g., `ANO-000001`) | Unique | Unique identifier for the anomaly. |
| `anomaly_type` | TEXT | Required | One of the 5 required negative scenarios: `EXPIRED_DOC_MARKED_VALID`, `APPROVED_WITHOUT_MANDATORY_EVIDENCE`, `UBO_PERCENTAGE_EXCEEDS_100`, `REVIEW_CLOSED_WITHOUT_RESOLUTION`, `DUPLICATE_DOCUMENT_CROSS_CUSTOMER` | Non-unique | Categorical defect classification. |
| `entity_type` | TEXT | Required | `DOCUMENT`, `CUSTOMER`, `BENEFICIAL_OWNER`, `REVIEW_CASE` | Non-unique | The corrupted entity type. |
| `primary_entity_id`| TEXT | Required | Valid entity ID | Non-unique | Primary target ID where anomaly exists. |
| `secondary_entity_id`| TEXT | Optional | Valid entity ID or `NULL` | Non-unique | Related ID (e.g. duplicate document holder). |
| `description` | TEXT | Required | Plain English description of the defect | Non-unique | Detailed description of the injected flaw. |
| `severity` | TEXT | Required | `CRITICAL`, `HIGH`, `MEDIUM` | Non-unique | Risk rating of the compliance breach. |
| `expected_rule_violation` | TEXT | Required | E.g. `RULE_DOC_EXPIRY_INTEGRITY`, `RULE_ONBOARDING_COMPLETENESS_GATE`, `RULE_UBO_SUM_CONSTRAINT`, `RULE_REVIEW_OUTCOME_RESOLUTION`, `RULE_DOC_GLOBAL_UNIQUENESS` | Non-unique | Formal validation rule identifier. |
