# Source Manifest & Lawful Provenance Statement

This document details the data provenance, regulatory citation sources, generation methodology, and legal compliance safeguards utilized in the **KYC Onboarding & Evidence Lifecycle Platform**.

---

## 1. Provenance & Privacy Guarantee (Zero PII Policy)

> [!IMPORTANT]
> **No Actual Personally Identifiable Information (PII) or Non-Public Financial Records were collected, scraped, ingested, or stored in this repository.**
> 
> All customer identities, corporate registrations, passport numbers, tax IDs, and transaction/verification timestamps are **100% synthetically generated** using deterministic pseudo-random mathematical generation algorithms seeded with PRNG seed `20261022`.

- **GDPR (Regulation EU 2016/679)**: Full compliance. Because no personal data relating to an identified or identifiable natural person is processed, the dataset is outside the scope of GDPR Article 2.
- **Gramm-Leach-Bliley Act (GLBA)**: Zero nonpublic personal information (NPI) of financial consumers is accessed.
- **California Consumer Privacy Act (CCPA/CPRA)**: Zero consumer personal records collected.

---

## 2. Regulatory Reference Standards (Schema Inspiration)

The relational schema, requirement matrix, and lifecycle state machines were inspired by the following public statutory frameworks:

1. **FATF Recommendations (Financial Action Task Force)**
   - *Topic*: International Standards on Combating Money Laundering and the Financing of Terrorism & Proliferation.
   - *Reference*: FATF Recommendation 10 (Customer Due Diligence), Recommendation 24 & 25 (Transparency and Beneficial Ownership of Legal Persons and Legal Arrangements).
   - *URL*: [https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html)
   - *Terms/License*: Publicly published international guidance; cited strictly for conceptual schema design.

2. **FinCEN Customer Due Diligence (CDD) Final Rule (31 CFR § 1010.230)**
   - *Topic*: Requirement for covered financial institutions to identify and verify the identity of beneficial owners of legal entity customers.
   - *Standard*: 25% equity ownership threshold, single individual with significant responsibility to control.
   - *URL*: [https://www.fincen.gov/resources/statutes-regulations/cdd-final-rule](https://www.fincen.gov/resources/statutes-regulations/cdd-final-rule)

3. **Directive (EU) 2018/843 (5th Anti-Money Laundering Directive - 5AMLD)**
   - *Topic*: Beneficial ownership register verification, enhanced due diligence for high-risk third countries.
   - *Standard*: Central registers for corporate and other legal entities, trusts, and fiduciary agreements.

4. **ICAO Document 9303 (Machine Readable Travel Documents)**
   - *Topic*: Machine Readable Zone (MRZ) formats and alphanumeric serial conventions used to inspire document reference codes.

---

## 3. Synthetic Data Generation Architecture

- **Random Number Generation**: Python `random.Random` initialized with a static seed (default: `20261022`).
- **Cryptographic Hashes**: SHA-256 digests (`hashlib.sha256`) generated over compound entity keys (`document_id:ref_num:customer_id`).
- **Nomenclature Conventions**:
  - Customers: `CUS-000001` through `CUS-008000`
  - Documents: `DOC-<customer-id>-001` through `DOC-<customer-id>-999`
  - Verifications: `VRF-2026-000001` onward
  - Risk Assessments: `RSK-2026-000001` onward
  - Beneficial Owners: `UBO-2026-000001` onward
  - Review Cases: `REV-<customer-id>-2026`
  - Alerts: `ALT-2026-000001` onward
  - Audit Trail: `AUD-2026-000001` onward
  - Ground Truth Anomalies: `ANO-000001` onward
- **Ground Truth Isolation**: The ground truth dataset (`ground_truth.csv`, `ground_truth.json`, and table `ground_truth`) is kept completely isolated from operational feature pipelines.
