"""
ImageSense - Intelligent OCR to Excel & SMME Accounting Web Application
Extracts text and tabular data from scanned documents, receipts, invoices, and PDFs,
provides interactive side-by-side human-in-the-loop validation, automated arithmetic checking,
and direct exports for Excel (.xlsx), Sage Pastel, Xero, QuickBooks Online, CSV, Word, and JSON.
"""

import os
import re
import json
import time
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import (
    Flask, render_template, request, redirect, url_for,
    send_file, flash, jsonify
)
from werkzeug.utils import secure_filename

import ocr_engine
import audit_engine
import schema_templates
import llm_validator

app = Flask(__name__)
app.secret_key = "imagesense-ocr-secure-key-2026"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "tiff", "bmp", "pdf", "gif"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024  # 128 MB max for batch uploads


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def cleanup_old_files(max_age_seconds: int = 3600):
    """
    Automated security and storage maintenance:
    Purges temporary files in uploads/ and processed/ older than max_age_seconds.
    """
    now = time.time()
    for folder in (UPLOAD_FOLDER, PROCESSED_FOLDER):
        if not os.path.exists(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            try:
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    if now - os.path.getmtime(fpath) > max_age_seconds:
                        os.remove(fpath)
                elif os.path.isdir(fpath):
                    if now - os.path.getmtime(fpath) > max_age_seconds:
                        shutil.rmtree(fpath, ignore_errors=True)
            except Exception as e:
                print(f"Error cleaning file {fpath}: {e}")


@app.route("/")
def index():
    cleanup_old_files()
    engine_ready = bool(ocr_engine.TESSERACT_CMD)
    return render_template(
        "index.html",
        engine_ready=engine_ready,
        schemas=schema_templates.SCHEMAS
    )


@app.route("/preview/<filename>")
def preview_file(filename):
    """Safely serves uploaded or preprocessed preview images for the side-by-side UI."""
    safe_name = secure_filename(filename)
    # Check processed folder first, then uploads
    fpath = os.path.join(app.config["PROCESSED_FOLDER"], safe_name)
    if not os.path.exists(fpath):
        fpath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)

    if os.path.exists(fpath):
        mimetype = "image/png"
        if safe_name.lower().endswith((".jpg", ".jpeg")):
            mimetype = "image/jpeg"
        elif safe_name.lower().endswith(".webp"):
            mimetype = "image/webp"
        return send_file(fpath, mimetype=mimetype)

    return "File not found", 404


@app.route("/upload", methods=["POST"])
def upload_file():
    cleanup_old_files()

    uploaded_files = request.files.getlist("document")
    files = [f for f in uploaded_files if f and f.filename and allowed_file(f.filename)]

    if not files:
        flash("Please select at least one valid image (PNG, JPG, TIFF, WEBP, BMP) or PDF file.")
        return redirect(url_for("index"))

    # Processing options from form
    preset = request.form.get("preset", "auto")
    deskew = request.form.get("deskew") in ("on", "true", "1")
    perspective_correct = request.form.get("perspective") not in ("off", "false", "0")
    remove_shadows = request.form.get("shadows") not in ("off", "false", "0")
    schema_id = request.form.get("schema", "auto")

    psm_str = request.form.get("psm", "6")
    try:
        psm = int(psm_str)
    except ValueError:
        psm = 6

    batch_id = str(uuid.uuid4())[:8]
    saved_paths = []

    for f in files:
        safe_name = secure_filename(f.filename)
        unique_prefix = f"{batch_id}_{str(uuid.uuid4())[:4]}"
        dest_filename = f"{unique_prefix}_{safe_name}"
        dest_path = os.path.join(app.config["UPLOAD_FOLDER"], dest_filename)
        f.save(dest_path)
        saved_paths.append(dest_path)

    # -----------------------------------------------------------------------
    # Case 1: Single Document Upload (Side-by-Side Review Station)
    # -----------------------------------------------------------------------
    if len(saved_paths) == 1:
        target_path = saved_paths[0]
        orig_filename = secure_filename(files[0].filename)
        is_pdf = target_path.lower().endswith(".pdf")

        try:
            doc_pages = ocr_engine.process_document_all_pages(
                target_path,
                preset=preset,
                deskew=deskew,
                perspective_correct=perspective_correct,
                remove_shadows=remove_shadows,
                psm=psm,
                schema_id=schema_id
            )
            if not doc_pages:
                flash("No text could be extracted from this document.")
                return redirect(url_for("index"))

            first_page = doc_pages[0]
            table_data = first_page["table_data"]
            raw_text = first_page["raw_text"]
            confidence = first_page["confidence"]
            detected_schema = first_page.get("schema_id", "retail_invoice")
            schema_name = first_page.get("schema_name", "Retail & Supplier Invoice")
            audit = first_page.get("audit", {})
            cell_confidences = first_page.get("cell_confidences", {})

            # Save preview images for side-by-side display
            prep_filename = f"prep_{batch_id}.png"
            overlay_filename = f"overlay_{batch_id}.png"
            orig_preview_name = f"orig_{batch_id}.png"

            if first_page.get("preprocessed_image"):
                first_page["preprocessed_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], prep_filename))
            if first_page.get("overlay_image"):
                first_page["overlay_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], overlay_filename))

            if not is_pdf:
                # Copy original image to processed for easy serving
                shutil.copy(target_path, os.path.join(app.config["PROCESSED_FOLDER"], orig_preview_name))
            else:
                # For PDF, use preprocessed as base view
                if first_page.get("preprocessed_image"):
                    first_page["preprocessed_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], orig_preview_name))

            # Generate export files (Standard Excel, Accounting Formats, CSV, Word, JSON)
            excel_filename = f"extracted_{batch_id}.xlsx"
            ocr_engine.export_to_excel(table_data, os.path.join(app.config["PROCESSED_FOLDER"], excel_filename))

            sage_filename = f"extracted_sage_{batch_id}.csv"
            ocr_engine.export_to_sage_pastel(table_data, os.path.join(app.config["PROCESSED_FOLDER"], sage_filename))

            xero_filename = f"extracted_xero_{batch_id}.csv"
            ocr_engine.export_to_xero(table_data, os.path.join(app.config["PROCESSED_FOLDER"], xero_filename))

            qb_filename = f"extracted_qb_{batch_id}.csv"
            ocr_engine.export_to_quickbooks(table_data, os.path.join(app.config["PROCESSED_FOLDER"], qb_filename))

            csv_filename = f"extracted_{batch_id}.csv"
            ocr_engine.export_to_csv(table_data, os.path.join(app.config["PROCESSED_FOLDER"], csv_filename))

            docx_filename = f"extracted_{batch_id}.docx"
            try:
                ocr_engine.export_to_docx(table_data, raw_text, os.path.join(app.config["PROCESSED_FOLDER"], docx_filename))
            except Exception:
                docx_filename = None

            json_filename = f"extracted_{batch_id}.json"
            ocr_engine.export_to_json(table_data, raw_text, confidence, os.path.join(app.config["PROCESSED_FOLDER"], json_filename))

            return render_template(
                "result.html",
                is_batch=False,
                batch_id=batch_id,
                filename=orig_filename,
                excel_filename=excel_filename,
                sage_filename=sage_filename,
                xero_filename=xero_filename,
                qb_filename=qb_filename,
                csv_filename=csv_filename,
                docx_filename=docx_filename,
                json_filename=json_filename,
                orig_preview=orig_preview_name,
                prep_preview=prep_filename,
                overlay_preview=overlay_filename,
                raw_text=raw_text,
                table_data=table_data,
                row_count=len(table_data),
                col_count=len(table_data[0]) if table_data else 0,
                confidence=confidence,
                page_count=len(doc_pages),
                is_pdf=is_pdf,
                schema_id=detected_schema,
                schema_name=schema_name,
                audit=audit,
                cell_confidences=cell_confidences,
                schemas=schema_templates.SCHEMAS
            )

        except Exception as e:
            flash(f"Error processing file '{orig_filename}': {str(e)}")
            return redirect(url_for("index"))

    # -----------------------------------------------------------------------
    # Case 2: Batch Processing (Large Amount of Files)
    # -----------------------------------------------------------------------
    try:
        batch_result = ocr_engine.batch_process_files(
            saved_paths,
            preset=preset,
            deskew=deskew,
            perspective_correct=perspective_correct,
            remove_shadows=remove_shadows,
            psm=psm,
            max_workers=4,
            schema_id=schema_id
        )

        combined_excel_name = f"batch_combined_{batch_id}.xlsx"
        ocr_engine.export_batch_to_excel(batch_result, os.path.join(app.config["PROCESSED_FOLDER"], combined_excel_name))

        batch_zip_name = f"batch_archive_{batch_id}.zip"
        ocr_engine.export_batch_to_zip(batch_result, os.path.join(app.config["PROCESSED_FOLDER"], batch_zip_name))

        file_items = []
        items_list = batch_result.get("items") or list(batch_result.get("results", {}).items())
        for idx, (path, pages) in enumerate(items_list):
            base_orig = os.path.basename(path).split("_", 2)[-1]
            p1 = pages[0] if pages else {}
            t_data = p1.get("table_data", [])
            raw_t = p1.get("raw_text", "")
            conf = p1.get("confidence", 0.0)
            s_id = p1.get("schema_id", "retail_invoice")
            s_name = p1.get("schema_name", "Retail & Supplier Invoice")
            aud = p1.get("audit", {})
            cell_confs = p1.get("cell_confidences", {})

            # Preview filenames for this batch item
            item_orig_preview = f"orig_{batch_id}_{idx}.png"
            item_prep_preview = f"prep_{batch_id}_{idx}.png"
            item_overlay_preview = f"overlay_{batch_id}_{idx}.png"

            if p1.get("preprocessed_image"):
                p1["preprocessed_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], item_prep_preview))
            if p1.get("overlay_image"):
                p1["overlay_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], item_overlay_preview))

            is_item_pdf = path.lower().endswith(".pdf")
            if not is_item_pdf and os.path.exists(path):
                shutil.copy(path, os.path.join(app.config["PROCESSED_FOLDER"], item_orig_preview))
            elif p1.get("preprocessed_image"):
                p1["preprocessed_image"].save(os.path.join(app.config["PROCESSED_FOLDER"], item_orig_preview))

            # Export packages for this item
            item_excel = f"extracted_{batch_id}_{idx}.xlsx"
            ocr_engine.export_to_excel(t_data, os.path.join(app.config["PROCESSED_FOLDER"], item_excel))

            item_sage = f"extracted_sage_{batch_id}_{idx}.csv"
            ocr_engine.export_to_sage_pastel(t_data, os.path.join(app.config["PROCESSED_FOLDER"], item_sage))

            item_xero = f"extracted_xero_{batch_id}_{idx}.csv"
            ocr_engine.export_to_xero(t_data, os.path.join(app.config["PROCESSED_FOLDER"], item_xero))

            item_qb = f"extracted_qb_{batch_id}_{idx}.csv"
            ocr_engine.export_to_quickbooks(t_data, os.path.join(app.config["PROCESSED_FOLDER"], item_qb))

            item_csv = f"extracted_{batch_id}_{idx}.csv"
            ocr_engine.export_to_csv(t_data, os.path.join(app.config["PROCESSED_FOLDER"], item_csv))

            item_docx = f"extracted_{batch_id}_{idx}.docx"
            try:
                ocr_engine.export_to_docx(t_data, raw_t, os.path.join(app.config["PROCESSED_FOLDER"], item_docx))
            except Exception:
                item_docx = None

            item_json = f"extracted_{batch_id}_{idx}.json"
            ocr_engine.export_to_json(t_data, raw_t, conf, os.path.join(app.config["PROCESSED_FOLDER"], item_json))

            file_items.append({
                "index": idx,
                "filename": base_orig,
                "confidence": conf,
                "row_count": p1.get("row_count", 0),
                "col_count": p1.get("col_count", 0),
                "pages": len(pages),
                "table_data": t_data,
                "raw_text": raw_t,
                "schema_id": s_id,
                "schema_name": s_name,
                "audit": aud,
                "cell_confidences": cell_confs,
                "orig_preview": item_orig_preview,
                "prep_preview": item_prep_preview,
                "overlay_preview": item_overlay_preview,
                "excel_filename": item_excel,
                "sage_filename": item_sage,
                "xero_filename": item_xero,
                "qb_filename": item_qb,
                "csv_filename": item_csv,
                "docx_filename": item_docx,
                "json_filename": item_json
            })

        # Save batch metadata JSON for persistent drill-down review
        batch_meta = {
            "batch_id": batch_id,
            "total_files": batch_result["total_files"],
            "processed_files": batch_result["processed_files"],
            "total_pages": batch_result["total_pages"],
            "average_confidence": batch_result["average_confidence"],
            "elapsed_seconds": batch_result["elapsed_seconds"],
            "combined_excel": combined_excel_name,
            "batch_zip": batch_zip_name,
            "file_items": file_items,
            "errors": batch_result.get("errors", [])
        }
        meta_path = os.path.join(app.config["PROCESSED_FOLDER"], f"batch_{batch_id}_meta.json")
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(batch_meta, mf)

        return render_template(
            "result.html",
            is_batch=True,
            batch_id=batch_id,
            total_files=batch_result["total_files"],
            processed_files=batch_result["processed_files"],
            total_pages=batch_result["total_pages"],
            average_confidence=batch_result["average_confidence"],
            elapsed_seconds=batch_result["elapsed_seconds"],
            combined_excel=combined_excel_name,
            batch_zip=batch_zip_name,
            file_items=file_items,
            errors=batch_result.get("errors", []),
            schemas=schema_templates.SCHEMAS
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Batch processing failed: {str(e)}")
        return redirect(url_for("index"))


@app.route("/batch/<batch_id>")
def view_batch_summary(batch_id):
    """Restores and views the full batch overview from saved metadata."""
    safe_batch = secure_filename(batch_id)
    meta_path = os.path.join(app.config["PROCESSED_FOLDER"], f"batch_{safe_batch}_meta.json")
    if not os.path.exists(meta_path):
        flash("Batch record not found or expired.")
        return redirect(url_for("index"))

    with open(meta_path, "r", encoding="utf-8") as mf:
        batch_meta = json.load(mf)

    return render_template(
        "result.html",
        is_batch=True,
        batch_id=batch_meta["batch_id"],
        total_files=batch_meta["total_files"],
        processed_files=batch_meta["processed_files"],
        total_pages=batch_meta["total_pages"],
        average_confidence=batch_meta["average_confidence"],
        elapsed_seconds=batch_meta["elapsed_seconds"],
        combined_excel=batch_meta["combined_excel"],
        batch_zip=batch_meta["batch_zip"],
        file_items=batch_meta["file_items"],
        errors=batch_meta.get("errors", []),
        schemas=schema_templates.SCHEMAS
    )


@app.route("/batch/<batch_id>/review/<int:item_index>")
def review_batch_item(batch_id, item_index):
    """Opens a specific document from a batch inside the dual-pane Review & Audit Station."""
    safe_batch = secure_filename(batch_id)
    meta_path = os.path.join(app.config["PROCESSED_FOLDER"], f"batch_{safe_batch}_meta.json")
    if not os.path.exists(meta_path):
        flash("Batch record not found or expired.")
        return redirect(url_for("index"))

    with open(meta_path, "r", encoding="utf-8") as mf:
        batch_meta = json.load(mf)

    items = batch_meta.get("file_items", [])
    if item_index < 0 or item_index >= len(items):
        flash("Document item not found in batch.")
        return redirect(url_for("view_batch_summary", batch_id=batch_id))

    item = items[item_index]
    t_data = item.get("table_data", [])

    return render_template(
        "result.html",
        is_batch=False,
        batch_id=f"{safe_batch}_{item_index}",
        batch_parent_id=safe_batch,
        batch_item_index=item_index,
        filename=item["filename"],
        excel_filename=item["excel_filename"],
        sage_filename=item["sage_filename"],
        xero_filename=item["xero_filename"],
        qb_filename=item["qb_filename"],
        csv_filename=item["csv_filename"],
        docx_filename=item.get("docx_filename"),
        json_filename=item["json_filename"],
        orig_preview=item.get("orig_preview"),
        prep_preview=item.get("prep_preview"),
        overlay_preview=item.get("overlay_preview"),
        raw_text=item.get("raw_text", ""),
        table_data=t_data,
        row_count=len(t_data),
        col_count=len(t_data[0]) if t_data else 0,
        confidence=item.get("confidence", 0.0),
        page_count=item.get("pages", 1),
        is_pdf=False,
        schema_id=item.get("schema_id", "retail_invoice"),
        schema_name=item.get("schema_name", "Retail & Supplier Invoice"),
        audit=item.get("audit", {}),
        cell_confidences=item.get("cell_confidences", {}),
        schemas=schema_templates.SCHEMAS
    )


@app.route("/api/llm_refine", methods=["POST"])
def api_llm_refine():
    """Applies Hybrid Vision/LLM validation and table refinement using Google Gemini or local heuristics."""
    try:
        data = request.get_json(force=True)
        table_data = data.get("table_data", [])
        schema_id = data.get("schema_id", "retail_invoice")
        raw_text = data.get("raw_text", "")
        api_key = data.get("api_key")

        res = llm_validator.refine_table_with_llm(
            table_data=table_data,
            schema_id=schema_id,
            raw_text=raw_text,
            api_key=api_key
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ---------------------------------------------------------------------------
# Human-in-the-Loop Interactive Review API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/audit", methods=["POST"])
def api_audit():
    """Runs instant mathematical and business audit on table data."""
    try:
        data = request.get_json(force=True)
        table_data = data.get("table_data", [])
        schema_id = data.get("schema_id", "retail_invoice")
        audit_res = audit_engine.audit_document_table(table_data, schema_id=schema_id)
        return jsonify({"success": True, "audit": audit_res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/auto_repair", methods=["POST"])
def api_auto_repair():
    """Applies automated OCR character confusion fixes and date standardization."""
    try:
        data = request.get_json(force=True)
        table_data = data.get("table_data", [])
        schema_id = data.get("schema_id", "retail_invoice")

        initial_audit = audit_engine.audit_document_table(table_data, schema_id=schema_id)
        repaired_table, changelog = audit_engine.auto_repair_table(table_data, initial_audit)
        new_audit = audit_engine.audit_document_table(repaired_table, schema_id=schema_id)

        return jsonify({
            "success": True,
            "repaired_table": repaired_table,
            "changelog": changelog,
            "audit": new_audit
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/save_and_export", methods=["POST"])
def api_save_and_export():
    """
    Saves edited table data from the browser grid and re-generates
    all export packages (Excel, Sage Pastel, Xero, QuickBooks, CSV, JSON).
    """
    try:
        data = request.get_json(force=True)
        table_data = data.get("table_data", [])
        batch_id = data.get("batch_id") or str(uuid.uuid4())[:8]
        schema_id = data.get("schema_id", "retail_invoice")
        filename = data.get("filename", "document")

        excel_filename = f"extracted_{batch_id}.xlsx"
        ocr_engine.export_to_excel(table_data, os.path.join(app.config["PROCESSED_FOLDER"], excel_filename))

        sage_filename = f"extracted_sage_{batch_id}.csv"
        ocr_engine.export_to_sage_pastel(table_data, os.path.join(app.config["PROCESSED_FOLDER"], sage_filename))

        xero_filename = f"extracted_xero_{batch_id}.csv"
        ocr_engine.export_to_xero(table_data, os.path.join(app.config["PROCESSED_FOLDER"], xero_filename))

        qb_filename = f"extracted_qb_{batch_id}.csv"
        ocr_engine.export_to_quickbooks(table_data, os.path.join(app.config["PROCESSED_FOLDER"], qb_filename))

        csv_filename = f"extracted_{batch_id}.csv"
        ocr_engine.export_to_csv(table_data, os.path.join(app.config["PROCESSED_FOLDER"], csv_filename))

        json_filename = f"extracted_{batch_id}.json"
        ocr_engine.export_to_json(table_data, "", 100.0, os.path.join(app.config["PROCESSED_FOLDER"], json_filename))

        new_audit = audit_engine.audit_document_table(table_data, schema_id=schema_id)

        return jsonify({
            "success": True,
            "audit": new_audit,
            "files": {
                "excel": excel_filename,
                "sage": sage_filename,
                "xero": xero_filename,
                "qb": qb_filename,
                "csv": csv_filename,
                "json": json_filename
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/download/<filename>")
def download_file(filename):
    safe_filename = secure_filename(filename)
    file_path = os.path.join(app.config["PROCESSED_FOLDER"], safe_filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=safe_filename)
    flash("The requested file was not found or has expired.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
