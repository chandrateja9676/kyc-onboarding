"""
Lightweight embedded HTTP server providing a REST API and rich single-page Dashboard.
Uses Python's standard library http.server (zero third-party dependencies required).
"""

import os
import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kyc_lifecycle.db")


class KYCRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Any, status: int = 200):
        response_bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def _send_html(self, html_content: str, status: int = 200):
        response_bytes = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Route API endpoints
        if path == "/api/stats":
            self.handle_stats()
        elif path == "/api/customers":
            self.handle_customers(query)
        elif path.startswith("/api/customer/"):
            cust_id = path.replace("/api/customer/", "")
            self.handle_customer_detail(cust_id)
        elif path == "/api/alerts":
            self.handle_alerts(query)
        elif path == "/api/reviews":
            self.handle_reviews(query)
        elif path == "/api/audit":
            self.handle_audit(query)
        elif path == "/api/compliance-audit":
            self.handle_compliance_audit()
        elif path == "/" or path == "/index.html":
            self.handle_dashboard_ui()
        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        from src.pipeline import LiveOnboardingPipeline, BatchSurveillancePipeline, TimeMachineEngine

        if path == "/api/pipeline/onboard":
            pipeline = LiveOnboardingPipeline(DB_PATH)
            res = pipeline.onboard_new_customer(
                customer_type_code=payload.get("customer_type_code", "INDIVIDUAL"),
                legal_name=payload.get("legal_name", "Anonymous"),
                tax_id=payload.get("tax_id", "US-TX-000000"),
                jurisdiction=payload.get("jurisdiction", "US"),
                date_of_birth_or_inc=payload.get("date_of_birth_or_inc", "1990-01-01"),
                trade_name=payload.get("trade_name"),
            )
            self._send_json(res, 201)
        elif path == "/api/pipeline/upload":
            pipeline = LiveOnboardingPipeline(DB_PATH)
            res = pipeline.upload_and_process_evidence(
                customer_id=payload.get("customer_id"),
                document_category=payload.get("document_category"),
                document_type=payload.get("document_type"),
                document_reference_number=payload.get("document_reference_number"),
                issuing_country=payload.get("issuing_country", "US"),
                issue_date=payload.get("issue_date", "2024-01-01"),
                expiry_date=payload.get("expiry_date"),
            )
            self._send_json(res, 200)
        elif path == "/api/pipeline/surveillance":
            surv = BatchSurveillancePipeline(DB_PATH)
            res = surv.run_daily_surveillance()
            self._send_json(res, 200)
        elif path == "/api/pipeline/advance-time":
            engine = TimeMachineEngine(DB_PATH)
            days = int(payload.get("days", 30))
            res = engine.advance_time(days=days)
            self._send_json(res, 200)
        elif path == "/api/pipeline/resolve-review":
            pipeline = LiveOnboardingPipeline(DB_PATH)
            res = pipeline.resolve_review_case(
                case_id=payload.get("case_id"),
                analyst_id=payload.get("analyst_id", "ANALYST_S_CHEN"),
                resolution_outcome=payload.get("resolution_outcome", "APPROVED"),
            )
            self._send_json(res, 200)
        else:
            self.send_error(404, "Endpoint Not Found")

    def handle_stats(self):
        conn = self.get_db()
        cur = conn.cursor()
        total_customers = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        approved_customers = cur.execute("SELECT COUNT(*) FROM customers WHERE onboarding_status = 'APPROVED'").fetchone()[0]
        avg_completeness = cur.execute("SELECT ROUND(AVG(completeness_score) * 100, 1) FROM customers").fetchone()[0] or 0.0
        total_docs = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        total_alerts = cur.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        critical_alerts = cur.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'CRITICAL'").fetchone()[0]
        open_reviews = cur.execute("SELECT COUNT(*) FROM review_cases WHERE case_status = 'OPEN'").fetchone()[0]
        total_anomalies = cur.execute("SELECT COUNT(*) FROM ground_truth").fetchone()[0]

        # By customer type
        type_counts = dict(cur.execute("SELECT customer_type_code, COUNT(*) FROM customers GROUP BY customer_type_code").fetchall())
        conn.close()

        self._send_json({
            "total_customers": total_customers,
            "approved_customers": approved_customers,
            "avg_completeness_pct": avg_completeness,
            "total_documents": total_docs,
            "total_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "open_reviews": open_reviews,
            "total_anomalies": total_anomalies,
            "type_counts": type_counts,
        })

    def handle_customers(self, query):
        conn = self.get_db()
        cur = conn.cursor()
        limit = int(query.get("limit", [50])[0])
        status = query.get("status", [None])[0]
        type_code = query.get("type", [None])[0]
        search = query.get("q", [None])[0]

        conditions = []
        params = []
        if status:
            conditions.append("c.onboarding_status = ?")
            params.append(status)
        if type_code:
            conditions.append("c.customer_type_code = ?")
            params.append(type_code)
        if search:
            conditions.append("(c.customer_id LIKE ? OR c.legal_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT c.*, r.risk_tier, r.risk_score, r.sanctions_screening_status
            FROM customers c
            LEFT JOIN risk_ratings r ON c.customer_id = r.customer_id
            {where_clause}
            ORDER BY c.customer_id ASC
            LIMIT ?
        """
        params.append(limit)
        rows = [dict(r) for r in cur.execute(sql, params).fetchall()]
        conn.close()
        self._send_json({"count": len(rows), "customers": rows})

    def handle_customer_detail(self, cust_id: str):
        conn = self.get_db()
        cur = conn.cursor()
        cust = cur.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,)).fetchone()
        if not cust:
            conn.close()
            self._send_json({"error": "Customer not found"}, 404)
            return

        risk = cur.execute("SELECT * FROM risk_ratings WHERE customer_id = ?", (cust_id,)).fetchone()
        docs = cur.execute("SELECT * FROM documents WHERE customer_id = ?", (cust_id,)).fetchall()
        ubos = cur.execute("SELECT * FROM beneficial_owners WHERE business_customer_id = ?", (cust_id,)).fetchall()
        reviews = cur.execute("SELECT * FROM review_cases WHERE customer_id = ?", (cust_id,)).fetchall()
        alerts = cur.execute("SELECT * FROM alerts WHERE customer_id = ?", (cust_id,)).fetchall()
        audits = cur.execute("SELECT * FROM audit_events WHERE entity_id = ? ORDER BY timestamp DESC", (cust_id,)).fetchall()

        conn.close()
        self._send_json({
            "customer": dict(cust),
            "risk_rating": dict(risk) if risk else None,
            "documents": [dict(d) for d in docs],
            "beneficial_owners": [dict(u) for u in ubos],
            "review_cases": [dict(r) for r in reviews],
            "alerts": [dict(a) for a in alerts],
            "audit_events": [dict(e) for e in audits],
        })

    def handle_alerts(self, query):
        conn = self.get_db()
        cur = conn.cursor()
        severity = query.get("severity", [None])[0]
        conditions = []
        params = []
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM alerts {where_clause} ORDER BY lead_time_days ASC LIMIT 100"
        rows = [dict(r) for r in cur.execute(sql, params).fetchall()]
        conn.close()
        self._send_json({"alerts": rows})

    def handle_reviews(self, query):
        conn = self.get_db()
        cur = conn.cursor()
        status = query.get("status", [None])[0]
        conditions = []
        params = []
        if status:
            conditions.append("case_status = ?")
            params.append(status)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM review_cases {where_clause} ORDER BY due_date ASC LIMIT 100"
        rows = [dict(r) for r in cur.execute(sql, params).fetchall()]
        conn.close()
        self._send_json({"reviews": rows})

    def handle_audit(self, query):
        conn = self.get_db()
        cur = conn.cursor()
        sql = "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 100"
        rows = [dict(r) for r in cur.execute(sql).fetchall()]
        conn.close()
        self._send_json({"audit_events": rows})

    def handle_compliance_audit(self):
        from src.validator import DatasetValidator
        validator = DatasetValidator(DB_PATH)
        report = validator.evaluate_compliance_rules_against_ground_truth()
        validator.close()
        self._send_json(report)

    def handle_dashboard_ui(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KYC Onboarding & Evidence Lifecycle Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-hover: #334155;
            --border-color: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-light: #60a5fa;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --accent: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; }
        header { background-color: var(--surface-color); border-bottom: 1px solid var(--border-color); padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; }
        .logo-wrap { display: flex; align-items: center; gap: 12px; }
        .logo-badge { background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 14px; letter-spacing: 0.5px; }
        .title { font-size: 18px; font-weight: 600; }
        .subtitle { font-size: 12px; color: var(--text-muted); }
        .nav-tabs { display: flex; gap: 8px; margin-top: 16px; border-bottom: 1px solid var(--border-color); padding: 0 32px; background-color: var(--surface-color); }
        .nav-btn { background: none; border: none; color: var(--text-muted); padding: 12px 18px; cursor: pointer; font-size: 14px; font-weight: 500; border-bottom: 2px solid transparent; transition: all 0.2s; }
        .nav-btn:hover { color: var(--text-main); }
        .nav-btn.active { color: var(--primary-light); border-bottom-color: var(--primary-light); font-weight: 600; }
        main { padding: 32px; flex: 1; max-width: 1400px; margin: 0 auto; width: 100%; }
        .grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background-color: var(--surface-color); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; }
        .card-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }
        .card-value { font-size: 28px; font-weight: 700; margin-top: 6px; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .badge-green { background-color: rgba(16, 185, 129, 0.15); color: #34d399; }
        .badge-yellow { background-color: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .badge-red { background-color: rgba(239, 68, 68, 0.15); color: #f87171; }
        .badge-blue { background-color: rgba(59, 130, 246, 0.15); color: #60a5fa; }
        .badge-purple { background-color: rgba(139, 92, 246, 0.15); color: #a78bfa; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
        th { text-align: left; padding: 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-color); font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid rgba(51, 65, 85, 0.5); }
        tr:hover td { background-color: var(--surface-hover); cursor: pointer; }
        .search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
        .search-input { flex: 1; background: var(--surface-color); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 14px; color: white; font-size: 14px; }
        .search-input:focus { outline: none; border-color: var(--primary); }
        .btn { background: var(--primary); border: none; color: white; padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; transition: 0.2s; }
        .btn:hover { background: #2563eb; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: center; }
        .modal-content { background: var(--surface-color); border: 1px solid var(--border-color); width: 850px; max-width: 90%; max-height: 85vh; overflow-y: auto; border-radius: 14px; padding: 24px; position: relative; }
        .close-btn { position: absolute; top: 18px; right: 20px; font-size: 20px; cursor: pointer; color: var(--text-muted); }
        .progress-bar-bg { background-color: #334155; border-radius: 4px; height: 8px; width: 100%; overflow: hidden; margin-top: 4px; }
        .progress-bar-fill { background: linear-gradient(90deg, #3b82f6, #10b981); height: 100%; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <header>
        <div class="logo-wrap">
            <div class="logo-badge">AML / KYC 2.0</div>
            <div>
                <div class="title">KYC Onboarding & Evidence Lifecycle Platform</div>
                <div class="subtitle">Complete Traceability • Completeness Validation • Automated Expiration Alerts • Ground Truth Audits</div>
            </div>

        </div>
        <div style="font-size: 12px; color: var(--text-muted);">
            Simulation Anchor Date: <strong style="color: white;">2026-10-26</strong>
        </div>
    </header>

    <div class="nav-tabs">
        <button class="nav-btn active" onclick="switchTab('customers-tab')">Customers & Completeness</button>
        <button class="nav-btn" onclick="switchTab('alerts-tab')">Expiry & Risk Alerts</button>
        <button class="nav-btn" onclick="switchTab('reviews-tab')">Periodic Reviews</button>
        <button class="nav-btn" onclick="switchTab('audits-tab')">Compliance Audit & Ground Truth</button>
        <button class="nav-btn" onclick="switchTab('log-tab')">Audit Event Trail</button>
        <button class="nav-btn" onclick="switchTab('pipeline-tab')">Live Operations & Time Machine</button>
    </div>

    <main>
        <!-- KPI METRICS -->
        <div class="grid-cards">
            <div class="card">
                <div class="card-label">Total Customers</div>
                <div class="card-value" id="kpi-total-cust">-</div>
            </div>

            <div class="card">
                <div class="card-label">Approved Accounts</div>
                <div class="card-value" style="color: #34d399;" id="kpi-approved-cust">-</div>
            </div>

            <div class="card">
                <div class="card-label">Avg Completeness</div>
                <div class="card-value" style="color: #60a5fa;" id="kpi-avg-comp">-%</div>
            </div>

            <div class="card">
                <div class="card-label">Critical Alerts</div>
                <div class="card-value" style="color: #f87171;" id="kpi-crit-alerts">-</div>
            </div>

            <div class="card">
                <div class="card-label">Open Reviews</div>
                <div class="card-value" style="color: #fbbf24;" id="kpi-open-reviews">-</div>
            </div>

            <div class="card">
                <div class="card-label">Injected Anomalies</div>
                <div class="card-value" style="color: #a78bfa;" id="kpi-anomalies">-</div>
            </div>

        </div>

        <!-- TAB 1: CUSTOMERS -->
        <div id="customers-tab" class="tab-content active">
            <div class="search-bar">
                <input type="text" id="cust-search" class="search-input" placeholder="Search by customer ID or legal name..." onkeyup="searchCustomers()">
                <select id="cust-status-filter" class="search-input" style="max-width: 180px;" onchange="loadCustomers()">
                    <option value="">All Statuses</option>
                    <option value="APPROVED">APPROVED</option>
                    <option value="IN_REVIEW">IN_REVIEW</option>
                    <option value="PENDING">PENDING</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                    <option value="REJECTED">REJECTED</option>
                </select>
                <select id="cust-type-filter" class="search-input" style="max-width: 180px;" onchange="loadCustomers()">
                    <option value="">All Types</option>
                    <option value="INDIVIDUAL">INDIVIDUAL</option>
                    <option value="CORPORATE">CORPORATE</option>
                    <option value="TRUST">TRUST</option>
                    <option value="PARTNERSHIP">PARTNERSHIP</option>
                </select>
            </div>

            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Customer ID</th>
                            <th>Legal Name</th>
                            <th>Type</th>
                            <th>Jurisdiction</th>
                            <th>Risk Tier</th>
                            <th>Completeness</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="customers-tbody">
                        <tr><td colspan="7">Loading customer records...</td></tr>
                    </tbody>
                </table>
            </div>

        </div>

        <!-- TAB 2: ALERTS -->
        <div id="alerts-tab" class="tab-content">
            <div class="card">
                <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px;">Operational Expiration & Surveillance Alerts</div>
                <table>
                    <thead>
                        <tr>
                            <th>Alert ID</th>
                            <th>Customer ID</th>
                            <th>Alert Type</th>
                            <th>Lead Time (Days)</th>
                            <th>Severity</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="alerts-tbody">
                        <tr><td colspan="6">Loading operational alerts...</td></tr>
                    </tbody>
                </table>
            </div>

        </div>

        <!-- TAB 3: REVIEWS -->
        <div id="reviews-tab" class="tab-content">
            <div class="card">
                <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px;">Periodic Review Cases & Overdue Surveillance</div>
                <table>
                    <thead>
                        <tr>
                            <th>Case ID</th>
                            <th>Customer ID</th>
                            <th>Type</th>
                            <th>Scheduled Date</th>
                            <th>Due Date</th>
                            <th>Status</th>
                            <th>Outcome</th>
                        </tr>
                    </thead>
                    <tbody id="reviews-tbody">
                        <tr><td colspan="7">Loading review cases...</td></tr>
                    </tbody>
                </table>
            </div>

        </div>

        <!-- TAB 4: COMPLIANCE AUDIT -->
        <div id="audits-tab" class="tab-content">
            <div class="card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 16px;">Automated Compliance Auditor Benchmark</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Evaluates rule enforcement accuracy against isolated Ground Truth dataset.</div>
                    </div>

                    <button class="btn" onclick="runComplianceBenchmark()">Run Live Benchmark</button>
                </div>

                <div style="display: flex; gap: 24px; margin-top: 20px;" id="benchmark-kpis">
                    <div>
                        <div class="card-label">Precision</div>
                        <div class="card-value" style="color: #60a5fa;" id="bm-precision">-</div>
                    </div>

                    <div>
                        <div class="card-label">Recall</div>
                        <div class="card-value" style="color: #34d399;" id="bm-recall">-</div>
                    </div>

                    <div>
                        <div class="card-label">F1-Score</div>
                        <div class="card-value" style="color: #a78bfa;" id="bm-f1">-</div>
                    </div>

                </div>

            </div>

            <div class="card">
                <div style="font-weight: 600; font-size: 15px; margin-bottom: 8px;">Breakdown by Injected Negative Scenario</div>
                <table>
                    <thead>
                        <tr>
                            <th>Anomaly Type</th>
                            <th>Ground Truth</th>
                            <th>Detected</th>
                            <th>True Positives</th>
                            <th>False Positives</th>
                            <th>Precision</th>
                            <th>Recall</th>
                            <th>F1-Score</th>
                        </tr>
                    </thead>
                    <tbody id="benchmark-tbody">
                        <tr><td colspan="8">Click 'Run Live Benchmark' to audit compliance data.</td></tr>
                    </tbody>
                </table>
            </div>

        </div>

        <!-- TAB 5: AUDIT LOG -->
        <div id="log-tab" class="tab-content">
            <div class="card">
                <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px;">Immutable Audit Event Trail</div>
                <table>
                    <thead>
                        <tr>
                            <th>Event ID</th>
                            <th>Entity</th>
                            <th>Actor Role</th>
                            <th>Action</th>
                            <th>Transition</th>
                            <th>Change Reason</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody id="audit-tbody">
                        <tr><td colspan="7">Loading audit events...</td></tr>
                    </tbody>
                </table>
            </div>

        </div>
        <!-- TAB 6: LIVE OPERATIONS & TIME MACHINE -->
        <div id="pipeline-tab" class="tab-content">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <!-- Live Onboarding Form -->
                <div class="card">
                    <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px; color: #60a5fa;">1. Live Customer Onboarding Pipeline</div>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <input type="text" id="live-onb-name" class="search-input" placeholder="Legal Name (e.g., Apex Global Corp)">
                        <select id="live-onb-type" class="search-input">
                            <option value="INDIVIDUAL">INDIVIDUAL</option>
                            <option value="CORPORATE">CORPORATE</option>
                            <option value="TRUST">TRUST</option>
                            <option value="PARTNERSHIP">PARTNERSHIP</option>
                        </select>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="live-onb-tax" class="search-input" placeholder="Tax ID (e.g., US-TX-778899)">
                            <select id="live-onb-juris" class="search-input" style="max-width: 120px;">
                                <option value="US">US</option>
                                <option value="GB">GB</option>
                                <option value="DE">DE</option>
                                <option value="SG">SG</option>
                                <option value="CY">CY</option>
                            </select>
                        </div>

                        <input type="date" id="live-onb-dob" class="search-input" value="1995-04-18">
                        <button class="btn" onclick="submitLiveOnboard()">Submit New Application</button>
                    </div>

                    <div id="live-onb-result" style="margin-top: 14px; font-size: 13px; font-family: monospace; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; display: none;"></div>
                </div>


                <!-- Live Evidence Ingestion & Gate -->
                <div class="card">
                    <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px; color: #34d399;">2. Live Evidence Ingestion & Approval Gate</div>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <input type="text" id="live-up-cust" class="search-input" placeholder="Target Customer ID (e.g., CUS-008001)">
                        <div style="display: flex; gap: 10px;">
                            <select id="live-up-cat" class="search-input">
                                <option value="IDENTITY">IDENTITY</option>
                                <option value="ADDRESS_PROOF">ADDRESS_PROOF</option>
                                <option value="INCORPORATION">INCORPORATION</option>
                                <option value="TAX_CERTIFICATE">TAX_CERTIFICATE</option>
                                <option value="UBO_DECLARATION">UBO_DECLARATION</option>
                            </select>
                            <input type="text" id="live-up-type" class="search-input" placeholder="Doc Type (e.g., PASSPORT)">
                        </div>

                        <input type="text" id="live-up-ref" class="search-input" placeholder="Document Serial/Reference (e.g., P889922)">
                        <div style="display: flex; gap: 10px;">
                            <input type="date" id="live-up-issue" class="search-input" value="2024-01-15">
                            <input type="date" id="live-up-expiry" class="search-input" value="2034-01-15">
                        </div>

                        <button class="btn" style="background: #10b981;" onclick="submitLiveEvidence()">Upload Evidence & Evaluate Gate</button>
                    </div>

                    <div id="live-up-result" style="margin-top: 14px; font-size: 13px; font-family: monospace; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; display: none;"></div>
                </div>

            </div>


            <!-- Time Machine & Batch Operations -->
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 16px; color: #a78bfa;">3. Time Machine & Scheduled Nightly Batch Engine</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Advance the calendar to simulate document aging, expiration triggers, and SLA escalations.</div>
                    </div>

                    <div style="display: flex; gap: 10px;">
                        <button class="btn" style="background: #8b5cf6;" onclick="advanceTimeMachine(30)">Advance +30 Days</button>
                        <button class="btn" style="background: #8b5cf6;" onclick="advanceTimeMachine(60)">Advance +60 Days</button>
                        <button class="btn" style="background: #f59e0b;" onclick="triggerBatchSurveillance()">Run Nightly Batch Job</button>
                    </div>

                </div>

                <div id="time-machine-result" style="margin-top: 14px; font-size: 13px; font-family: monospace; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; display: none;"></div>
            </div>

        </div>
    </main>

    <!-- CUSTOMER DETAILS MODAL -->
    <div id="cust-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal()">&times;</span>
            <div id="modal-body">Loading...</div>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
            if (tabId === 'alerts-tab') loadAlerts();
            if (tabId === 'reviews-tab') loadReviews();
            if (tabId === 'audits-tab') runComplianceBenchmark();
            if (tabId === 'log-tab') loadAuditTrail();
        }

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('kpi-total-cust').innerText = data.total_customers.toLocaleString();
                document.getElementById('kpi-approved-cust').innerText = data.approved_customers.toLocaleString();
                document.getElementById('kpi-avg-comp').innerText = data.avg_completeness_pct + '%';
                document.getElementById('kpi-crit-alerts').innerText = data.critical_alerts.toLocaleString();
                document.getElementById('kpi-open-reviews').innerText = data.open_reviews.toLocaleString();
                document.getElementById('kpi-anomalies').innerText = data.total_anomalies.toLocaleString();
            } catch(e) { console.error(e); }
        }

        async function loadCustomers() {
            const status = document.getElementById('cust-status-filter').value;
            const type = document.getElementById('cust-type-filter').value;
            const search = document.getElementById('cust-search').value;
            let url = `/api/customers?limit=60`;
            if (status) url += `&status=${status}`;
            if (type) url += `&type=${type}`;
            if (search) url += `&q=${encodeURIComponent(search)}`;

            const res = await fetch(url);
            const data = await res.json();
            const tbody = document.getElementById('customers-tbody');
            tbody.innerHTML = '';
            data.customers.forEach(c => {
                const tr = document.createElement('tr');
                tr.onclick = () => openCustomerModal(c.customer_id);
                const scorePct = Math.round(c.completeness_score * 100);
                const badgeClass = c.onboarding_status === 'APPROVED' ? 'badge-green' : (c.onboarding_status === 'REJECTED' ? 'badge-red' : 'badge-yellow');
                const riskClass = c.risk_tier === 'HIGH' ? 'badge-red' : (c.risk_tier === 'MEDIUM' ? 'badge-yellow' : 'badge-green');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #60a5fa;">${c.customer_id}</td>
                    <td>${c.legal_name}</td>
                    <td><span class="badge badge-purple">${c.customer_type_code}</span></td>
                    <td>${c.jurisdiction}</td>
                    <td><span class="badge ${riskClass}">${c.risk_tier || 'LOW'}</span></td>
                    <td style="width: 140px;">
                        <div style="font-size: 11px; font-weight: 600;">${scorePct}%</div>
                        <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: ${scorePct}%;"></div></div>
                    </td>
                    <td><span class="badge ${badgeClass}">${c.onboarding_status}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }

        let debounceTimer;
        function searchCustomers() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(loadCustomers, 300);
        }

        async function openCustomerModal(custId) {
            const modal = document.getElementById('cust-modal');
            modal.style.display = 'flex';
            const body = document.getElementById('modal-body');
            body.innerHTML = '<div>Loading customer details...</div>';
            const res = await fetch(`/api/customer/${custId}`);
            const data = await res.json();
            const c = data.customer;
            const r = data.risk_rating;

            let docsHtml = data.documents.map(d => `
                <tr style="cursor: default;">
                    <td><strong style="color: #60a5fa;">${d.document_id}</strong></td>
                    <td>${d.document_type}</td>
                    <td>${d.document_reference_number}</td>
                    <td>${d.issue_date}</td>
                    <td>${d.expiry_date || 'N/A (Indefinite)'}</td>
                    <td><span class="badge ${d.document_status === 'VERIFIED' ? 'badge-green' : (d.document_status === 'EXPIRED' ? 'badge-red' : 'badge-yellow')}">${d.document_status}</span></td>
                </tr>
            `).join('');

            let ubosHtml = '';
            if (data.beneficial_owners && data.beneficial_owners.length > 0) {
                const totalPct = data.beneficial_owners.reduce((acc, u) => acc + u.ownership_percentage, 0).toFixed(1);
                ubosHtml = `
                    <div style="margin-top: 20px;">
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Beneficial Ownership Structure (Total: ${totalPct}%)</div>
                        <table>
                            <thead><tr><th>Owner ID</th><th>Name</th><th>Nationality</th><th>Ownership %</th><th>Control Type</th></tr></thead>
                            <tbody>
                                ${data.beneficial_owners.map(u => `
                                    <tr>
                                        <td>${u.owner_id}</td>
                                        <td>${u.first_name} ${u.last_name}</td>
                                        <td>${u.nationality}</td>
                                        <td><strong>${u.ownership_percentage}%</strong></td>
                                        <td><span class="badge badge-purple">${u.control_type}</span></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>

                `;
            }

            body.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--border-color); padding-bottom: 16px;">
                    <div>
                        <h2 style="font-size: 20px;">${c.legal_name}</h2>
                        <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">ID: ${c.customer_id} | Tax ID: ${c.tax_id} | Jurisdiction: ${c.jurisdiction}</div>
                    </div>

                    <span class="badge ${c.onboarding_status === 'APPROVED' ? 'badge-green' : 'badge-yellow'}" style="font-size: 14px; padding: 6px 12px;">${c.onboarding_status}</span>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0;">
                    <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px;">
                        <div class="card-label">Type</div>
                        <div style="font-weight: 600; margin-top: 4px;">${c.customer_type_code}</div>
                    </div>

                    <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px;">
                        <div class="card-label">Risk Rating</div>
                        <div style="font-weight: 600; margin-top: 4px; color: ${r?.risk_tier === 'HIGH' ? '#f87171' : '#34d399'};">${r?.risk_tier || 'LOW'} (${r?.risk_score || 0}/100)</div>
                    </div>

                    <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px;">
                        <div class="card-label">Sanctions State</div>
                        <div style="font-weight: 600; margin-top: 4px;">${r?.sanctions_screening_status || 'CLEARED'}</div>
                    </div>

                    <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 8px;">
                        <div class="card-label">Completeness</div>
                        <div style="font-weight: 600; margin-top: 4px;">${Math.round(c.completeness_score * 100)}%</div>
                    </div>

                </div>

                <div style="margin-top: 20px;">
                    <div style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Submitted Evidence & Documents</div>
                    <table>
                        <thead><tr><th>Document ID</th><th>Category/Type</th><th>Ref Number</th><th>Issue Date</th><th>Expiry Date</th><th>Status</th></tr></thead>
                        <tbody>${docsHtml || '<tr><td colspan="6">No documents submitted.</td></tr>'}</tbody>
                    </table>
                </div>

                ${ubosHtml}
            `;
        }

        function closeModal() {
            document.getElementById('cust-modal').style.display = 'none';
        }

        async function loadAlerts() {
            const res = await fetch('/api/alerts');
            const data = await res.json();
            const tbody = document.getElementById('alerts-tbody');
            tbody.innerHTML = '';
            data.alerts.forEach(a => {
                const tr = document.createElement('tr');
                const sevBadge = a.severity === 'CRITICAL' ? 'badge-red' : (a.severity === 'HIGH' ? 'badge-yellow' : 'badge-blue');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #60a5fa;">${a.alert_id}</td>
                    <td>${a.customer_id}</td>
                    <td><strong>${a.alert_type}</strong></td>
                    <td>${a.lead_time_days < 0 ? `<span style="color: #f87171; font-weight: 600;">${Math.abs(a.lead_time_days)} days overdue</span>` : `${a.lead_time_days} days`}</td>
                    <td><span class="badge ${sevBadge}">${a.severity}</span></td>
                    <td><span class="badge badge-purple">${a.alert_status}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }

        async function loadReviews() {
            const res = await fetch('/api/reviews');
            const data = await res.json();
            const tbody = document.getElementById('reviews-tbody');
            tbody.innerHTML = '';
            data.reviews.forEach(r => {
                const tr = document.createElement('tr');
                const stBadge = r.case_status === 'APPROVED' ? 'badge-green' : (r.case_status === 'CLOSED_WITHOUT_RESOLUTION' ? 'badge-red' : 'badge-yellow');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #60a5fa;">${r.case_id}</td>
                    <td>${r.customer_id}</td>
                    <td>${r.review_type}</td>
                    <td>${r.scheduled_date}</td>
                    <td>${r.due_date}</td>
                    <td><span class="badge ${stBadge}">${r.case_status}</span></td>
                    <td>${r.resolution_outcome || '<em style="color: #94a3b8;">Pending</em>'}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        async function runComplianceBenchmark() {
            const tbody = document.getElementById('benchmark-tbody');
            tbody.innerHTML = '<tr><td colspan="8">Executing audit queries and checking ground truth...</td></tr>';
            const res = await fetch('/api/compliance-audit');
            const data = await res.json();
            document.getElementById('bm-precision').innerText = (data.overall_precision * 100).toFixed(1) + '%';
            document.getElementById('bm-recall').innerText = (data.overall_recall * 100).toFixed(1) + '%';
            document.getElementById('bm-f1').innerText = (data.f1_score * 100).toFixed(1) + '%';

            tbody.innerHTML = '';
            for (const [k, v] of Object.entries(data.breakdown)) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${k}</strong></td>
                    <td>${v.ground_truth_count}</td>
                    <td>${v.detected_count}</td>
                    <td><span style="color: #34d399; font-weight: 600;">${v.true_positives}</span></td>
                    <td><span style="color: #f87171; font-weight: 600;">${v.false_positives}</span></td>
                    <td>${(v.precision * 100).toFixed(1)}%</td>
                    <td>${(v.recall * 100).toFixed(1)}%</td>
                    <td><span class="badge badge-purple">${(v.f1_score * 100).toFixed(1)}%</span></td>
                `;
                tbody.appendChild(tr);
            }
        }

        async function loadAuditTrail() {
            const res = await fetch('/api/audit');
            const data = await res.json();
            const tbody = document.getElementById('audit-tbody');
            tbody.innerHTML = '';
            data.audit_events.forEach(e => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #60a5fa;">${e.event_id}</td>
                    <td>${e.entity_type}:${e.entity_id}</td>
                    <td><span class="badge badge-blue">${e.actor_role}</span></td>
                    <td>${e.event_type}</td>
                    <td>${e.old_state ? `${e.old_state} &rarr; ` : ''}<strong>${e.new_state}</strong></td>
                    <td style="font-size: 12px; color: var(--text-muted);">${e.change_reason}</td>
                    <td style="font-size: 11px; white-space: nowrap;">${e.timestamp}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        window.onclick = function(event) {
            const modal = document.getElementById('cust-modal');
            if (event.target == modal) { modal.style.display = "none"; }
        }

        async function submitLiveOnboard() {
            const body = {
                legal_name: document.getElementById('live-onb-name').value || 'Apex Global Corp',
                customer_type_code: document.getElementById('live-onb-type').value,
                tax_id: document.getElementById('live-onb-tax').value || 'US-TX-998800',
                jurisdiction: document.getElementById('live-onb-juris').value,
                date_of_birth_or_inc: document.getElementById('live-onb-dob').value,
            };
            const res = await fetch('/api/pipeline/onboard', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            const data = await res.json();
            const el = document.getElementById('live-onb-result');
            el.style.display = 'block';
            el.innerText = JSON.stringify(data, null, 2);
            document.getElementById('live-up-cust').value = data.customer_id;
            loadStats();
            loadCustomers();
        }

        async function submitLiveEvidence() {
            const custId = document.getElementById('live-up-cust').value;
            if (!custId) { alert('Please enter target customer ID'); return; }
            const body = {
                customer_id: custId,
                document_category: document.getElementById('live-up-cat').value,
                document_type: document.getElementById('live-up-type').value || (document.getElementById('live-up-cat').value === 'IDENTITY' ? 'PASSPORT' : 'BANK_STATEMENT'),
                document_reference_number: document.getElementById('live-up-ref').value || ('REF-' + Math.floor(Math.random()*900000+100000)),
                issue_date: document.getElementById('live-up-issue').value,
                expiry_date: document.getElementById('live-up-expiry').value,
            };
            const res = await fetch('/api/pipeline/upload', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            const data = await res.json();
            const el = document.getElementById('live-up-result');
            el.style.display = 'block';
            el.innerText = JSON.stringify(data, null, 2);
            loadStats();
            loadCustomers();
        }

        async function advanceTimeMachine(days) {
            const res = await fetch('/api/pipeline/advance-time', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ days: days })
            });
            const data = await res.json();
            const el = document.getElementById('time-machine-result');
            el.style.display = 'block';
            el.innerText = JSON.stringify(data, null, 2);
            loadStats();
        }

        async function triggerBatchSurveillance() {
            const res = await fetch('/api/pipeline/surveillance', { method: 'POST' });
            const data = await res.json();
            const el = document.getElementById('time-machine-result');
            el.style.display = 'block';
            el.innerText = JSON.stringify(data, null, 2);
            loadStats();
        }

        // Initial fetch
        loadStats();
        loadCustomers();
    </script>
</body>
</html>
"""
        self._send_html(html)


def run_server(port: int = 8501):
    candidate_ports = [port, 8000, 8888, 5000, 3000, 8090]
    httpd = None
    selected_port = port

    for p in candidate_ports:
        try:
            server_address = ("", p)
            httpd = HTTPServer(server_address, KYCRequestHandler)
            selected_port = p
            break
        except OSError as e:
            if p == port:
                print(f"[!] Warning: Port {p} is currently occupied by another service (e.g., Oracle XE, Tomcat, or another web server).")
            continue

    if not httpd:
        print(f"[!] Error: Unable to bind to any candidate port ({candidate_ports}).")
        return

    print("=" * 70)
    print(" KYC ONBOARDING & EVIDENCE LIFECYCLE PLATFORM")
    print(f" [*] Dashboard Server successfully running!")
    print(f" [*] URL: http://localhost:{selected_port}")
    print("=" * 70)
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    run_server(8501)
