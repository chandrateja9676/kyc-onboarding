"""
Business logic and compliance policy rules for the KYC Lifecycle & Onboarding Evidence System.
Defines requirement matrices, completeness scoring, expiration triggers, periodic review schedules,
and validation assertions.
"""

from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
from src.models import (
    CustomerType,
    KYCRequirement,
    Customer,
    Document,
    RiskRating,
    BeneficialOwner,
    ReviewCase,
    SIMULATION_ANCHOR_DATE,
)

# Reference anchor date
ANCHOR_DATE = datetime.strptime(SIMULATION_ANCHOR_DATE, "%Y-%m-%d").date()


def get_default_customer_types() -> List[CustomerType]:
    """Returns the statutory master customer types."""
    return [
        CustomerType(
            type_code="INDIVIDUAL",
            type_name="Individual / Natural Person",
            description="Natural person retail or private banking customer",
            is_business_entity=False,
            min_ubo_threshold=0.0,
        ),
        CustomerType(
            type_code="CORPORATE",
            type_name="Corporation / Limited Liability Company",
            description="Commercial corporate entity requiring UBO disclosure",
            is_business_entity=True,
            min_ubo_threshold=0.25,
        ),
        CustomerType(
            type_code="TRUST",
            type_name="Trust / Fiduciary Structure",
            description="Fiduciary vehicle requiring trustee, settlor, and beneficiary registry",
            is_business_entity=True,
            min_ubo_threshold=0.10,
        ),
        CustomerType(
            type_code="PARTNERSHIP",
            type_name="General or Limited Partnership",
            description="Commercial partnership requiring general and limited partner disclosure",
            is_business_entity=True,
            min_ubo_threshold=0.25,
        ),
    ]


def get_default_kyc_requirements() -> List[KYCRequirement]:
    """Returns the regulatory policy requirement matrix."""
    return [
        # INDIVIDUAL REQUIREMENTS
        KYCRequirement(
            requirement_id="REQ-IND-001",
            customer_type_code="INDIVIDUAL",
            risk_tier="ALL",
            document_category="IDENTITY",
            document_type="PASSPORT",
            is_mandatory=True,
            validity_period_days=3650,
        ),
        KYCRequirement(
            requirement_id="REQ-IND-002",
            customer_type_code="INDIVIDUAL",
            risk_tier="ALL",
            document_category="ADDRESS_PROOF",
            document_type="UTILITY_BILL",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-IND-003",
            customer_type_code="INDIVIDUAL",
            risk_tier="HIGH",
            document_category="TAX_CERTIFICATE",
            document_type="W9_W8BEN",
            is_mandatory=True,
            validity_period_days=1095,
        ),

        # CORPORATE REQUIREMENTS
        KYCRequirement(
            requirement_id="REQ-CORP-001",
            customer_type_code="CORPORATE",
            risk_tier="ALL",
            document_category="INCORPORATION",
            document_type="CERTIFICATE_OF_INC",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-CORP-002",
            customer_type_code="CORPORATE",
            risk_tier="ALL",
            document_category="ADDRESS_PROOF",
            document_type="BANK_STATEMENT",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-CORP-003",
            customer_type_code="CORPORATE",
            risk_tier="ALL",
            document_category="UBO_DECLARATION",
            document_type="REGISTER_OF_DIRECTORS",
            is_mandatory=True,
            validity_period_days=365,
        ),
        KYCRequirement(
            requirement_id="REQ-CORP-004",
            customer_type_code="CORPORATE",
            risk_tier="ALL",
            document_category="TAX_CERTIFICATE",
            document_type="W9_W8BEN",
            is_mandatory=True,
            validity_period_days=1095,
        ),
        KYCRequirement(
            requirement_id="REQ-CORP-005",
            customer_type_code="CORPORATE",
            risk_tier="HIGH",
            document_category="FINANCIAL_STATEMENT",
            document_type="AUDITED_FINANCIALS",
            is_mandatory=True,
            validity_period_days=365,
        ),

        # TRUST REQUIREMENTS
        KYCRequirement(
            requirement_id="REQ-TRST-001",
            customer_type_code="TRUST",
            risk_tier="ALL",
            document_category="INCORPORATION",
            document_type="TRUST_DEED",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-TRST-002",
            customer_type_code="TRUST",
            risk_tier="ALL",
            document_category="ADDRESS_PROOF",
            document_type="BANK_STATEMENT",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-TRST-003",
            customer_type_code="TRUST",
            risk_tier="ALL",
            document_category="UBO_DECLARATION",
            document_type="REGISTER_OF_BENEFICIARIES",
            is_mandatory=True,
            validity_period_days=365,
        ),

        # PARTNERSHIP REQUIREMENTS
        KYCRequirement(
            requirement_id="REQ-PRTN-001",
            customer_type_code="PARTNERSHIP",
            risk_tier="ALL",
            document_category="INCORPORATION",
            document_type="PARTNERSHIP_AGREEMENT",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-PRTN-002",
            customer_type_code="PARTNERSHIP",
            risk_tier="ALL",
            document_category="ADDRESS_PROOF",
            document_type="UTILITY_BILL",
            is_mandatory=True,
            validity_period_days=None,
        ),
        KYCRequirement(
            requirement_id="REQ-PRTN-003",
            customer_type_code="PARTNERSHIP",
            risk_tier="ALL",
            document_category="UBO_DECLARATION",
            document_type="REGISTER_OF_PARTNERS",
            is_mandatory=True,
            validity_period_days=365,
        ),
    ]


def get_mandatory_requirements_for_customer(
    customer_type_code: str, risk_tier: str, requirements: List[KYCRequirement]
) -> List[KYCRequirement]:
    """Finds all mandatory requirements applicable to a specific customer profile."""
    matched = []
    for req in requirements:
        if req.customer_type_code == customer_type_code and req.is_mandatory:
            if req.risk_tier == "ALL" or req.risk_tier == risk_tier:
                matched.append(req)
    return matched


def calculate_customer_completeness(
    customer: Customer,
    customer_risk_tier: str,
    documents: List[Document],
    requirements: List[KYCRequirement],
    anchor_date: Optional[date] = None,
) -> Tuple[float, List[str], List[str]]:
    """
    Calculates derived completeness score.
    Returns:
        (completeness_score, satisfied_categories, missing_categories)
    """
    if anchor_date is None:
        anchor_date = ANCHOR_DATE

    mandatory_reqs = get_mandatory_requirements_for_customer(
        customer.customer_type_code, customer_risk_tier, requirements
    )
    if not mandatory_reqs:
        return 1.0, [], []

    # Map categories present in verified, non-expired documents
    valid_categories = set()
    for doc in documents:
        if doc.customer_id != customer.customer_id:
            continue
        if doc.document_status == "VERIFIED":
            if doc.expiry_date:
                doc_exp = datetime.strptime(doc.expiry_date, "%Y-%m-%d").date()
                if doc_exp <= anchor_date:
                    continue  # Expired documents do not satisfy requirement
            valid_categories.add(doc.document_category)

    satisfied = []
    missing = []
    for req in mandatory_reqs:
        if req.document_category in valid_categories:
            satisfied.append(req.document_category)
        else:
            missing.append(req.document_category)

    score = round(len(satisfied) / len(mandatory_reqs), 4)
    return score, satisfied, missing


def get_periodic_review_interval_days(risk_tier: str) -> int:
    """Returns statutory review frequency in days."""
    if risk_tier == "HIGH":
        return 365    # 1 year
    elif risk_tier == "MEDIUM":
        return 730   # 2 years
    else:
        return 1095  # 3 years


def evaluate_document_expiry_alert(
    doc: Document, anchor_date: Optional[date] = None
) -> Optional[Tuple[str, int, str]]:
    """
    Evaluates expiration status of a document.
    Returns:
        (alert_type, lead_time_days, severity) or None
    """
    if not doc.expiry_date:
        return None

    if anchor_date is None:
        anchor_date = ANCHOR_DATE

    exp_date = datetime.strptime(doc.expiry_date, "%Y-%m-%d").date()
    delta_days = (exp_date - anchor_date).days

    if delta_days < 0:
        return ("DOCUMENT_EXPIRED", delta_days, "CRITICAL")
    elif 0 <= delta_days <= 30:
        return ("DOCUMENT_EXPIRING_SOON", delta_days, "HIGH")
    elif 31 <= delta_days <= 60:
        return ("DOCUMENT_EXPIRING_SOON", delta_days, "WARNING")
    elif 61 <= delta_days <= 90:
        return ("DOCUMENT_EXPIRING_SOON", delta_days, "INFO")
    else:
        return None
