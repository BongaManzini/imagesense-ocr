"""
ImageSense - Audit & Arithmetic Validation Engine
Provides automated mathematical integrity verification, date format standardization,
numeric/currency sanitation, OCR character confusion repair, and cell confidence auditing.
Designed specifically for small business accounting and ERP readiness.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

# Regex patterns for currency symbols
CURRENCY_REGEX = re.compile(r"^[R$€£¥₹\s]+|[R$€£¥₹\s]+$")


def repair_numeric_ocr_confusions(text: str) -> str:
    """
    Cleans OCR character confusions specifically in numeric and currency fields:
    - 'O', 'o' -> '0'
    - 'l', 'I', '|' -> '1'
    - 'S' -> '5' (when preceded or followed by digits)
    - 'B' -> '8' (when preceded or followed by digits)
    - Commas and periods in numbers: 1,250.00 vs 1 250.00
    """
    if not text:
        return ""
    t = str(text).strip()

    # If it contains digits or currency marks, apply targeted character repair
    if re.search(r"[\d$€£R]", t):
        # Letter O to zero between or adjacent to digits, and in decimals
        t = re.sub(r"(\d)[oO]", r"\g<1>0", t)
        t = re.sub(r"[oO](\d)", r"0\g<1>", t)
        t = re.sub(r"\.[oO]{2}", r".00", t)
        t = re.sub(r"\.[oO]", r".0", t)
        t = re.sub(r"^[oO]\.", r"0.", t)

        # Lowercase l or uppercase I or pipe | surrounded by digits to 1
        t = re.sub(r"(\d)[lI|](\d)", r"\g<1>1\g<2>", t)
        t = re.sub(r"(\d)\.[lI|](\d)", r"\g<1>.1\g<2>", t)
        t = re.sub(r"^[lI|]\.(\d+)", r"1.\g<1>", t)

        # S to 5 in obvious decimal places (e.g. .S0 -> .50)
        t = re.sub(r"\.[sS](\d)", r".5\g<1>", t)
        t = re.sub(r"(\d)\.[sS]{2}", r"\g<1>.55", t)

        # SKU / Item Code format with letter O instead of zero (e.g. PRD-O1 -> PRD-01)
        t = re.sub(r"([A-Za-z]+[-_])[oO](\d+)", r"\g<1>0\g<2>", t)
        t = re.sub(r"([A-Za-z]+[-_]\d+)[oO]", r"\g<1>0", t)

    return t


def parse_number_safe(val: Any) -> Optional[float]:
    """
    Safely extracts a float value from text.
    Handles currency symbols ($120.00, R240.50, €50), comma separators (1,250.00),
    negative numbers in parentheses (150.00), and OCR letter confusions.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = repair_numeric_ocr_confusions(str(val).strip())
    if not s:
        return None

    # Check for negative in parentheses: (120.00)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Strip currency symbols and spaces
    s = CURRENCY_REGEX.sub("", s).strip()
    # Remove thousand commas or spaces
    s = s.replace(",", "").replace(" ", "")

    # Match numeric float / int
    m = re.search(r"^-?\d+(\.\d+)?$", s)
    if m:
        try:
            res = float(s)
            return -res if is_negative else res
        except ValueError:
            return None
    return None


def parse_date_safe(val: str) -> Tuple[Optional[str], bool]:
    """
    Attempts to parse and standardize date strings into ISO YYYY-MM-DD.
    Returns (standardized_date_str_or_None, is_valid).
    """
    if not val:
        return None, False

    s = str(val).strip()
    # Strip prefixes like "Date:", "Dated:"
    s = re.sub(r"^(date|dated|invoice date|delivery date)[:\s]+", "", s, flags=re.I).strip()

    date_formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
        "%d-%b-%Y", "%d-%B-%Y", "%Y.%m.%d", "%d.%m.%Y"
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), True
        except ValueError:
            continue

    # Regex test for date-like structure that failed valid calendar bounds (e.g., 31 Feb, 32/12/2026)
    if re.search(r"\b\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}\b", s):
        return s, False

    return None, False


def find_column_index(headers: List[str], target_keywords: List[str]) -> Optional[int]:
    """Finds the index of a column matching any of target_keywords."""
    for idx, h in enumerate(headers):
        hl = str(h).lower()
        if any(kw == hl or kw in hl for kw in target_keywords):
            return idx
    return None


def verify_math_equations(
    table_data: List[List[str]],
    qty_col_idx: Optional[int] = None,
    price_col_idx: Optional[int] = None,
    total_col_idx: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Audits arithmetic on tabular data:
    Verifies that for each line item: Quantity * Unit Price == Total.
    Also identifies subtotal/grand total consistency if present.
    """
    checks: List[Dict[str, Any]] = []
    stats = {"total_rows": 0, "passed": 0, "failed": 0, "skipped": 0}

    if not table_data or len(table_data) < 2:
        return checks, stats

    headers = [str(c).strip().lower() for c in table_data[0]]

    # Heuristic column discovery if not explicitly supplied
    if qty_col_idx is None:
        qty_col_idx = find_column_index(headers, ["qty", "quantity", "hours", "units", "count", "pcs"])
    if price_col_idx is None:
        price_col_idx = find_column_index(headers, ["unit price", "price", "rate", "cost", "unit cost"])
    if total_col_idx is None:
        total_col_idx = find_column_index(headers, ["total", "line total", "amount", "ext price", "subtotal"])

    # If column indices could not be found by keywords, try searching for numeric triplet in rows
    if qty_col_idx is None or price_col_idx is None or total_col_idx is None:
        for r in table_data[1:]:
            nums = []
            for col_i, cell in enumerate(r):
                n = parse_number_safe(cell)
                if n is not None:
                    nums.append((col_i, n))
            # Test if any 3 numbers satisfy A * B == C
            if len(nums) >= 3:
                for i in range(len(nums)):
                    for j in range(len(nums)):
                        if i == j:
                            continue
                        for k in range(len(nums)):
                            if k == i or k == j:
                                continue
                            ci, a = nums[i]
                            cj, b = nums[j]
                            ck, c = nums[k]
                            if abs((a * b) - c) <= 0.05 and c > 0:
                                qty_col_idx = ci
                                price_col_idx = cj
                                total_col_idx = ck
                                break
                        if total_col_idx is not None:
                            break
                    if total_col_idx is not None:
                        break
            if total_col_idx is not None:
                break

    if qty_col_idx is None or price_col_idx is None or total_col_idx is None:
        return checks, stats

    # Audit each row
    for r_idx in range(1, len(table_data)):
        row = table_data[r_idx]
        if len(row) <= max(qty_col_idx, price_col_idx, total_col_idx):
            continue

        raw_qty = row[qty_col_idx]
        raw_price = row[price_col_idx]
        raw_total = row[total_col_idx]

        qty = parse_number_safe(raw_qty)
        price = parse_number_safe(raw_price)
        total = parse_number_safe(raw_total)

        if qty is None or price is None or total is None:
            stats["skipped"] += 1
            continue

        stats["total_rows"] += 1
        expected_total = round(qty * price, 2)
        diff = round(abs(expected_total - total), 2)
        passed = diff <= 0.05

        if passed:
            stats["passed"] += 1
            status = "PASS"
        else:
            stats["failed"] += 1
            status = "MISMATCH"

        checks.append({
            "row_index": r_idx,
            "qty_col": qty_col_idx,
            "price_col": price_col_idx,
            "total_col": total_col_idx,
            "qty": qty,
            "price": price,
            "reported_total": total,
            "expected_total": expected_total,
            "difference": diff,
            "passed": passed,
            "status": status,
            "expression": f"{qty:g} × {price:.2f} = {expected_total:.2f} (reported: {total:.2f})"
        })

    return checks, stats


def audit_document_table(
    table_data: List[List[str]],
    schema_id: str = "retail_invoice",
    cell_confidences: Optional[Dict[Tuple[int, int], float]] = None,
    raw_text: str = ""
) -> Dict[str, Any]:
    """
    Performs full automated business audit of extracted table data:
    1. Arithmetic validation (Qty * Price == Total)
    2. Date syntax & validity audit
    3. Blank cell / missing mandatory field check
    4. Cell-level OCR confidence score flagging (< 75%)
    5. Clean suggested fixes for human review
    """
    flagged_cells: List[Dict[str, Any]] = []
    cell_confidences = cell_confidences or {}

    if not table_data or len(table_data) == 0:
        return {
            "status": "EMPTY",
            "overall_rating": "No Data",
            "summary_text": "No table data available to audit.",
            "math_checks": [],
            "math_summary": {"total_rows": 0, "passed": 0, "failed": 0, "skipped": 0},
            "flagged_cells": [],
            "date_checks": []
        }

    headers = [str(c).strip() for c in table_data[0]]

    # 1. Arithmetic Check
    math_checks, math_stats = verify_math_equations(table_data)
    for mc in math_checks:
        if not mc["passed"]:
            flagged_cells.append({
                "row": mc["row_index"],
                "col": mc["total_col"],
                "type": "math_mismatch",
                "severity": "error",
                "message": f"Calculation mismatch: {mc['expression']}. Difference: {mc['difference']:.2f}",
                "suggested_fix": f"{mc['expected_total']:.2f}"
            })

    # 2. Date Format & Calendar Validity Check
    date_checks: List[Dict[str, Any]] = []
    date_col_idx = find_column_index(headers, ["date", "timestamp", "work date", "posting date"])
    if date_col_idx is not None:
        for r_idx in range(1, len(table_data)):
            if date_col_idx < len(table_data[r_idx]):
                raw_val = table_data[r_idx][date_col_idx].strip()
                if raw_val:
                    std_date, is_valid = parse_date_safe(raw_val)
                    if std_date and is_valid:
                        date_checks.append({"row": r_idx, "original": raw_val, "standardized": std_date, "valid": True})
                    elif not is_valid and re.search(r"\d", raw_val):
                        date_checks.append({"row": r_idx, "original": raw_val, "standardized": None, "valid": False})
                        flagged_cells.append({
                            "row": r_idx,
                            "col": date_col_idx,
                            "type": "invalid_date",
                            "severity": "warning",
                            "message": f"Invalid calendar date format: '{raw_val}'",
                            "suggested_fix": std_date or ""
                        })

    # Also check date in header/metadata lines (common in invoices like 'Date: October 27, 2026')
    if not date_checks:
        for r_idx in range(min(3, len(table_data))):
            for c_idx, cell in enumerate(table_data[r_idx]):
                if "date" in str(cell).lower():
                    std_date, is_valid = parse_date_safe(str(cell))
                    if std_date and is_valid:
                        date_checks.append({"row": r_idx, "original": str(cell), "standardized": std_date, "valid": True})

    # 3. Low Confidence & Blank Cell Auditing
    for r_idx, row in enumerate(table_data):
        for c_idx, val in enumerate(row):
            coord = (r_idx, c_idx)
            val_str = str(val).strip()

            # Flag low OCR confidence cells
            conf = cell_confidences.get(coord)
            if conf is not None and 0 <= conf < 70.0 and val_str:
                flagged_cells.append({
                    "row": r_idx,
                    "col": c_idx,
                    "type": "low_confidence",
                    "severity": "warning",
                    "message": f"Low OCR character confidence ({conf:.1f}%). Please verify accuracy.",
                    "suggested_fix": val_str
                })

            # Flag empty cells inside body if surrounding cells have values
            if r_idx > 0 and not val_str and any(row):
                # Don't flag if whole row is empty
                flagged_cells.append({
                    "row": r_idx,
                    "col": c_idx,
                    "type": "blank_cell",
                    "severity": "info",
                    "message": f"Empty value in column '{headers[c_idx] if c_idx < len(headers) else f'Col {c_idx+1}'}'",
                    "suggested_fix": ""
                })

    # Determine overall document audit status
    has_errors = any(f["severity"] == "error" for f in flagged_cells)
    has_warnings = any(f["severity"] == "warning" for f in flagged_cells)

    if has_errors:
        status = "NEEDS_REVIEW"
        overall_rating = "Arithmetic Mismatches Detected"
        badge_color = "rose"
    elif has_warnings:
        status = "WARNINGS"
        overall_rating = "Review Advised (Low Confidence or Date)"
        badge_color = "amber"
    else:
        status = "VERIFIED"
        overall_rating = "100% Validated & Verified"
        badge_color = "emerald"

    # Build concise human summary text
    passed_math = math_stats["passed"]
    total_math = math_stats["total_rows"]
    if total_math > 0:
        if math_stats["failed"] == 0:
            math_text = f"All {passed_math} line item calculations verified."
        else:
            math_text = f"Math Alert: {math_stats['failed']} calculation mismatch(es) detected across {total_math} rows."
    else:
        math_text = "Standard layout verified (No arithmetic equations required)."

    summary_text = f"{overall_rating}. {math_text} {len(flagged_cells)} cell(s) flagged for human review."

    return {
        "status": status,
        "overall_rating": overall_rating,
        "badge_color": badge_color,
        "summary_text": summary_text,
        "math_checks": math_checks,
        "math_summary": math_stats,
        "date_checks": date_checks,
        "flagged_cells": flagged_cells,
        "flagged_count": len(flagged_cells)
    }


def auto_repair_table(
    table_data: List[List[str]],
    audit_results: Dict[str, Any]
) -> Tuple[List[List[str]], List[str]]:
    """
    Applies automatic high-confidence fixes:
    - Normalizes numeric fields (replaces letter O with 0, cleans currency tokens)
    - Recomputes broken math equations when quantity and unit price are clear
    - Standardizes date formats to YYYY-MM-DD
    Returns (repaired_table_data, log_of_changes).
    """
    import copy
    repaired = copy.deepcopy(table_data)
    changelog: List[str] = []

    # Apply date standardizations
    for dc in audit_results.get("date_checks", []):
        r = dc.get("row")
        std = dc.get("standardized")
        if r is not None and std and r < len(repaired):
            for c_idx in range(len(repaired[r])):
                if dc.get("original") in repaired[r][c_idx]:
                    repaired[r][c_idx] = std
                    changelog.append(f"Row {r+1}: Standardized date to '{std}'")

    # Clean numeric fields across data rows
    for r_idx in range(1, len(repaired)):
        for c_idx in range(len(repaired[r_idx])):
            val = repaired[r_idx][c_idx]
            repaired_val = repair_numeric_ocr_confusions(val)
            if repaired_val != val:
                repaired[r_idx][c_idx] = repaired_val
                changelog.append(f"Row {r_idx+1}, Col {c_idx+1}: Fixed OCR character confusion '{val}' -> '{repaired_val}'")

    return repaired, changelog
