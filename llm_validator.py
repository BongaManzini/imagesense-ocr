"""
ImageSense - Hybrid Vision/LLM Validation & Table Refinement Engine
Combines fast local heuristic repairs (0 vs O, l vs 1, date standardization, math reconciliation)
with optional Google Gemini Vision/LLM post-processing for complex handwritten documents,
garbled receipts, and borderless tables.
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple

import audit_engine
import schema_templates


DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def is_llm_available(api_key: Optional[str] = None) -> bool:
    """Checks whether a Gemini API key is configured either in environment or passed directly."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return bool(key and len(key.strip()) > 10)


def refine_table_with_llm(
    table_data: List[List[str]],
    schema_id: str = "retail_invoice",
    raw_text: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: str = DEFAULT_GEMINI_MODEL,
    timeout_seconds: int = 15
) -> Dict[str, Any]:
    """
    Refines and validates extracted table data using either:
    1. Google Gemini Flash LLM (if API key is present), or
    2. High-precision local heuristic audit & repair engine (offline fallback).

    Returns a dict with:
    - success: bool
    - table_data: List[List[str]] (cleaned)
    - corrections_applied: List[str]
    - model_used: str
    - audit: Dict[str, Any]
    """
    effective_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if not table_data or len(table_data) == 0:
        return {
            "success": False,
            "error": "Empty table data provided",
            "table_data": table_data,
            "corrections_applied": [],
            "model_used": "none",
            "audit": {}
        }

    # -----------------------------------------------------------------------
    # Path A: Gemini LLM API Call
    # -----------------------------------------------------------------------
    if effective_key and len(effective_key.strip()) > 10:
        try:
            llm_result = _call_gemini_api(
                table_data=table_data,
                schema_id=schema_id,
                raw_text=raw_text,
                api_key=effective_key.strip(),
                model_name=model_name,
                timeout_seconds=timeout_seconds
            )
            if llm_result and "table_data" in llm_result:
                refined_table = llm_result["table_data"]
                # Run audit on the LLM-refined table
                audit_res = audit_engine.audit_document_table(refined_table, schema_id=schema_id)
                return {
                    "success": True,
                    "table_data": refined_table,
                    "corrections_applied": llm_result.get("corrections_applied", ["LLM schema refinement applied"]),
                    "model_used": f"Google {model_name} (Cloud Vision/LLM)",
                    "audit": audit_res
                }
        except Exception as e:
            # On LLM failure, log and seamlessly fallback to local engine
            print(f"[LLM_VALIDATOR] Gemini API request failed: {e}. Falling back to local heuristic engine.")

    # -----------------------------------------------------------------------
    # Path B: Local Heuristic Audit & Repair Engine (100% Offline / Free)
    # -----------------------------------------------------------------------
    initial_audit = audit_engine.audit_document_table(table_data, schema_id=schema_id)
    repaired_table, changelog = audit_engine.auto_repair_table(table_data, initial_audit)
    final_audit = audit_engine.audit_document_table(repaired_table, schema_id=schema_id)

    corrections = changelog

    return {
        "success": True,
        "table_data": repaired_table,
        "corrections_applied": corrections,
        "model_used": "ImageSense Local Heuristic Engine (Deterministic / Offline)",
        "audit": final_audit
    }


def _call_gemini_api(
    table_data: List[List[str]],
    schema_id: str,
    raw_text: Optional[str],
    api_key: str,
    model_name: str,
    timeout_seconds: int
) -> Optional[Dict[str, Any]]:
    """Makes a direct REST call to Gemini generateContent endpoint using standard library urllib."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    schema_def = schema_templates.SCHEMAS.get(schema_id, schema_templates.SCHEMAS["retail_invoice"])
    target_columns = schema_def.get("columns", [])

    prompt_instructions = (
        f"You are a financial document and OCR table post-processing expert for small businesses (SMMEs).\n"
        f"Below is a preliminary table extracted via Optical Character Recognition from a document.\n\n"
        f"Target Document Schema: '{schema_def.get('name')}' (ID: {schema_id})\n"
        f"Expected Standard Columns: {target_columns}\n\n"
        f"Raw OCR Text excerpt (if available):\n{raw_text[:800] if raw_text else 'N/A'}\n\n"
        f"Current Raw Table Extracted:\n{json.dumps(table_data, ensure_ascii=False, indent=2)}\n\n"
        f"TASKS:\n"
        f"1. Fix OCR character confusions: Replace letter 'O' with number '0' in numeric prices/quantities, "
        f"letter 'l' or 'I' with '1' where appropriate, and correct thousand separators and broken decimal points.\n"
        f"2. Standardize dates to ISO YYYY-MM-DD format.\n"
        f"3. Strip currency symbols (e.g. '$', 'R', 'EUR') from numeric amount columns so they are clean floats.\n"
        f"4. Verify arithmetic consistency: Quantity * Unit Price == Total. If an OCR error corrupted a digit, correct it.\n"
        f"5. Align column headers to match or map into the expected standard columns.\n\n"
        f"Return ONLY a valid JSON object with EXACTLY this structure:\n"
        f"{{\n"
        f'  "table_data": [["Header1", "Header2", ...], ["Val1", "Val2", ...]],\n'
        f'  "corrections_applied": ["Summary of fix 1", "Summary of fix 2"]\n'
        f"}}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_instructions}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        res_body = response.read().decode("utf-8")
        parsed_res = json.loads(res_body)

        # Extract text from candidate
        candidates = parsed_res.get("candidates", [])
        if not candidates:
            return None

        content_parts = candidates[0].get("content", {}).get("parts", [])
        if not content_parts:
            return None

        raw_json_str = content_parts[0].get("text", "").strip()

        # Clean markdown codeblocks if returned
        if raw_json_str.startswith("```json"):
            raw_json_str = raw_json_str[7:]
        if raw_json_str.startswith("```"):
            raw_json_str = raw_json_str[3:]
        if raw_json_str.endswith("```"):
            raw_json_str = raw_json_str[:-3]

        parsed_json = json.loads(raw_json_str.strip())
        return parsed_json
