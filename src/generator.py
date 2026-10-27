"""
Deterministic synthetic data generator for KYC Lifecycle & Onboarding Evidence Tracking.
Supports starter, standard, and full baseline scale (8,000 customers, 20,000 documents,
1,000 business entities, 3,000 review cases) with fixed seed and separate ground truth.
"""

import random
import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional

from src.models import (
    CustomerType,
    Customer,
    KYCRequirement,
    Document,
    Verification,
    RiskRating,
    BeneficialOwner,
    ReviewCase,
    Alert,
    AuditEvent,
    GroundTruthAnomaly,
    SIMULATION_ANCHOR_DATE,
)
from src.rules import (
    ANCHOR_DATE,
    get_default_customer_types,
    get_default_kyc_requirements,
    get_mandatory_requirements_for_customer,
    calculate_customer_completeness,
    get_periodic_review_interval_days,
    evaluate_document_expiry_alert,
)

# Realistic pool of names and corporate entities for high data realism
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Margaret", "Anthony", "Betty", "Donald", "Sandra", "Mark", "Ashley",
    "Paul", "Dorothy", "Steven", "Kimberly", "Andrew", "Emily", "Kenneth", "Donna",
    "Joshua", "Michelle", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Shirley", "Eric", "Angela", "Jonathan", "Helen", "Stephen", "Anna",
    "Larry", "Brenda", "Justin", "Pamela", "Scott", "Nicole", "Brandon", "Emma",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Gregory", "Christine", "Alexander", "Debra",
    "Frank", "Rachel", "Patrick", "Catherine", "Raymond", "Carolyn", "Jack", "Janet",
    "Dennis", "Ruth", "Jerry", "Maria", "Tyler", "Heather", "Aaron", "Diane",
    "Jose", "Virginia", "Adam", "Julie", "Henry", "Joyce", "Nathan", "Victoria",
    "Douglas", "Olivia", "Zachary", "Kelly", "Peter", "Christina", "Kyle", "Lauren",
    "Walter", "Joan", "Ethan", "Evelyn", "Jeremy", "Judith", "Harold", "Megan",
    "Keith", "Cheryl", "Christian", "Andrea", "Roger", "Hannah", "Noah", "Martha",
    "Gerald", "Jacqueline", "Carl", "Frances", "Terry", "Ann", "Sean", "Gloria",
    "Austin", "Jean", "Arthur", "Kathryn", "Lawrence", "Alice", "Jesse", "Teresa",
    "Dylan", "Sara", "Bryan", "Janice", "Joe", "Doris", "Jordan", "Madison",
    "Billy", "Julia", "Albert", "Grace", "Bruce", "Judy", "Willie", "Abigail",
    "Gabriel", "Marie", "Logan", "Denise", "Alan", "Beverly", "Juan", "Amber",
    "Wayne", "Theresa", "Roy", "Marilyn", "Ralph", "Danielle", "Randy", "Diana",
    "Eugene", "Brittany", "Vincent", "Natalie", "Russell", "Sophia", "Louis", "Rose",
    "Philip", "Isabella", "Bobby", "Alexis", "Johnny", "Kayla", "Bradley", "Charlotte"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Mendoza", "Gray",
    "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long",
    "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry", "Russell", "Sullivan",
    "Bell", "Coleman", "Butler", "Henderson", "Barnes", "Gonzales", "Fisher", "Vasquez",
    "Simmons", "Romero", "Jordan", "Patterson", "Alexander", "Hamilton", "Graham", "Reynolds",
    "Griffin", "Wallace", "Moreno", "West", "Cole", "Hayes", "Bryant", "Herrera",
    "Gibson", "Ellis", "Tran", "Medina", "Aguilar", "Stevens", "Murray", "Ford",
    "Castro", "Marshall", "Owens", "Harrison", "Fernandez", "McDonald", "Woods", "Washington",
    "Kennedy", "Wells", "Vargas", "Henry", "Chen", "Freeman", "Webb", "Tucker",
    "Guzman", "Burns", "Crawford", "Olson", "Simpson", "Porter", "Hunter", "Gordon"
]

CORPORATE_PREFIXES = [
    "Apex", "Nexus", "Vanguard", "Horizon", "Pinnacle", "Aegis", "Sterling", "Summit",
    "Cascade", "Crestview", "Beacon", "Zenith", "Meridian", "Solstice", "Paramount", "Atlas",
    "Quantum", "Trident", "Novus", "Synergy", "Astra", "Keystone", "Falcon", "Helios",
    "Fortress", "Pacific", "Atlantic", "Omega", "Olympus", "Frontier", "Vertex", "Polaris"
]

CORPORATE_SUFFIXES = [
    "Capital Management", "Technologies Inc", "Holdings LLC", "Global Logistics",
    "Consulting Group", "Asset Partners", "Financial Services", "Energy Systems",
    "Ventures LP", "Industrial Corp", "Security Solutions", "Digital Health",
    "Trading Partners", "BioPharma LLC", "Real Estate Trust", "International Ltd"
]

JURISDICTIONS = [
    ("US", 0.40, "STANDARD"),
    ("GB", 0.20, "STANDARD"),
    ("DE", 0.10, "STANDARD"),
    ("SG", 0.10, "STANDARD"),
    ("CH", 0.05, "STANDARD"),
    ("CY", 0.05, "ELEVATED"),
    ("KY", 0.04, "ELEVATED"),
    ("PA", 0.03, "FATF_GREYLIST"),
    ("AE", 0.03, "FATF_GREYLIST"),
]

ANALYST_POOL = ["ANALYST_J_DOE", "ANALYST_K_PATEL", "ANALYST_S_CHEN", "ANALYST_M_GARCIA", "ANALYST_A_VOGEL"]
VERIFIER_ACTORS = ["SYSTEM", "OPERATIONS_ANALYST", "COMPLIANCE_OFFICER"]


class KYCDataGenerator:
    """
    Engine to generate synthetic datasets matching all distribution, integrity,
    and ground truth injection specifications.
    """

    def __init__(self, seed: int = 20261022, scale_profile: str = "full"):
        self.seed = seed
        self.scale_profile = scale_profile
        self.rng = random.Random(seed)

        # Scale parameters
        if scale_profile == "starter":
            self.target_customers = 400
            self.target_business_entities = 60
            self.target_documents = 1000
            self.target_review_cases = 150
            self.target_anomalies_per_type = 3
        elif scale_profile == "standard":
            self.target_customers = 2000
            self.target_business_entities = 300
            self.target_documents = 5000
            self.target_review_cases = 800
            self.target_anomalies_per_type = 6
        elif scale_profile == "full":
            self.target_customers = 8000
            self.target_business_entities = 1000
            self.target_documents = 20000
            self.target_review_cases = 3000
            self.target_anomalies_per_type = 12
        else:
            raise ValueError(f"Unknown scale profile: {scale_profile}")

        # In-memory storage for entities
        self.customer_types: List[CustomerType] = []
        self.kyc_requirements: List[KYCRequirement] = []
        self.customers: List[Customer] = []
        self.documents: List[Document] = []
        self.verifications: List[Verification] = []
        self.risk_ratings: List[RiskRating] = []
        self.beneficial_owners: List[BeneficialOwner] = []
        self.review_cases: List[ReviewCase] = []
        self.alerts: List[Alert] = []
        self.audit_events: List[AuditEvent] = []
        self.ground_truth: List[GroundTruthAnomaly] = []

        # Counters for deterministic IDs
        self.vrf_counter = 0
        self.rsk_counter = 0
        self.ubo_counter = 0
        self.alt_counter = 0
        self.aud_counter = 0
        self.ano_counter = 0

    def _next_vrf_id(self) -> str:
        self.vrf_counter += 1
        return f"VRF-2026-{self.vrf_counter:06d}"

    def _next_rsk_id(self) -> str:
        self.rsk_counter += 1
        return f"RSK-2026-{self.rsk_counter:06d}"

    def _next_ubo_id(self) -> str:
        self.ubo_counter += 1
        return f"UBO-2026-{self.ubo_counter:06d}"

    def _next_alt_id(self) -> str:
        self.alt_counter += 1
        return f"ALT-2026-{self.alt_counter:06d}"

    def _next_aud_id(self) -> str:
        self.aud_counter += 1
        return f"AUD-2026-{self.aud_counter:06d}"

    def _next_ano_id(self) -> str:
        self.ano_counter += 1
        return f"ANO-{self.ano_counter:06d}"

    def _pick_jurisdiction(self) -> Tuple[str, str]:
        r = self.rng.random()
        cumulative = 0.0
        for code, weight, risk in JURISDICTIONS:
            cumulative += weight
            if r <= cumulative:
                return code, risk
        return JURISDICTIONS[0][0], JURISDICTIONS[0][2]

    def _random_date(self, start_date: date, end_date: date) -> date:
        delta = (end_date - start_date).days
        if delta <= 0:
            return start_date
        random_days = self.rng.randint(0, delta)
        return start_date + timedelta(days=random_days)

    def _generate_sha256(self, payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate_all(self):
        """Orchestrates parent-first generation, derived calculation, and anomaly injection."""
        # 1. Master tables
        self.customer_types = get_default_customer_types()
        self.kyc_requirements = get_default_kyc_requirements()

        # 2. Customers
        self._generate_customers()

        # 3. Risk Ratings
        self._generate_risk_ratings()

        # 4. Beneficial Owners for business entities
        self._generate_beneficial_owners()

        # 5. Baseline Documents & Verifications
        self._generate_documents_and_verifications()

        # 6. Inject the 5 mandatory edge cases (strictly labelled in ground truth)
        self._inject_mandatory_edge_cases()

        # 7. Derive Customer Completeness scores from actual source records
        self._calculate_derived_completeness()

        # 8. Generate Periodic Reviews based on customer risk tier and approval date
        self._generate_review_cases()

        # 9. Derive Expiry & Overdue Alerts
        self._generate_alerts()

        # 10. Generate Audit Trail Events
        self._generate_audit_events()

    def _generate_customers(self):
        """Generates synthetic customer master records."""
        biz_target = min(self.target_business_entities, self.target_customers)
        biz_indices = set(self.rng.sample(range(1, self.target_customers + 1), biz_target))

        for i in range(1, self.target_customers + 1):
            customer_id = f"CUS-{i:06d}"
            
            # Determine if business or individual
            if i in biz_indices:
                biz_type = self.rng.choice(["CORPORATE", "CORPORATE", "CORPORATE", "TRUST", "PARTNERSHIP"])
                customer_type_code = biz_type
                prefix = self.rng.choice(CORPORATE_PREFIXES)
                suffix = self.rng.choice(CORPORATE_SUFFIXES)
                legal_name = f"{prefix} {suffix}"
                trade_name = f"{prefix} Commercial" if self.rng.random() < 0.4 else None
                dob_or_inc = self._random_date(date(2000, 1, 1), date(2025, 6, 1)).isoformat()
            else:
                customer_type_code = "INDIVIDUAL"
                first_name = self.rng.choice(FIRST_NAMES)
                last_name = self.rng.choice(LAST_NAMES)
                legal_name = f"{first_name} {last_name}"
                trade_name = None
                dob_or_inc = self._random_date(date(1950, 1, 1), date(2006, 1, 1)).isoformat()

            jurisdiction, _ = self._pick_jurisdiction()
            tax_num = self.rng.randint(10000000, 99999999)
            tax_id = f"{jurisdiction}-TX-{tax_num}"

            # Initial status: majority approved, some in review, pending, rejected, suspended
            r_status = self.rng.random()
            if r_status < 0.70:
                onboarding_status = "APPROVED"
            elif r_status < 0.85:
                onboarding_status = "IN_REVIEW"
            elif r_status < 0.93:
                onboarding_status = "PENDING"
            elif r_status < 0.97:
                onboarding_status = "SUSPENDED"
            else:
                onboarding_status = "REJECTED"

            # Creation date between 2023-01-01 and 2026-09-01
            created_dt = self._random_date(date(2023, 1, 1), date(2026, 9, 1))
            created_at = f"{created_dt.isoformat()}T09:00:00Z"
            updated_at = f"{(created_dt + timedelta(days=self.rng.randint(1, 30))).isoformat()}T14:30:00Z"

            customer = Customer(
                customer_id=customer_id,
                customer_type_code=customer_type_code,
                legal_name=legal_name,
                trade_name=trade_name,
                tax_id=tax_id,
                jurisdiction=jurisdiction,
                date_of_birth_or_inc=dob_or_inc,
                onboarding_status=onboarding_status,
                completeness_score=0.0,  # Will be derived in step 7
                created_at=created_at,
                updated_at=updated_at,
            )
            self.customers.append(customer)

    def _generate_risk_ratings(self):
        """Generates 1:1 risk rating evaluation for every customer."""
        for cust in self.customers:
            risk_id = self._next_rsk_id()
            _, _, juris_risk = next((j for j in JURISDICTIONS if j[0] == cust.jurisdiction), ("US", 0.40, "STANDARD"))

            # Risk score calculation
            base_score = self.rng.randint(10, 45)
            if juris_risk == "FATF_GREYLIST":
                base_score += 35
            elif juris_risk == "ELEVATED":
                base_score += 15

            if cust.customer_type_code in ["CORPORATE", "TRUST"]:
                base_score += 10

            # Screening statuses
            r_pep = self.rng.random()
            if r_pep < 0.02:
                pep_status = "PEP_FOREIGN"
                base_score += 30
            elif r_pep < 0.05:
                pep_status = "PEP_DOMESTIC"
                base_score += 15
            else:
                pep_status = "PEP_CLEAR"

            r_sanc = self.rng.random()
            if r_sanc < 0.005:
                sanctions_status = "CONFIRMED_HIT"
                base_score = 100
                cust.onboarding_status = "REJECTED"
            elif r_sanc < 0.02:
                sanctions_status = "POTENTIAL_MATCH"
                base_score += 25
            else:
                sanctions_status = "CLEARED"

            risk_score = min(100, max(5, base_score))
            if risk_score >= 70:
                risk_tier = "HIGH"
            elif risk_score >= 40:
                risk_tier = "MEDIUM"
            else:
                risk_tier = "LOW"

            rationale = f"Assessed based on jurisdiction ({cust.jurisdiction}:{juris_risk}), PEP state ({pep_status}), and legal structure."
            assessed_by = self.rng.choice(ANALYST_POOL) if risk_tier == "HIGH" else "SYSTEM_ENGINE"
            assessed_at = cust.created_at

            rr = RiskRating(
                risk_id=risk_id,
                customer_id=cust.customer_id,
                risk_score=risk_score,
                risk_tier=risk_tier,
                rationale=rationale,
                sanctions_screening_status=sanctions_status,
                pep_status=pep_status,
                jurisdiction_risk=juris_risk,
                assessed_by=assessed_by,
                assessed_at=assessed_at,
            )
            self.risk_ratings.append(rr)

    def _generate_beneficial_owners(self):
        """Generates UBO equity holders for business entities."""
        for cust in self.customers:
            if cust.customer_type_code == "INDIVIDUAL":
                continue

            # Corporate / Trust / Partnership requires 1 to 4 beneficial owners
            num_owners = self.rng.randint(1, 4)
            # Create valid percentages summing to 100% or slightly less
            if num_owners == 1:
                percentages = [100.0]
            elif num_owners == 2:
                p1 = round(self.rng.uniform(40.0, 60.0), 2)
                percentages = [p1, round(100.0 - p1, 2)]
            elif num_owners == 3:
                p1 = round(self.rng.uniform(30.0, 45.0), 2)
                p2 = round(self.rng.uniform(25.0, 35.0), 2)
                percentages = [p1, p2, round(100.0 - (p1 + p2), 2)]
            else:
                percentages = [30.0, 25.0, 25.0, 20.0]

            for pct in percentages:
                owner_id = self._next_ubo_id()
                first_name = self.rng.choice(FIRST_NAMES)
                last_name = self.rng.choice(LAST_NAMES)
                dob = self._random_date(date(1955, 1, 1), date(1998, 1, 1)).isoformat()
                nationality, _ = self._pick_jurisdiction()
                control_type = "DIRECT_SHAREHOLDER" if pct >= 25.0 else "INDIRECT_SHAREHOLDER"

                bo = BeneficialOwner(
                    owner_id=owner_id,
                    business_customer_id=cust.customer_id,
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=dob,
                    nationality=nationality,
                    ownership_percentage=pct,
                    control_type=control_type,
                    is_sanctions_screened=True,
                    created_at=cust.created_at,
                )
                self.beneficial_owners.append(bo)

    def _generate_documents_and_verifications(self):
        """Generates documents and verification checks matching policy requirements."""
        risk_map = {r.customer_id: r.risk_tier for r in self.risk_ratings}
        doc_counter_by_cust: Dict[str, int] = {}

        # Pre-calculate how many docs per customer to hit scale target (~20,000 for full)
        for cust in self.customers:
            risk_tier = risk_map.get(cust.customer_id, "LOW")
            reqs = get_mandatory_requirements_for_customer(
                cust.customer_type_code, risk_tier, self.kyc_requirements
            )
            cust_created_date = datetime.strptime(cust.created_at[:10], "%Y-%m-%d").date()

            # Determine whether customer has complete documents submitted
            # If customer status is APPROVED, baseline has all required docs verified
            # If IN_REVIEW, maybe missing 1 doc
            # If PENDING, maybe only 1 uploaded
            docs_to_generate = []
            if cust.onboarding_status == "APPROVED":
                docs_to_generate = reqs.copy()
            elif cust.onboarding_status == "IN_REVIEW":
                docs_to_generate = reqs[: max(1, len(reqs) - 1)]
            elif cust.onboarding_status == "PENDING":
                docs_to_generate = reqs[:1]
            else:  # REJECTED or SUSPENDED
                docs_to_generate = reqs[: max(1, len(reqs) - 1)]

            for req in docs_to_generate:
                c_idx = doc_counter_by_cust.get(cust.customer_id, 0) + 1
                doc_counter_by_cust[cust.customer_id] = c_idx
                doc_id = f"DOC-{cust.customer_id}-{c_idx:03d}"

                # Expiry date and issue date
                if req.validity_period_days:
                    if cust.onboarding_status == "APPROVED":
                        expiry_date_val = ANCHOR_DATE + timedelta(days=self.rng.randint(60, max(61, req.validity_period_days)))
                        issue_date_val = expiry_date_val - timedelta(days=req.validity_period_days)
                    else:
                        issue_date_val = self._random_date(
                            cust_created_date - timedelta(days=700), cust_created_date - timedelta(days=10)
                        )
                        expiry_date_val = issue_date_val + timedelta(days=req.validity_period_days)
                    expiry_str = expiry_date_val.isoformat()
                else:
                    issue_date_val = self._random_date(
                        cust_created_date - timedelta(days=700), cust_created_date - timedelta(days=10)
                    )
                    expiry_date_val = None
                    expiry_str = None

                # Baseline status: if customer is approved and doc not expired, VERIFIED
                if cust.onboarding_status == "APPROVED":
                    if expiry_date_val and expiry_date_val <= ANCHOR_DATE:
                        doc_status = "EXPIRED"
                    else:
                        doc_status = "VERIFIED"
                elif cust.onboarding_status == "IN_REVIEW":
                    doc_status = "UNDER_REVIEW"
                elif cust.onboarding_status == "PENDING":
                    doc_status = "UPLOADED"
                else:
                    doc_status = "REJECTED"

                ref_num = f"{req.document_type[:3]}-{cust.customer_id[4:]}-{c_idx:02d}"
                sha = self._generate_sha256(f"{doc_id}:{ref_num}:{cust.customer_id}")

                doc = Document(
                    document_id=doc_id,
                    customer_id=cust.customer_id,
                    document_category=req.document_category,
                    document_type=req.document_type,
                    document_reference_number=ref_num,
                    issuing_country=cust.jurisdiction,
                    issue_date=issue_date_val.isoformat(),
                    expiry_date=expiry_str,
                    document_status=doc_status,
                    file_hash_sha256=sha,
                    created_at=cust.created_at,
                )
                self.documents.append(doc)

                # Generate Verification for submitted documents
                vrf_id = self._next_vrf_id()
                v_method = "AUTOMATED_OCR" if req.document_category == "IDENTITY" else "MANUAL_DOCUMENT_CHECK"
                v_actor = "SYSTEM" if v_method == "AUTOMATED_OCR" else "OPERATIONS_ANALYST"
                v_status = "PASSED" if doc_status in ["VERIFIED", "EXPIRED"] else ("FAILED" if doc_status == "REJECTED" else "INCONCLUSIVE")
                notes = None if v_status == "PASSED" else "Awaiting complete manual reconciliation."

                vrf = Verification(
                    verification_id=vrf_id,
                    document_id=doc.document_id,
                    verifier_actor=v_actor,
                    verification_method=v_method,
                    verification_status=v_status,
                    discrepancy_notes=notes,
                    verified_at=cust.updated_at,
                )
                self.verifications.append(vrf)

        # Supplementary documents to reach exact target document scale (~20,000 for full)
        cust_idx = 0
        num_custs = len(self.customers)
        while len(self.documents) < self.target_documents and num_custs > 0:
            cust = self.customers[cust_idx % num_custs]
            cust_idx += 1
            cust_created_date = datetime.strptime(cust.created_at[:10], "%Y-%m-%d").date()
            c_idx = doc_counter_by_cust.get(cust.customer_id, 0) + 1
            doc_counter_by_cust[cust.customer_id] = c_idx
            doc_id = f"DOC-{cust.customer_id}-{c_idx:03d}"

            if cust.customer_type_code == "INDIVIDUAL":
                supp_cat = "IDENTITY" if c_idx % 2 == 0 else "TAX_CERTIFICATE"
                supp_type = "DRIVERS_LICENSE" if supp_cat == "IDENTITY" else "W9_W8BEN"
                validity = 1460 if supp_cat == "IDENTITY" else 1095
            else:
                supp_cat = "FINANCIAL_STATEMENT" if c_idx % 2 == 0 else "TAX_CERTIFICATE"
                supp_type = "AUDITED_FINANCIALS" if supp_cat == "FINANCIAL_STATEMENT" else "W9_W8BEN"
                validity = 365

            if cust.onboarding_status == "APPROVED":
                r_exp = self.rng.random()
                if r_exp < 0.20:
                    expiry_date_val = ANCHOR_DATE - timedelta(days=self.rng.randint(10, 180))
                    issue_date_val = expiry_date_val - timedelta(days=validity)
                    doc_status = "EXPIRED"
                elif r_exp < 0.40:
                    expiry_date_val = ANCHOR_DATE + timedelta(days=self.rng.randint(5, 89))
                    issue_date_val = expiry_date_val - timedelta(days=validity)
                    doc_status = "VERIFIED"
                else:
                    expiry_date_val = ANCHOR_DATE + timedelta(days=self.rng.randint(91, max(92, validity)))
                    issue_date_val = expiry_date_val - timedelta(days=validity)
                    doc_status = "VERIFIED"
            else:
                issue_date_val = self._random_date(
                    cust_created_date - timedelta(days=600), cust_created_date - timedelta(days=15)
                )
                expiry_date_val = issue_date_val + timedelta(days=validity)
                doc_status = "UNDER_REVIEW"

            expiry_str = expiry_date_val.isoformat()

            ref_num = f"{supp_type[:3]}-{cust.customer_id[4:]}-{c_idx:02d}"
            sha = self._generate_sha256(f"{doc_id}:{ref_num}:{cust.customer_id}")

            doc = Document(
                document_id=doc_id,
                customer_id=cust.customer_id,
                document_category=supp_cat,
                document_type=supp_type,
                document_reference_number=ref_num,
                issuing_country=cust.jurisdiction,
                issue_date=issue_date_val.isoformat(),
                expiry_date=expiry_str,
                document_status=doc_status,
                file_hash_sha256=sha,
                created_at=cust.created_at,
            )
            self.documents.append(doc)

            vrf_id = self._next_vrf_id()
            vrf = Verification(
                verification_id=vrf_id,
                document_id=doc.document_id,
                verifier_actor="OPERATIONS_ANALYST",
                verification_method="MANUAL_DOCUMENT_CHECK",
                verification_status="PASSED" if doc.document_status in ["VERIFIED", "EXPIRED"] else "INCONCLUSIVE",
                discrepancy_notes=None,
                verified_at=cust.updated_at,
            )
            self.verifications.append(vrf)

    def _inject_mandatory_edge_cases(self):
        """
        Injects the 5 mandated compliance edge cases with exact ground truth tracking:
        1. Document expired but marked valid (EXPIRED_DOC_MARKED_VALID)
        2. Customer approved with missing mandatory evidence (APPROVED_WITHOUT_MANDATORY_EVIDENCE)
        3. Ownership percentages exceed 100% (UBO_PERCENTAGE_EXCEEDS_100)
        4. Review closes without resolution (REVIEW_CLOSED_WITHOUT_RESOLUTION)
        5. Duplicate document used across unrelated customers (DUPLICATE_DOCUMENT_CROSS_CUSTOMER)
        """
        k = self.target_anomalies_per_type

        # ---------------------------------------------------------
        # Case 1: Document expired but marked valid (EXPIRED_DOC_MARKED_VALID)
        # ---------------------------------------------------------
        expirable_docs = [
            d for d in self.documents
            if d.expiry_date and datetime.strptime(d.expiry_date, "%Y-%m-%d").date() < ANCHOR_DATE
        ]
        target_exp_docs = expirable_docs[:k] if len(expirable_docs) >= k else [d for d in self.documents if d.expiry_date][:k]
        for d in target_exp_docs:
            # Force issue_date to 2020-01-01 and expiry_date to past 2025-05-10 with VERIFIED status
            d.issue_date = "2020-01-01"
            d.expiry_date = "2025-05-10"
            d.document_status = "VERIFIED"
            
            ano = GroundTruthAnomaly(
                anomaly_id=self._next_ano_id(),
                anomaly_type="EXPIRED_DOC_MARKED_VALID",
                entity_type="DOCUMENT",
                primary_entity_id=d.document_id,
                secondary_entity_id=d.customer_id,
                description=f"Document {d.document_id} expired on 2025-05-10 but retains VERIFIED status.",
                severity="CRITICAL",
                expected_rule_violation="RULE_DOC_EXPIRY_INTEGRITY",
            )
            self.ground_truth.append(ano)

        # ---------------------------------------------------------
        # Case 2: Customer approved with missing mandatory evidence (APPROVED_WITHOUT_MANDATORY_EVIDENCE)
        # ---------------------------------------------------------
        approved_customers = [c for c in self.customers if c.onboarding_status == "APPROVED"]
        target_approved = approved_customers[:k]
        for c in target_approved:
            # Delete one or all mandatory documents for this approved customer
            cust_docs = [d for d in self.documents if d.customer_id == c.customer_id]
            if cust_docs:
                doc_to_remove = cust_docs[0]
                self.documents = [d for d in self.documents if d.document_id != doc_to_remove.document_id]
                self.verifications = [v for v in self.verifications if v.document_id != doc_to_remove.document_id]

            ano = GroundTruthAnomaly(
                anomaly_id=self._next_ano_id(),
                anomaly_type="APPROVED_WITHOUT_MANDATORY_EVIDENCE",
                entity_type="CUSTOMER",
                primary_entity_id=c.customer_id,
                secondary_entity_id=None,
                description=f"Customer {c.customer_id} is marked APPROVED while missing mandatory verification evidence.",
                severity="CRITICAL",
                expected_rule_violation="RULE_ONBOARDING_COMPLETENESS_GATE",
            )
            self.ground_truth.append(ano)

        # ---------------------------------------------------------
        # Case 3: Ownership percentages exceed 100% (UBO_PERCENTAGE_EXCEEDS_100)
        # ---------------------------------------------------------
        biz_ids = list(set(b.business_customer_id for b in self.beneficial_owners))[:k]
        for biz_id in biz_ids:
            biz_ubos = [b for b in self.beneficial_owners if b.business_customer_id == biz_id]
            if biz_ubos:
                # Inflate the first beneficial owner percentage so the total exceeds 100%
                biz_ubos[0].ownership_percentage += 35.0  # E.g. pushes total to ~115% - 135%
                
                ano = GroundTruthAnomaly(
                    anomaly_id=self._next_ano_id(),
                    anomaly_type="UBO_PERCENTAGE_EXCEEDS_100",
                    entity_type="BENEFICIAL_OWNER",
                    primary_entity_id=biz_id,
                    secondary_entity_id=biz_ubos[0].owner_id,
                    description=f"Business customer {biz_id} total registered UBO ownership exceeds 100.0%.",
                    severity="HIGH",
                    expected_rule_violation="RULE_UBO_SUM_CONSTRAINT",
                )
                self.ground_truth.append(ano)

        # ---------------------------------------------------------
        # Case 4: Review closes without resolution (REVIEW_CLOSED_WITHOUT_RESOLUTION)
        # Note: We track these customer IDs now and inject the faulty ReviewCase during _generate_review_cases
        # ---------------------------------------------------------
        approved_suspended = [c.customer_id for c in self.customers if c.onboarding_status in ["APPROVED", "SUSPENDED"]]
        self.anomalous_review_cust_ids = approved_suspended[50 : 50 + k]
        for cid in self.anomalous_review_cust_ids:
            case_id = f"REV-{cid}-2026"
            ano = GroundTruthAnomaly(
                anomaly_id=self._next_ano_id(),
                anomaly_type="REVIEW_CLOSED_WITHOUT_RESOLUTION",
                entity_type="REVIEW_CASE",
                primary_entity_id=case_id,
                secondary_entity_id=cid,
                description=f"Review case {case_id} was closed as CLOSED_WITHOUT_RESOLUTION without definitive disposition.",
                severity="HIGH",
                expected_rule_violation="RULE_REVIEW_OUTCOME_RESOLUTION",
            )
            self.ground_truth.append(ano)

        # ---------------------------------------------------------
        # Case 5: Duplicate document used across unrelated customers (DUPLICATE_DOCUMENT_CROSS_CUSTOMER)
        # ---------------------------------------------------------
        individual_docs = [
            d for d in self.documents
            if d.document_category == "IDENTITY" and d.customer_id not in [a.primary_entity_id for a in self.ground_truth]
        ]
        unrelated_customers = [c for c in self.customers if c.customer_type_code == "INDIVIDUAL"]
        for idx in range(min(k, len(individual_docs) - 1, len(unrelated_customers) - 2)):
            victim_doc = individual_docs[idx]
            target_cust = unrelated_customers[-(idx + 1)]
            
            dup_doc_id = f"DOC-{target_cust.customer_id}-999"
            dup_doc = Document(
                document_id=dup_doc_id,
                customer_id=target_cust.customer_id,
                document_category=victim_doc.document_category,
                document_type=victim_doc.document_type,
                document_reference_number=victim_doc.document_reference_number,  # Stolen identical reference number
                issuing_country=victim_doc.issuing_country,
                issue_date=victim_doc.issue_date,
                expiry_date=victim_doc.expiry_date,
                document_status="VERIFIED",
                file_hash_sha256=victim_doc.file_hash_sha256,
                created_at=target_cust.created_at,
            )
            self.documents.append(dup_doc)

            ano = GroundTruthAnomaly(
                anomaly_id=self._next_ano_id(),
                anomaly_type="DUPLICATE_DOCUMENT_CROSS_CUSTOMER",
                entity_type="DOCUMENT",
                primary_entity_id=dup_doc_id,
                secondary_entity_id=victim_doc.document_id,
                description=f"Document {dup_doc_id} reuses reference number '{victim_doc.document_reference_number}' across distinct customers {target_cust.customer_id} and {victim_doc.customer_id}.",
                severity="CRITICAL",
                expected_rule_violation="RULE_DOC_GLOBAL_UNIQUENESS",
            )
            self.ground_truth.append(ano)

    def _calculate_derived_completeness(self):
        """Calculates derived completeness score for every customer strictly from source records."""
        risk_map = {r.customer_id: r.risk_tier for r in self.risk_ratings}
        # Group documents by customer_id for fast O(1) lookup
        docs_by_cust: Dict[str, List[Document]] = {}
        for d in self.documents:
            docs_by_cust.setdefault(d.customer_id, []).append(d)

        for cust in self.customers:
            cust_docs = docs_by_cust.get(cust.customer_id, [])
            risk_tier = risk_map.get(cust.customer_id, "LOW")
            score, _, _ = calculate_customer_completeness(
                cust, risk_tier, cust_docs, self.kyc_requirements, ANCHOR_DATE
            )
            cust.completeness_score = score

    def _generate_review_cases(self):
        """Generates periodic reviews and initial onboarding reviews."""
        risk_map = {r.customer_id: r.risk_tier for r in self.risk_ratings}

        # Target reviews up to self.target_review_cases
        case_candidates = [c for c in self.customers if c.onboarding_status in ["APPROVED", "SUSPENDED"]]
        selected_candidates = case_candidates[: min(len(case_candidates), self.target_review_cases)]

        for cust in selected_candidates:
            case_id = f"REV-{cust.customer_id}-2026"
            risk_tier = risk_map.get(cust.customer_id, "LOW")
            interval_days = get_periodic_review_interval_days(risk_tier)

            created_date = datetime.strptime(cust.created_at[:10], "%Y-%m-%d").date()
            scheduled_date = created_date + timedelta(days=interval_days)
            due_date = scheduled_date + timedelta(days=30)

            # Check if this customer is marked for the Case 4 anomaly
            if hasattr(self, "anomalous_review_cust_ids") and cust.customer_id in self.anomalous_review_cust_ids:
                rc = ReviewCase(
                    case_id=case_id,
                    customer_id=cust.customer_id,
                    review_type="PERIODIC_ANNUAL",
                    case_status="CLOSED_WITHOUT_RESOLUTION",
                    priority="HIGH",
                    scheduled_date=scheduled_date.isoformat(),
                    due_date=due_date.isoformat(),
                    assigned_analyst=self.rng.choice(ANALYST_POOL),
                    resolved_at=f"{due_date.isoformat()}T17:00:00Z",
                    resolution_outcome="UNRESOLVED",
                    created_at=f"{scheduled_date.isoformat()}T08:00:00Z",
                )
                self.review_cases.append(rc)
                continue

            # Regular case logic
            priority = "URGENT" if risk_tier == "HIGH" else ("HIGH" if risk_tier == "MEDIUM" else "NORMAL")
            
            # If scheduled date is in the past, it's either completed or overdue
            if scheduled_date < ANCHOR_DATE:
                if self.rng.random() < 0.65:
                    status = "APPROVED"
                    outcome = "APPROVED"
                    resolved_at = f"{(scheduled_date + timedelta(days=14)).isoformat()}T16:00:00Z"
                else:
                    status = "OPEN"  # Overdue review!
                    outcome = None
                    resolved_at = None
            else:
                status = "OPEN"
                outcome = None
                resolved_at = None

            rc = ReviewCase(
                case_id=case_id,
                customer_id=cust.customer_id,
                review_type="PERIODIC_ANNUAL",
                case_status=status,
                priority=priority,
                scheduled_date=scheduled_date.isoformat(),
                due_date=due_date.isoformat(),
                assigned_analyst=self.rng.choice(ANALYST_POOL),
                resolved_at=resolved_at,
                resolution_outcome=outcome,
                created_at=f"{scheduled_date.isoformat()}T08:00:00Z",
            )
            self.review_cases.append(rc)

    def _generate_alerts(self):
        """Evaluates documents and review cases to generate operational alerts."""
        # 1. Document Expiration Alerts
        for doc in self.documents:
            eval_res = evaluate_document_expiry_alert(doc, ANCHOR_DATE)
            if eval_res:
                alert_type, lead_days, severity = eval_res
                alt = Alert(
                    alert_id=self._next_alt_id(),
                    customer_id=doc.customer_id,
                    document_id=doc.document_id,
                    alert_type=alert_type,
                    lead_time_days=lead_days,
                    severity=severity,
                    alert_status="NEW",
                    created_at=f"{ANCHOR_DATE.isoformat()}T06:00:00Z",
                    acknowledged_at=None,
                )
                self.alerts.append(alt)

        # 2. Overdue Periodic Review Alerts
        for rc in self.review_cases:
            if rc.case_status == "OPEN":
                due = datetime.strptime(rc.due_date, "%Y-%m-%d").date()
                if due < ANCHOR_DATE:
                    overdue_days = (ANCHOR_DATE - due).days
                    alt = Alert(
                        alert_id=self._next_alt_id(),
                        customer_id=rc.customer_id,
                        document_id=None,
                        alert_type="PERIODIC_REVIEW_OVERDUE",
                        lead_time_days=-overdue_days,
                        severity="HIGH" if overdue_days < 60 else "CRITICAL",
                        alert_status="NEW",
                        created_at=f"{ANCHOR_DATE.isoformat()}T06:00:00Z",
                        acknowledged_at=None,
                    )
                    self.alerts.append(alt)

    def _generate_audit_events(self):
        """Generates immutable audit event trail for customer and evidence state transitions."""
        for cust in self.customers[: min(len(self.customers), 1000)]:
            ev1 = AuditEvent(
                event_id=self._next_aud_id(),
                entity_type="CUSTOMER",
                entity_id=cust.customer_id,
                actor_role="CUSTOMER",
                actor_id="SYS_PORTAL",
                event_type="CREATED",
                old_state=None,
                new_state="PENDING",
                change_reason="Customer profile initiated via onboarding portal",
                timestamp=cust.created_at,
            )
            self.audit_events.append(ev1)

            if cust.onboarding_status in ["APPROVED", "REJECTED", "SUSPENDED"]:
                ev2 = AuditEvent(
                    event_id=self._next_aud_id(),
                    entity_type="CUSTOMER",
                    entity_id=cust.customer_id,
                    actor_role="RISK_COMPLIANCE_REVIEWER",
                    actor_id="COMPLIANCE_LEAD",
                    event_type="STATUS_CHANGED",
                    old_state="IN_REVIEW",
                    new_state=cust.onboarding_status,
                    change_reason=f"Transitioned to {cust.onboarding_status} following completeness and risk review",
                    timestamp=cust.updated_at,
                )
                self.audit_events.append(ev2)
