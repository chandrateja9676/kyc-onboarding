"""
Data models and schema definitions for the KYC Onboarding & Lifecycle Evidence System.
Provides strongly typed dataclasses, serialization methods, and SQL table schemas.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

# Anchor date used throughout the simulation
SIMULATION_ANCHOR_DATE = "2026-10-26"


@dataclass
class CustomerType:
    type_code: str
    type_name: str
    description: str
    is_business_entity: bool
    min_ubo_threshold: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Customer:
    customer_id: str
    customer_type_code: str
    legal_name: str
    trade_name: Optional[str]
    tax_id: str
    jurisdiction: str
    date_of_birth_or_inc: str
    onboarding_status: str
    completeness_score: float
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KYCRequirement:
    requirement_id: str
    customer_type_code: str
    risk_tier: str
    document_category: str
    document_type: str
    is_mandatory: bool
    validity_period_days: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    document_id: str
    customer_id: str
    document_category: str
    document_type: str
    document_reference_number: str
    issuing_country: str
    issue_date: str
    expiry_date: Optional[str]
    document_status: str
    file_hash_sha256: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Verification:
    verification_id: str
    document_id: str
    verifier_actor: str
    verification_method: str
    verification_status: str
    discrepancy_notes: Optional[str]
    verified_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskRating:
    risk_id: str
    customer_id: str
    risk_score: int
    risk_tier: str
    rationale: str
    sanctions_screening_status: str
    pep_status: str
    jurisdiction_risk: str
    assessed_by: str
    assessed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BeneficialOwner:
    owner_id: str
    business_customer_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    nationality: str
    ownership_percentage: float
    control_type: str
    is_sanctions_screened: bool
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewCase:
    case_id: str
    customer_id: str
    review_type: str
    case_status: str
    priority: str
    scheduled_date: str
    due_date: str
    assigned_analyst: Optional[str]
    resolved_at: Optional[str]
    resolution_outcome: Optional[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Alert:
    alert_id: str
    customer_id: str
    document_id: Optional[str]
    alert_type: str
    lead_time_days: int
    severity: str
    alert_status: str
    created_at: str
    acknowledged_at: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEvent:
    event_id: str
    entity_type: str
    entity_id: str
    actor_role: str
    actor_id: str
    event_type: str
    old_state: Optional[str]
    new_state: str
    change_reason: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundTruthAnomaly:
    anomaly_id: str
    anomaly_type: str
    entity_type: str
    primary_entity_id: str
    secondary_entity_id: Optional[str]
    description: str
    severity: str
    expected_rule_violation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# SQL Schema definition for SQLite
SQL_SCHEMA = """
-- Master table: Customer Types
CREATE TABLE IF NOT EXISTS customer_types (
    type_code TEXT PRIMARY KEY,
    type_name TEXT NOT NULL,
    description TEXT NOT NULL,
    is_business_entity INTEGER NOT NULL,
    min_ubo_threshold REAL NOT NULL
);

-- Master table: KYC Requirements Policy Matrix
CREATE TABLE IF NOT EXISTS kyc_requirements (
    requirement_id TEXT PRIMARY KEY,
    customer_type_code TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    document_category TEXT NOT NULL,
    document_type TEXT NOT NULL,
    is_mandatory INTEGER NOT NULL,
    validity_period_days INTEGER,
    FOREIGN KEY (customer_type_code) REFERENCES customer_types(type_code)
);

-- Master/Core table: Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    customer_type_code TEXT NOT NULL,
    legal_name TEXT NOT NULL,
    trade_name TEXT,
    tax_id TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    date_of_birth_or_inc TEXT NOT NULL,
    onboarding_status TEXT NOT NULL,
    completeness_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (customer_type_code) REFERENCES customer_types(type_code)
);

-- Child table: Documents
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    document_category TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_reference_number TEXT NOT NULL,
    issuing_country TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    expiry_date TEXT,
    document_status TEXT NOT NULL,
    file_hash_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Child/Bridge table: Verifications
CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    verifier_actor TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    discrepancy_notes TEXT,
    verified_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

-- Child table: Risk Ratings
CREATE TABLE IF NOT EXISTS risk_ratings (
    risk_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    risk_score INTEGER NOT NULL,
    risk_tier TEXT NOT NULL,
    rationale TEXT NOT NULL,
    sanctions_screening_status TEXT NOT NULL,
    pep_status TEXT NOT NULL,
    jurisdiction_risk TEXT NOT NULL,
    assessed_by TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Child/Bridge table: Beneficial Owners (UBO)
CREATE TABLE IF NOT EXISTS beneficial_owners (
    owner_id TEXT PRIMARY KEY,
    business_customer_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    nationality TEXT NOT NULL,
    ownership_percentage REAL NOT NULL,
    control_type TEXT NOT NULL,
    is_sanctions_screened INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (business_customer_id) REFERENCES customers(customer_id)
);

-- Lifecycle table: Review Cases
CREATE TABLE IF NOT EXISTS review_cases (
    case_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    review_type TEXT NOT NULL,
    case_status TEXT NOT NULL,
    priority TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    assigned_analyst TEXT,
    resolved_at TEXT,
    resolution_outcome TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Surveillance table: Alerts
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    document_id TEXT,
    alert_type TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL,
    severity TEXT NOT NULL,
    alert_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

-- Event store: Audit Events (Immutable)
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_state TEXT,
    new_state TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- Isolated ground truth table (not joined in production scoring)
CREATE TABLE IF NOT EXISTS ground_truth (
    anomaly_id TEXT PRIMARY KEY,
    anomaly_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    primary_entity_id TEXT NOT NULL,
    secondary_entity_id TEXT,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    expected_rule_violation TEXT NOT NULL
);

-- Performance and Integrity Indexes
CREATE INDEX IF NOT EXISTS idx_customers_type ON customers(customer_type_code);
CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(onboarding_status);
CREATE INDEX IF NOT EXISTS idx_documents_customer ON documents(customer_id);
CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_verifications_doc ON verifications(document_id);
CREATE INDEX IF NOT EXISTS idx_review_cases_cust ON review_cases(customer_id);
CREATE INDEX IF NOT EXISTS idx_review_cases_status ON review_cases(case_status);
CREATE INDEX IF NOT EXISTS idx_alerts_cust ON alerts(customer_id);
CREATE INDEX IF NOT EXISTS idx_ubo_biz ON beneficial_owners(business_customer_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);
"""
