"""
ImageSense - SMME Schema Templates & Accounting Export Generators
Provides standardized schemas for key SMME industries:
- Retail & Invoicing (Delivery notes, supplier invoices, cash slips)
- Logistics & Courier (Proof of Delivery POD, waybills, driver logbooks)
- Medical / Dental Clinics (Lab test results, patient rosters)
- Construction & Contracting (Timesheets, hardware slips, job costing)
- Education & Tutoring (Attendance registers, grade rosters)
- Bank Statements & Accounting Transactions
- Generic Grid

Also provides direct export formatters for leading SME accounting packages:
- Sage Pastel / Sage Business Cloud
- Xero
- QuickBooks Online
"""

import os
import re
import csv
from typing import List, Dict, Any, Optional, Tuple


SCHEMAS: Dict[str, Dict[str, Any]] = {
    "retail_invoice": {
        "id": "retail_invoice",
        "name": "Retail & Supplier Invoice",
        "sector": "Retail, Spaza, Wholesale & Convenience",
        "description": "Supplier delivery notes, cash till slips, invoices with inventory lines",
        "columns": ["Item Code", "Description", "Quantity", "Unit Price", "VAT / Tax", "Total"],
        "aliases": {
            "Item Code": ["code", "sku", "item", "part", "ref", "prd", "id", "barcode"],
            "Description": ["description", "desc", "details", "item name", "product", "particulars"],
            "Quantity": ["qty", "quantity", "count", "units", "pcs", "volume", "qnty"],
            "Unit Price": ["unit price", "price", "rate", "cost", "unit cost", "unit rate"],
            "VAT / Tax": ["vat", "tax", "tax amt", "vat amt", "gst"],
            "Total": ["total", "amount", "line total", "ext price", "subtotal", "amt", "inclusive"]
        },
        "math_rule": "Quantity * Unit Price == Total"
    },
    "logistics_waybill": {
        "id": "logistics_waybill",
        "name": "Logistics & Proof of Delivery (POD)",
        "sector": "Logistics, Couriers & Transport",
        "description": "Signed waybills, delivery confirmation dockets, driver logbooks",
        "columns": ["Waybill #", "Recipient Name", "Timestamp / Date", "Destination", "Status"],
        "aliases": {
            "Waybill #": ["waybill", "waybill #", "tracking #", "pod #", "consignment", "docket"],
            "Recipient Name": ["recipient", "receiver", "customer", "received by", "consignee", "name"],
            "Timestamp / Date": ["date", "time", "timestamp", "delivery date", "received on"],
            "Destination": ["destination", "address", "delivery address", "drop off", "location"],
            "Status": ["status", "condition", "delivery status", "remarks", "sign"]
        },
        "math_rule": None
    },
    "medical_clinic": {
        "id": "medical_clinic",
        "name": "Medical & Clinic Lab Results",
        "sector": "Medical, Dental & Diagnostics",
        "description": "Scanned pathology results, paper patient intake records, medicine lists",
        "columns": ["Date", "Test / Marker", "Measured Value", "Unit", "Reference Range"],
        "aliases": {
            "Date": ["date", "test date", "collected", "reported"],
            "Test / Marker": ["test", "marker", "investigation", "parameter", "analyte", "examination"],
            "Measured Value": ["result", "value", "measured value", "reading", "observed"],
            "Unit": ["unit", "units", "uom", "metric"],
            "Reference Range": ["reference", "range", "ref range", "normal range", "interval"]
        },
        "math_rule": None
    },
    "construction_timesheet": {
        "id": "construction_timesheet",
        "name": "Construction & Timesheet Dockets",
        "sector": "Construction, Contracting & Trades",
        "description": "Site timesheets, material receipt slips, hardware dockets, job costing",
        "columns": ["Worker ID / Name", "Date", "Site / Job Name", "Hours / Qty", "Rate / Unit Cost", "Total"],
        "aliases": {
            "Worker ID / Name": ["worker", "employee", "name", "id", "staff", "technician", "operator"],
            "Date": ["date", "day", "work date"],
            "Site / Job Name": ["site", "job", "project", "location", "cost code"],
            "Hours / Qty": ["hours", "hrs", "qty", "quantity", "worked", "units"],
            "Rate / Unit Cost": ["rate", "hourly rate", "unit price", "cost", "unit cost"],
            "Total": ["total", "amount", "cost total", "pay", "line cost"]
        },
        "math_rule": "Hours / Qty * Rate / Unit Cost == Total"
    },
    "education_register": {
        "id": "education_register",
        "name": "Education Attendance & Rosters",
        "sector": "Education, Schools & Tutoring Centres",
        "description": "Attendance registers, physical grade sheets, test score rosters",
        "columns": ["Student ID", "Student Name", "Test 1 / Date", "Test 2 / Status", "Final Grade / Result"],
        "aliases": {
            "Student ID": ["student id", "id", "roll no", "adm #", "student #"],
            "Student Name": ["student name", "name", "full name", "learner"],
            "Test 1 / Date": ["test 1", "score 1", "session 1", "assignment 1", "attendance"],
            "Test 2 / Status": ["test 2", "score 2", "session 2", "exam", "status"],
            "Final Grade / Result": ["final grade", "grade", "total score", "result", "mark", "average"]
        },
        "math_rule": None
    },
    "bank_statement": {
        "id": "bank_statement",
        "name": "Bank Statement / Financial Transactions",
        "sector": "Finance, Accounting & Bookkeeping",
        "description": "Bank account statements, merchant settlements, cashbook entries",
        "columns": ["Date", "Description", "Debit / Paid Out", "Credit / Paid In", "Balance"],
        "aliases": {
            "Date": ["date", "trans date", "posting date", "value date"],
            "Description": ["description", "narrative", "details", "reference", "particulars", "trans details"],
            "Debit / Paid Out": ["debit", "paid out", "payments", "dr", "withdrawals"],
            "Credit / Paid In": ["credit", "paid in", "deposits", "cr", "receipts"],
            "Balance": ["balance", "running balance", "closing balance"]
        },
        "math_rule": None
    },
    "generic": {
        "id": "generic",
        "name": "Generic Table / Custom Document",
        "sector": "General Business Documents",
        "description": "Flexible grid with auto-detected headers and layout",
        "columns": [],
        "aliases": {},
        "math_rule": None
    },
    "xero_bill": {
        "id": "xero_bill",
        "name": "Xero Bill Import Format",
        "sector": "Accounting & ERP",
        "description": "Official Xero Bill & Supplier Invoice CSV Import specification",
        "columns": [
            "*ContactName", "*InvoiceNumber", "*InvoiceDate", "*DueDate", "Total",
            "InventoryItemCode", "*Description", "*Quantity", "*UnitAmount", "*AccountCode", "*TaxType"
        ],
        "aliases": {
            "*ContactName": ["contact name", "supplier", "vendor", "payee", "company", "creditor", "biller", "from", "contact"],
            "*InvoiceNumber": ["invoice number", "inv no", "bill no", "reference", "doc #", "inv #", "invoice #", "bill #"],
            "*InvoiceDate": ["invoice date", "bill date", "date", "issued date", "trans date"],
            "*DueDate": ["due date", "payment due", "terms date", "expiry"],
            "Total": ["total", "line total", "total amount", "amount", "gross", "inclusive"],
            "InventoryItemCode": ["item code", "sku", "item #", "code", "part no", "product code"],
            "*Description": ["description", "desc", "details", "item desc", "product", "particulars", "line description"],
            "*Quantity": ["quantity", "qty", "count", "units", "pcs", "qnty"],
            "*UnitAmount": ["unit amount", "unit price", "price", "rate", "cost", "unit cost"],
            "*AccountCode": ["account code", "account", "gl code", "chart of accounts", "nominal code", "ledger"],
            "*TaxType": ["tax type", "vat type", "tax rate", "tax code", "tax"]
        },
        "math_rule": "*Quantity * *UnitAmount == Total"
    },
    "quickbooks_bill": {
        "id": "quickbooks_bill",
        "name": "QuickBooks Online Bill Import",
        "sector": "Accounting & ERP",
        "description": "QuickBooks Online Bill and Expense CSV Import specification",
        "columns": [
            "*Vendor", "*InvoiceNo", "*InvoiceDate", "*DueDate", "*Terms",
            "*Location", "*Item", "*Description", "*Quantity", "*Rate", "*Amount", "*TaxCode"
        ],
        "aliases": {
            "*Vendor": ["vendor", "supplier", "payee", "contact", "company"],
            "*InvoiceNo": ["invoice no", "inv no", "bill no", "reference", "doc #", "invoice #"],
            "*InvoiceDate": ["invoice date", "bill date", "date", "trans date"],
            "*DueDate": ["due date", "payment due"],
            "*Terms": ["terms", "payment terms"],
            "*Location": ["location", "branch", "site"],
            "*Item": ["item", "item code", "sku", "product"],
            "*Description": ["description", "desc", "details", "particulars"],
            "*Quantity": ["quantity", "qty", "count", "units"],
            "*Rate": ["rate", "unit price", "price", "cost", "unit amount"],
            "*Amount": ["amount", "total", "line total"],
            "*TaxCode": ["tax code", "tax rate", "tax type", "vat"]
        },
        "math_rule": "*Quantity * *Rate == *Amount"
    }
}



def detect_schema(table_data: List[List[str]]) -> str:
    """
    Intelligently classifies document tabular structure into an SMME schema preset.
    Analyzes header row tokens, column text patterns, and numeric distributions.
    """
    if not table_data or len(table_data) < 2:
        return "generic"

    # Analyze first 2 rows for header keywords
    header_text = " ".join([str(c).lower() for r in table_data[:2] for c in r if c])
    full_text = " ".join([str(c).lower() for r in table_data for c in r if c])

    scores: Dict[str, int] = {k: 0 for k in SCHEMAS.keys() if k != "generic"}

    # Keyword weights for retail invoice
    invoice_keywords = ["qty", "quantity", "unit price", "price", "subtotal", "vat", "tax", "total", "invoice", "item", "description", "prd-", "sku"]
    for kw in invoice_keywords:
        if kw in header_text:
            scores["retail_invoice"] += 3
        elif kw in full_text:
            scores["retail_invoice"] += 1

    # Logistics waybill
    logistics_keywords = ["waybill", "tracking", "pod", "recipient", "consignee", "destination", "courier", "delivery", "proof of delivery", "driver", "docket"]
    for kw in logistics_keywords:
        if kw in header_text:
            scores["logistics_waybill"] += 3
        elif kw in full_text:
            scores["logistics_waybill"] += 1

    # Medical clinic
    medical_keywords = ["test", "marker", "analyte", "reference range", "measured", "uom", "specimen", "pathology", "clinic", "lab", "serum", "mg/dl", "mmol/l"]
    for kw in medical_keywords:
        if kw in header_text:
            scores["medical_clinic"] += 3
        elif kw in full_text:
            scores["medical_clinic"] += 1

    # Construction timesheet
    construction_keywords = ["worker", "hours worked", "site", "job costing", "contractor", "hourly rate", "hardware", "material", "timesheet", "docket", "labor", "plant"]
    for kw in construction_keywords:
        if kw in header_text:
            scores["construction_timesheet"] += 3
        elif kw in full_text:
            scores["construction_timesheet"] += 1

    # Education roster
    education_keywords = ["student", "grade", "attendance", "roster", "exam", "roll no", "learner", "score", "mark", "term", "tutor", "homework"]
    for kw in education_keywords:
        if kw in header_text:
            scores["education_register"] += 3
        elif kw in full_text:
            scores["education_register"] += 1

    # Bank statement
    bank_keywords = ["debit", "credit", "balance", "statement", "paid out", "paid in", "transaction date", "withdrawal", "deposit", "cheque", "ledger"]
    for kw in bank_keywords:
        if kw in header_text:
            scores["bank_statement"] += 3
        elif kw in full_text:
            scores["bank_statement"] += 1

    # Find highest score with a threshold
    best_schema = "generic"
    max_score = 0
    for schema_id, score in scores.items():
        if score > max_score and score >= 3:
            max_score = score
            best_schema = schema_id

    return best_schema


def levenshtein_sim(s1: str, s2: str) -> float:
    """
    Computes normalized Levenshtein similarity in [0.0, 1.0].
    Returns 1.0 for identical strings, 0.0 for completely disjoint strings.
    """
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    m, n = len(s1), len(s2)
    if m == 0 or n == 0:
        return 0.0

    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = temp
    dist = dp[n]
    max_len = max(m, n)
    return round(max(0.0, 1.0 - (dist / max_len)), 3)


def fuzzy_match_header(
    header: str,
    target_field: str,
    aliases: List[str]
) -> Tuple[float, str]:
    """
    Evaluates fuzzy match confidence between a detected table header and a schema field.
    Returns (confidence_score: float in [0.0, 1.0], matched_alias_or_field: str).
    """
    clean_h = re.sub(r"[^\w\s]", " ", header.lower()).strip()
    clean_target = re.sub(r"[^\w\s]", " ", target_field.lower()).strip()

    if clean_h == clean_target:
        return 1.0, target_field

    all_aliases = [clean_target] + [re.sub(r"[^\w\s]", " ", a.lower()).strip() for a in aliases]
    best_score = 0.0
    best_alias = target_field

    clean_h_alphanumeric = re.sub(r"[\W_]+", "", header.lower())

    for alias in all_aliases:
        if not alias:
            continue
        # Exact alias match
        if clean_h == alias:
            return 0.98, alias

        # Alphanumeric equality (handles punctuation noise like "Qt.y" -> "qty", "Total:" -> "total")
        alias_alphanumeric = re.sub(r"[\W_]+", "", alias.lower())
        if clean_h_alphanumeric and clean_h_alphanumeric == alias_alphanumeric:
            return 0.96, alias

        # Substring / token containment
        if alias in clean_h or clean_h in alias:
            if re.search(r'\b' + re.escape(alias) + r'\b', clean_h):
                score = 0.92
            else:
                score = 0.85
            if score > best_score:
                best_score = score
                best_alias = alias

        # Character-level edit similarity (handles OCR typos e.g. "qt.y", "pr1ce", "unlt")
        sim_raw = levenshtein_sim(clean_h, alias)
        sim_alpha = levenshtein_sim(clean_h_alphanumeric, alias_alphanumeric) if clean_h_alphanumeric and alias_alphanumeric else 0.0
        sim = max(sim_raw, sim_alpha)
        if sim >= 0.70:
            weighted = round(0.75 + (sim - 0.70) * 0.80, 3)
            if weighted > best_score:
                best_score = min(0.95, weighted)
                best_alias = alias

    return round(best_score, 3), best_alias


def map_columns_to_schema_with_confidence(
    headers: List[str],
    schema_id: str,
    custom_aliases: Optional[Dict[str, List[str]]] = None,
    min_confidence: float = 0.50
) -> Dict[str, Any]:
    """
    Maps detected table headers to canonical schema columns using fuzzy similarity scoring.
    Returns comprehensive mapping details including per-header confidence ratings and status flags.
    """
    schema = SCHEMAS.get(schema_id, SCHEMAS["generic"])
    canonical_cols = schema.get("columns", [])
    aliases = {col: list(alias_list) for col, alias_list in schema.get("aliases", {}).items()}

    # Merge custom user aliases if supplied (supporting exact, case-insensitive, or snake_case keys)
    if custom_aliases:
        for k, v in custom_aliases.items():
            clean_k = re.sub(r"[\W_]+", "", k.lower())
            matched_canonical = None
            for col in canonical_cols:
                if col == k or re.sub(r"[\W_]+", "", col.lower()) == clean_k:
                    matched_canonical = col
                    break
            target_key = matched_canonical or k
            if target_key in aliases:
                aliases[target_key] = list(set(aliases[target_key] + v))
            else:
                aliases[target_key] = list(v)

    mapping: Dict[str, Optional[int]] = {col: None for col in canonical_cols}
    header_confidences: Dict[str, Dict[str, Any]] = {}
    used_indices = set()

    # Score each (canonical_col, header_index) pair
    candidate_matches = []
    for col in canonical_cols:
        col_aliases = aliases.get(col, [])
        for idx, h in enumerate(headers):
            score, matched_alias = fuzzy_match_header(str(h), col, col_aliases)
            if score >= min_confidence:
                candidate_matches.append((score, col, idx, str(h), matched_alias))

    # Greedy assignment from highest confidence to lowest
    candidate_matches.sort(key=lambda x: x[0], reverse=True)
    assigned_cols = set()

    for score, col, idx, h_text, matched_alias in candidate_matches:
        if col in assigned_cols or idx in used_indices:
            continue
        mapping[col] = idx
        assigned_cols.add(col)
        used_indices.add(idx)

        status = "HIGH_CONFIDENCE" if score >= 0.85 else ("MODERATE" if score >= 0.65 else "LOW_CONFIDENCE")
        header_confidences[col] = {
            "mapped_index": idx,
            "detected_header": h_text,
            "matched_alias": matched_alias,
            "confidence": score,
            "status": status
        }

    # Record unmapped canonical columns
    for col in canonical_cols:
        if col not in assigned_cols:
            header_confidences[col] = {
                "mapped_index": None,
                "detected_header": None,
                "matched_alias": None,
                "confidence": 0.0,
                "status": "UNMAPPED"
            }

    # Ordinal fallback for remaining unmapped if counts align
    for idx, col in enumerate(canonical_cols):
        if mapping[col] is None and idx < len(headers) and idx not in used_indices:
            mapping[col] = idx
            used_indices.add(idx)
            header_confidences[col] = {
                "mapped_index": idx,
                "detected_header": str(headers[idx]),
                "matched_alias": "ordinal_position_fallback",
                "confidence": 0.40,
                "status": "ORDINAL_FALLBACK"
            }

    unmapped_headers = [headers[i] for i in range(len(headers)) if i not in used_indices]

    valid_scores = [d["confidence"] for d in header_confidences.values() if d["mapped_index"] is not None]
    overall_conf = round(sum(valid_scores) / max(len(canonical_cols), 1), 2) if canonical_cols else 1.0

    return {
        "mapping": mapping,
        "header_confidences": header_confidences,
        "confidence_map": header_confidences,
        "overall_mapping_confidence": overall_conf,
        "overall_confidence": overall_conf,
        "unmapped_headers": unmapped_headers,
        "schema_id": schema_id,
        "schema_name": schema.get("name", "Generic")
    }


def map_columns_to_schema(
    headers: List[str],
    schema_id: str,
    custom_aliases: Optional[Dict[str, List[str]]] = None
) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """
    Backward-compatible wrapper mapping detected table headers to canonical schema columns.
    Returns (mapping: Dict[str, Optional[int]], unmapped_headers: List[str]).
    """
    res = map_columns_to_schema_with_confidence(headers, schema_id, custom_aliases=custom_aliases)
    return res["mapping"], res["unmapped_headers"]



# ---------------------------------------------------------------------------
# Direct Accounting Software Export Templates
# ---------------------------------------------------------------------------

def export_to_sage_pastel_csv(
    table_data: List[List[str]],
    output_path: str,
    doc_type: str = "Tax Invoice",
    customer_code: str = "CASH001"
) -> str:
    """
    Generates a Sage Pastel / Sage Business Cloud compatible CSV file.
    Format adheres to Sage Pastel partner/cloud lines:
    [Header/Line Flag, Customer/Supplier Code, Document Date, Document Number, Item Code, Description, Quantity, Unit Price, Inclusive, Tax Type]
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    mapping, _ = map_columns_to_schema(table_data[0] if table_data else [], "retail_invoice")
    rows = table_data[1:] if len(table_data) > 1 else []

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Sage Header Definition
        writer.writerow([
            "RecordType", "AccountCode", "Date", "Reference",
            "ItemCode", "Description", "Quantity", "UnitPrice", "TaxType", "LineTotal"
        ])

        for r_idx, row in enumerate(rows, start=1):
            def get_col(canonical_name: str, default: str = "") -> str:
                idx = mapping.get(canonical_name)
                if idx is not None and idx < len(row):
                    return str(row[idx]).strip()
                return default

            item_code = get_col("Item Code", f"ITEM{r_idx:03d}")
            desc = get_col("Description", f"Line Item {r_idx}")
            raw_qty = get_col("Quantity", "1")
            raw_price = get_col("Unit Price", "0.00")
            raw_total = get_col("Total", "0.00")

            # Clean numeric values
            clean_qty = re.sub(r"[^\d.]", "", raw_qty) or "1"
            clean_price = re.sub(r"[^\d.]", "", raw_price.replace(",", "")) or "0.00"
            clean_total = re.sub(r"[^\d.]", "", raw_total.replace(",", "")) or "0.00"

            writer.writerow([
                "LINE", customer_code, "", f"INV-{r_idx}",
                item_code, desc, clean_qty, clean_price, "Standard Rate (15%)", clean_total
            ])

    return output_path


def export_to_xero_csv(
    table_data: List[List[str]],
    output_path: str,
    contact_name: str = "Standard Supplier",
    invoice_number: str = "INV-OCR-001",
    invoice_date: str = ""
) -> str:
    """
    Generates a Xero Bill / Invoice Import CSV file.
    Official Xero Format:
    *ContactName, EmailAddress, POAddressLine1, *InvoiceNumber, Reference,
    *InvoiceDate, *DueDate, Total, InventoryItemCode, *Description, *Quantity,
    *UnitAmount, Discount, *AccountCode, *TaxType
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    mapping, _ = map_columns_to_schema(table_data[0] if table_data else [], "retail_invoice")
    rows = table_data[1:] if len(table_data) > 1 else []

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "*ContactName", "EmailAddress", "POAddressLine1", "*InvoiceNumber", "Reference",
            "*InvoiceDate", "*DueDate", "Total", "InventoryItemCode", "*Description",
            "*Quantity", "*UnitAmount", "Discount", "*AccountCode", "*TaxType"
        ])

        for r_idx, row in enumerate(rows, start=1):
            def get_col(canonical_name: str, default: str = "") -> str:
                idx = mapping.get(canonical_name)
                if idx is not None and idx < len(row):
                    return str(row[idx]).strip()
                return default

            item_code = get_col("Item Code", "")
            desc = get_col("Description", f"Item {r_idx}")
            raw_qty = get_col("Quantity", "1")
            raw_price = get_col("Unit Price", "0.00")
            raw_total = get_col("Total", "")

            clean_qty = re.sub(r"[^\d.]", "", raw_qty) or "1"
            clean_price = re.sub(r"[^\d.]", "", raw_price.replace(",", "")) or "0.00"

            writer.writerow([
                contact_name, "", "", invoice_number, "ImageSense-OCR",
                invoice_date, "", raw_total, item_code, desc,
                clean_qty, clean_price, "", "200", "Tax on Purchases"
            ])

    return output_path


def export_to_quickbooks_csv(
    table_data: List[List[str]],
    output_path: str,
    vendor_name: str = "Supplier",
    invoice_no: str = "BILL-001",
    invoice_date: str = ""
) -> str:
    """
    Generates a QuickBooks Online Bill / Expense Import CSV file.
    Format:
    *Vendor, *InvoiceNo, *InvoiceDate, *DueDate, *Terms, *Location,
    *Item, *Description, *Quantity, *Rate, *Amount, *TaxCode
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    mapping, _ = map_columns_to_schema(table_data[0] if table_data else [], "retail_invoice")
    rows = table_data[1:] if len(table_data) > 1 else []

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "*Vendor", "*InvoiceNo", "*InvoiceDate", "*DueDate", "*Terms",
            "*Location", "*Item", "*Description", "*Quantity", "*Rate", "*Amount", "*TaxCode"
        ])

        for r_idx, row in enumerate(rows, start=1):
            def get_col(canonical_name: str, default: str = "") -> str:
                idx = mapping.get(canonical_name)
                if idx is not None and idx < len(row):
                    return str(row[idx]).strip()
                return default

            item_code = get_col("Item Code", f"ITEM-{r_idx}")
            desc = get_col("Description", f"Service/Good {r_idx}")
            raw_qty = get_col("Quantity", "1")
            raw_price = get_col("Unit Price", "0.00")
            raw_total = get_col("Total", "0.00")

            clean_qty = re.sub(r"[^\d.]", "", raw_qty) or "1"
            clean_price = re.sub(r"[^\d.]", "", raw_price.replace(",", "")) or "0.00"
            clean_total = re.sub(r"[^\d.]", "", raw_total.replace(",", "")) or "0.00"

            writer.writerow([
                vendor_name, invoice_no, invoice_date, "", "Net 30",
                "Main", item_code, desc, clean_qty, clean_price, clean_total, "Standard"
            ])

    return output_path
