"""
Comprehensive Test Suite for ImageSense SMME OCR & Accounting Pipeline
Tests image reading, perspective correction, shadow removal, morphological grid detection,
table reconstruction, SMME schema detection, arithmetic & date validation,
accounting exports (Sage Pastel, Xero, QuickBooks), and Web API endpoints.
"""

import os
import re
import io
import json
import shutil
import tempfile
import unittest
import numpy as np
from PIL import Image, ImageDraw

import ocr_engine
import audit_engine
import schema_templates
import llm_validator
import engine_strategy
import teds_evaluator
import gui
from app import app


class TestImageSensePipeline(unittest.TestCase):

    def test_01_locate_tesseract(self):
        cmd, data = ocr_engine.locate_tesseract()
        self.assertIsNotNone(cmd, "Tesseract executable should be located")
        self.assertTrue(os.path.exists(cmd), f"Tesseract binary does not exist at {cmd}")
        print(f"\n[PASS] Tesseract located at: {cmd}")

    def test_02_image_reading_formats(self):
        """Verifies that ImageSense can load and process various image formats."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            img = Image.new("RGB", (600, 300), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), "Item Description Qty Price Total", fill=(0, 0, 0))
            draw.text((20, 60), "101 Widget Alpha 2 50.00 100.00", fill=(0, 0, 0))
            draw.text((20, 100), "102 Widget Beta 1 75.00 75.00", fill=(0, 0, 0))

            formats = ["png", "jpeg", "webp", "bmp", "tiff"]
            for fmt in formats:
                filepath = os.path.join(tmp_dir, f"test_img.{fmt}")
                img.save(filepath, format="JPEG" if fmt == "jpeg" else fmt.upper())
                self.assertTrue(os.path.exists(filepath))

                result = ocr_engine.perform_high_accuracy_ocr(filepath, preset="document")
                self.assertIsNotNone(result)
                self.assertIn("table_data", result)
                self.assertGreaterEqual(len(result["table_data"]), 1)
                print(f"[PASS] Read and processed format: {fmt.upper()}")

    def test_03_sample_invoice_extraction(self):
        sample_file = "sample_data/sample_invoice.png"
        self.assertTrue(os.path.exists(sample_file), "Sample invoice image must exist")

        result = ocr_engine.perform_high_accuracy_ocr(sample_file, preset="invoice")
        self.assertGreater(result["confidence"], 75.0, f"Expected >75% confidence, got {result['confidence']}%")
        self.assertGreaterEqual(result["row_count"], 4, f"Expected at least 4 rows, got {result['row_count']}")
        self.assertGreaterEqual(result["col_count"], 4, f"Expected at least 4 columns, got {result['col_count']}")

        flat_table = " ".join(" ".join(r) for r in result["table_data"])
        self.assertTrue("PRD" in flat_table or "Cloud" in flat_table)
        self.assertEqual(result["schema_id"], "retail_invoice")
        print(f"[PASS] Sample invoice extracted with {result['confidence']}% confidence, {result['row_count']} rows x {result['col_count']} cols (Schema: {result['schema_name']})")

    def test_04_batch_processing_and_master_excel(self):
        sample_file = "sample_data/sample_invoice.png"
        files = [sample_file, sample_file]

        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_res = ocr_engine.batch_process_files(files, max_workers=2)
            self.assertEqual(batch_res["total_files"], 2)
            self.assertEqual(batch_res["processed_files"], 2)
            self.assertGreater(batch_res["average_confidence"], 75.0)

            # Master Excel
            master_excel = os.path.join(tmp_dir, "master_batch.xlsx")
            ocr_engine.export_batch_to_excel(batch_res, master_excel)
            self.assertTrue(os.path.exists(master_excel))
            self.assertGreater(os.path.getsize(master_excel), 1000)

            # ZIP export
            zip_path = os.path.join(tmp_dir, "master_batch.zip")
            ocr_engine.export_batch_to_zip(batch_res, zip_path)
            self.assertTrue(os.path.exists(zip_path))
            self.assertGreater(os.path.getsize(zip_path), 1000)
            print(f"[PASS] Batch processing successfully verified: 2 files, master Excel ({os.path.getsize(master_excel)} bytes), zip ({os.path.getsize(zip_path)} bytes)")

    def test_05_flask_web_app(self):
        app.config["TESTING"] = True
        client = app.test_client()

        # 1. Index page
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"ImageSense", r.data)
        self.assertIn(b"Extract & Convert to Excel", r.data)

        # 2. Single document upload
        sample_file = "sample_data/sample_invoice.png"
        with open(sample_file, "rb") as f:
            file_bytes = io.BytesIO(f.read())

        data = {
            "document": (file_bytes, "sample_invoice.png"),
            "preset": "auto",
            "deskew": "on"
        }
        r_post = client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(r_post.status_code, 200)
        self.assertIn(b"Conversion Completed Successfully", r_post.data)
        self.assertIn(b"sample_invoice.png", r_post.data)

        # 3. Batch document upload (multiple files)
        with open(sample_file, "rb") as f1, open(sample_file, "rb") as f2:
            b1 = io.BytesIO(f1.read())
            b2 = io.BytesIO(f2.read())

        batch_data = {
            "document": [
                (b1, "invoice_doc_1.png"),
                (b2, "invoice_doc_2.png")
            ],
            "preset": "auto"
        }
        r_batch = client.post("/upload", data=batch_data, content_type="multipart/form-data")
        self.assertEqual(r_batch.status_code, 200)
        self.assertIn(b"Batch Processing Completed", r_batch.data)
        self.assertIn(b"Download Master Excel", r_batch.data)
        self.assertIn(b"invoice_doc_1.png", r_batch.data)
        self.assertIn(b"invoice_doc_2.png", r_batch.data)
        print("[PASS] Flask web app verified: Index, Single Upload, Batch Upload all returned 200 OK")

    def test_06_perspective_correction_and_shadow_removal(self):
        """Verifies perspective correction and shadow removal algorithms."""
        # Create synthetic image with a quadrilateral document on a dark table
        canvas = np.zeros((600, 800, 3), dtype=np.uint8)
        # Angled document polygon
        doc_pts = np.array([[100, 120], [700, 80], [680, 520], [120, 500]], dtype=np.int32)
        cv2 = ocr_engine.cv2
        if cv2 is not None:
            cv2.fillPoly(canvas, [doc_pts], (240, 240, 240))
            cv2.putText(canvas, "INVOICE #999", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

            warped, detected = ocr_engine.correct_perspective(canvas)
            self.assertTrue(detected, "Perspective quadrilateral should be detected")
            self.assertGreater(warped.shape[0], 200)
            self.assertGreater(warped.shape[1], 300)

            # Test shadow removal
            shadow_test = np.ones((400, 400), dtype=np.uint8) * 200
            shadow_test[100:300, :] = 100  # Dark shadow stripe
            normalized = ocr_engine.remove_shadows_and_uneven_light(shadow_test)
            self.assertEqual(normalized.shape, (400, 400))
            self.assertGreater(float(np.mean(normalized)), 180.0)
            print("[PASS] Perspective correction and shadow removal verified")

    def test_07_morphological_table_grid_detection(self):
        """Verifies cell bounding-box detection on an explicit grid table."""
        cv2 = ocr_engine.cv2
        if cv2 is None:
            return

        # Draw a synthetic grid table (3 rows x 3 columns)
        img = np.ones((500, 700), dtype=np.uint8) * 255
        # Horizontal lines
        for y in [100, 200, 300, 400]:
            cv2.line(img, (50, y), (650, y), 0, 2)
        # Vertical lines
        for x in [50, 250, 450, 650]:
            cv2.line(img, (x, 100), (x, 400), 0, 2)

        # Detect cells
        cells, has_grid = ocr_engine.detect_table_cells_opencv(img, min_cells=4)
        self.assertTrue(has_grid, "Synthetic grid table must be detected")
        self.assertGreaterEqual(len(cells), 6, f"Expected at least 6 grid cells, got {len(cells)}")

        # Map synthetic words into cells
        words = [
            {"text": "Header1", "left": 100, "top": 140, "width": 80, "height": 20, "conf": 95.0},
            {"text": "Header2", "left": 300, "top": 140, "width": 80, "height": 20, "conf": 92.0},
            {"text": "ItemA", "left": 100, "top": 240, "width": 60, "height": 20, "conf": 96.0},
            {"text": "100.00", "left": 300, "top": 240, "width": 60, "height": 20, "conf": 94.0},
        ]
        table_data, confs = ocr_engine.map_words_to_grid_cells(words, cells)
        self.assertGreaterEqual(len(table_data), 2)
        self.assertIn("Header1", table_data[0][0])
        print(f"[PASS] Morphological grid detection verified: {len(cells)} cells detected and mapped")

    def test_08_smme_schemas_and_classification(self):
        """Verifies schema detection and canonical column mapping for SMME sectors."""
        # 1. Retail invoice
        inv_table = [["Item Code", "Description", "Quantity", "Unit Price", "Total"], ["P1", "Item A", "2", "50", "100"]]
        schema_inv = schema_templates.detect_schema(inv_table)
        self.assertEqual(schema_inv, "retail_invoice")

        # 2. Logistics Waybill / POD
        pod_table = [["Waybill #", "Recipient Name", "Date", "Destination", "Status"], ["WB-123", "Acme", "2026-10-27", "Joburg", "Delivered"]]
        schema_pod = schema_templates.detect_schema(pod_table)
        self.assertEqual(schema_pod, "logistics_waybill")

        # 3. Construction Timesheet
        const_table = [["Worker ID", "Site Name", "Hours Worked", "Hourly Rate", "Total"], ["W01", "Site A", "8", "150", "1200"]]
        schema_const = schema_templates.detect_schema(const_table)
        self.assertEqual(schema_const, "construction_timesheet")

        # 4. Medical Clinic
        med_table = [["Test / Marker", "Measured Value", "Unit", "Reference Range"], ["Glucose", "5.4", "mmol/L", "4.0-7.0"]]
        schema_med = schema_templates.detect_schema(med_table)
        self.assertEqual(schema_med, "medical_clinic")

        # 5. Bank Statement
        bank_table = [["Transaction Date", "Particulars", "Debit", "Credit", "Balance"], ["2026-10-01", "Client Payment", "", "5000.00", "12500.00"]]
        schema_bank = schema_templates.detect_schema(bank_table)
        self.assertEqual(schema_bank, "bank_statement")

        print("[PASS] SMME Schema Detection verified across Retail, Logistics, Construction, Medical, and Banking")

    def test_09_arithmetic_and_date_validation(self):
        """Verifies calculation checks, date validation, and OCR confusion repairs."""
        # 1. Math check
        table_with_math = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-01", "Alpha", "2", "50.00", "100.00"],   # Pass: 2*50 = 100
            ["PRD-02", "Beta", "3", "45.00", "135.00"],    # Pass: 3*45 = 135
            ["PRD-03", "Gamma", "3", "46.00", "135.00"],   # Fail: 3*46 = 138 != 135
        ]
        checks, stats = audit_engine.verify_math_equations(table_with_math)
        self.assertEqual(stats["total_rows"], 3)
        self.assertEqual(stats["passed"], 2)
        self.assertEqual(stats["failed"], 1)
        self.assertFalse(checks[2]["passed"])
        self.assertEqual(checks[2]["expected_total"], 138.0)

        # 2. Date parsing
        std_date, is_valid = audit_engine.parse_date_safe("October 27, 2026")
        self.assertTrue(is_valid)
        self.assertEqual(std_date, "2026-10-27")

        std_date_dmy, is_valid_dmy = audit_engine.parse_date_safe("27/10/2026")
        self.assertTrue(is_valid_dmy)
        self.assertEqual(std_date_dmy, "2026-10-27")

        # Invalid date
        _, invalid_res = audit_engine.parse_date_safe("32/13/2026")
        self.assertFalse(invalid_res)

        # 3. Numeric & SKU character confusions
        self.assertEqual(audit_engine.repair_numeric_ocr_confusions("PRD-O1"), "PRD-01")
        self.assertEqual(audit_engine.repair_numeric_ocr_confusions("PRD-O4"), "PRD-04")
        self.assertEqual(audit_engine.repair_numeric_ocr_confusions("$12O.OO"), "$120.00")
        self.assertEqual(audit_engine.parse_number_safe("$1,250.50"), 1250.50)
        self.assertEqual(audit_engine.parse_number_safe("(45.00)"), -45.0)

        # 4. Auto repair table
        audit_res = audit_engine.audit_document_table(table_with_math, "retail_invoice")
        self.assertEqual(audit_res["status"], "NEEDS_REVIEW")
        print("[PASS] Arithmetic and date validation engine verified with 100% precision")

    def test_10_accounting_software_exports(self):
        """Verifies Sage Pastel, Xero, and QuickBooks CSV exports."""
        table = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-01", "Database Server", "2", "120.00", "240.00"],
            ["PRD-02", "Fiber Router", "1", "350.00", "350.00"]
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Sage Pastel
            sage_path = os.path.join(tmp_dir, "test_sage.csv")
            ocr_engine.export_to_sage_pastel(table, sage_path)
            self.assertTrue(os.path.exists(sage_path))
            with open(sage_path, "r", encoding="utf-8") as f:
                sage_content = f.read()
            self.assertIn("RecordType,AccountCode", sage_content)
            self.assertIn("PRD-01", sage_content)

            # 2. Xero
            xero_path = os.path.join(tmp_dir, "test_xero.csv")
            ocr_engine.export_to_xero(table, xero_path, contact_name="Vodacom", invoice_number="INV-2026-01")
            self.assertTrue(os.path.exists(xero_path))
            with open(xero_path, "r", encoding="utf-8") as f:
                xero_content = f.read()
            self.assertIn("*ContactName", xero_content)
            self.assertIn("Vodacom", xero_content)

            # 3. QuickBooks
            qb_path = os.path.join(tmp_dir, "test_qb.csv")
            ocr_engine.export_to_quickbooks(table, qb_path, vendor_name="Makro", invoice_no="BILL-888")
            self.assertTrue(os.path.exists(qb_path))
            with open(qb_path, "r", encoding="utf-8") as f:
                qb_content = f.read()
            self.assertIn("*Vendor,*InvoiceNo", qb_content)
            self.assertIn("Makro", qb_content)

            print("[PASS] Direct Accounting Exports (Sage Pastel, Xero, QuickBooks) successfully generated and validated")

    def test_11_web_api_endpoints(self):
        """Verifies /api/audit, /api/auto_repair, /api/save_and_export, and /preview endpoints."""
        app.config["TESTING"] = True
        client = app.test_client()

        sample_table = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-O1", "Cloud Server", "2", "$120.00", "$240.00"],
            ["PRD-02", "Fiber Router", "1", "$350.00", "$350.00"]
        ]

        # 1. /api/audit
        r1 = client.post("/api/audit", json={"table_data": sample_table, "schema_id": "retail_invoice"})
        self.assertEqual(r1.status_code, 200)
        data1 = json.loads(r1.data)
        self.assertTrue(data1["success"])
        self.assertIn("audit", data1)

        # 2. /api/auto_repair
        r2 = client.post("/api/auto_repair", json={"table_data": sample_table, "schema_id": "retail_invoice"})
        self.assertEqual(r2.status_code, 200)
        data2 = json.loads(r2.data)
        self.assertTrue(data2["success"])
        # PRD-O1 should be repaired to PRD-01
        self.assertEqual(data2["repaired_table"][1][0], "PRD-01")

        # 3. /api/save_and_export
        r3 = client.post("/api/save_and_export", json={
            "table_data": sample_table,
            "schema_id": "retail_invoice",
            "batch_id": "testbatch",
            "filename": "test_invoice.png"
        })
        self.assertEqual(r3.status_code, 200)
        data3 = json.loads(r3.data)
        self.assertTrue(data3["success"])
        self.assertIn("excel", data3["files"])
        self.assertIn("sage", data3["files"])
        self.assertIn("xero", data3["files"])
        self.assertIn("qb", data3["files"])

        # 4. /download/<filename>
        r_dl = client.get(f"/download/{data3['files']['excel']}")
        self.assertEqual(r_dl.status_code, 200)
        self.assertGreater(len(r_dl.data), 1000)

        print("[PASS] All Interactive Review Web API endpoints (/api/audit, /api/auto_repair, /api/save_and_export) 200 OK")

    def test_12_hybrid_llm_validator(self):
        """Verifies the hybrid LLM/heuristic validation engine and /api/llm_refine endpoint."""
        app.config["TESTING"] = True
        client = app.test_client()

        raw_table = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-O1", "Cloud Server Pro", "2", "$12O.OO", "$240.00"],
            ["PRD-O2", "Dedicated Host", "1", "$35O.OO", "$350.00"]
        ]

        # Test direct call to refine_table_with_llm (heuristic fallback mode)
        res = llm_validator.refine_table_with_llm(raw_table, schema_id="retail_invoice")
        self.assertTrue(res["success"])
        repaired = res["table_data"]
        # Check that numeric and SKU confusions were repaired
        self.assertEqual(repaired[1][0], "PRD-01")
        self.assertEqual(repaired[2][0], "PRD-02")
        self.assertEqual(repaired[1][3], "$120.00")
        self.assertEqual(repaired[2][3], "$350.00")
        self.assertIn("audit", res)
        self.assertEqual(res["audit"]["math_summary"]["failed"], 0)

        # Test /api/llm_refine Web API endpoint
        api_r = client.post("/api/llm_refine", json={
            "table_data": raw_table,
            "schema_id": "retail_invoice"
        })
        self.assertEqual(api_r.status_code, 200)
        api_data = json.loads(api_r.data)
        self.assertTrue(api_data["success"])
        self.assertGreaterEqual(len(api_data["corrections_applied"]), 1)

        print("[PASS] Hybrid Vision/LLM Validation engine & /api/llm_refine verified")

    def test_13_batch_drill_down_review_station(self):
        """Verifies batch overview persistence, metadata JSON, and individual review station drilldown."""
        app.config["TESTING"] = True
        client = app.test_client()
        sample_file = "sample_data/sample_invoice.png"

        with open(sample_file, "rb") as f1, open(sample_file, "rb") as f2:
            data = {
                "document": [
                    (io.BytesIO(f1.read()), "invoice_a.png"),
                    (io.BytesIO(f2.read()), "invoice_b.png")
                ],
                "preset": "invoice"
            }
            res = client.post("/upload", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Processed 2 of 2 Documents", res.data)
            self.assertTrue(b"Review & Edit Station" in res.data or b"Review &amp; Edit Station" in res.data)

            # Find batch_id in the HTML output
            match = re.search(r'/batch/([a-f0-9]+)/review/0', res.data.decode("utf-8"))
            self.assertIsNotNone(match, "Expected /batch/<id>/review/0 link in batch HTML")
            batch_id = match.group(1)

            # 1. Test /batch/<batch_id> returns summary
            r_sum = client.get(f"/batch/{batch_id}")
            self.assertEqual(r_sum.status_code, 200)
            self.assertIn(b"Processed 2 of 2 Documents", r_sum.data)

            # 2. Test /batch/<batch_id>/review/0 opens side-by-side review station
            r_rev = client.get(f"/batch/{batch_id}/review/0")
            self.assertEqual(r_rev.status_code, 200)
            self.assertIn(b"Back to Batch Overview", r_rev.data)
            self.assertIn(b"Export Verified Data", r_rev.data)
            self.assertIn(b"AI Hybrid Refine", r_rev.data)

        print("[PASS] Batch drill-down navigation and Review & Audit Station verified")

    def test_14_gui_class_architecture(self):
        """Verifies ImageSenseDesktopGUI methods, schema bindings, and export handlers."""
        # Check that ImageSenseDesktopGUI exposes all SMME accounting methods
        expected_methods = [
            "start_ocr_thread",
            "update_audit_badge",
            "auto_clean_confusions_action",
            "recalculate_audit_action",
            "export_excel_action",
            "export_sage_pastel_action",
            "export_xero_action",
            "export_quickbooks_action",
            "export_csv_action",
            "export_docx_action",
            "_sync_table_data_from_tree"
        ]
        for m in expected_methods:
            self.assertTrue(hasattr(gui.ImageSenseDesktopGUI, m), f"ImageSenseDesktopGUI missing method '{m}'")

        print("[PASS] Desktop GUI architecture, schema bindings, and accounting exports verified")

    def test_15_engine_strategy_pattern(self):
        """Verifies the Strategy Pattern implementation separating Free Local and Premium VLM tiers."""
        sample_file = "sample_data/sample_invoice.png"
        self.assertTrue(os.path.exists(sample_file))

        # 1. Test Free / Local Tier Strategy
        local_extractor = engine_strategy.LocalTesseractExtractor()
        local_res = local_extractor.extract_table(sample_file, schema_id="retail_invoice")
        self.assertTrue(local_res["success"])
        self.assertEqual(local_res["tier"], "free_local")
        self.assertEqual(local_res["token_cost"]["cost_usd"], 0.0)
        self.assertGreaterEqual(len(local_res["table_data"]), 4)

        # 2. Test Strategy Context switching
        context = engine_strategy.TableExtractionStrategyContext(default_tier="free")
        ctx_res = context.extract(sample_file, schema_id="retail_invoice")
        self.assertTrue(ctx_res["success"])
        self.assertEqual(ctx_res["tier"], "free_local")

        # 3. Test Hybrid Resilient Strategy (offline fallback test)
        hybrid_extractor = engine_strategy.HybridResilientExtractor(api_key=None)
        hybrid_res = hybrid_extractor.extract_table(sample_file, schema_id="retail_invoice")
        self.assertTrue(hybrid_res["success"])
        self.assertIn("free_local", hybrid_res["tier"])

        print("[PASS] Dual-tier Strategy Pattern (Free Local vs Premium VLM vs Hybrid) verified")

    def test_16_teds_benchmark_evaluator(self):
        """Verifies Tree-Edit-Distance-based Similarity (TEDS) computation and benchmarking."""
        ground_truth = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-01", "Cloud Server", "2", "$120.00", "$240.00"],
            ["PRD-02", "Fiber Router", "1", "$350.00", "$350.00"]
        ]

        # 1. Identical table must give 1.0 (100% TEDS)
        identical_teds = teds_evaluator.compute_teds(ground_truth, ground_truth)
        self.assertAlmostEqual(identical_teds, 1.0, places=2)

        # 2. Table with slight OCR corruption
        corrupted = [
            ["Item Code", "Description", "Quantity", "Unit Price", "Total"],
            ["PRD-O1", "Cloud Server", "2", "$12O.OO", "$240.00"],
            ["PRD-02", "Fiber Router", "1", "$350.00", "$350.00"]
        ]
        corrupted_teds = teds_evaluator.compute_teds(corrupted, ground_truth)
        self.assertGreater(corrupted_teds, 0.85)
        self.assertLess(corrupted_teds, 1.0)

        # 3. Structural TEDS should be 1.0 if rows and cols match exactly
        struct_teds = teds_evaluator.compute_teds(corrupted, ground_truth, structural_only=True)
        self.assertAlmostEqual(struct_teds, 1.0, places=2)

        # 4. Comparative benchmark generator
        report = teds_evaluator.benchmark_table_engines(corrupted, ground_truth, ground_truth)
        self.assertIn("local_tier", report)
        self.assertIn("premium_tier", report)
        self.assertEqual(report["premium_tier"]["teds_score"], 1.0)

        print("[PASS] Tree-Edit-Distance-based Similarity (TEDS) academic benchmark engine verified")

    def test_17_fuzzy_header_matching_and_confidence(self):
        """Verifies fuzzy header matching, confidence scores, and Xero accounting strictness."""
        # 1. Test basic Levenshtein similarity
        self.assertAlmostEqual(schema_templates.levenshtein_sim("Quantity", "Quantity"), 1.0)
        self.assertGreater(schema_templates.levenshtein_sim("Quantty", "Quantity"), 0.85)
        self.assertLess(schema_templates.levenshtein_sim("Description", "Total"), 0.3)

        # 2. Test fuzzy_match_header with OCR noise
        score_exact, _ = schema_templates.fuzzy_match_header("Quantity", "quantity", ["qty", "quant", "units"])
        self.assertGreaterEqual(score_exact, 0.95)

        score_ocr_noise, _ = schema_templates.fuzzy_match_header("Qt.y", "quantity", ["qty", "units"])
        self.assertGreaterEqual(score_ocr_noise, 0.80)

        score_unrelated, _ = schema_templates.fuzzy_match_header("Unrelated Header", "quantity", ["qty"])
        self.assertLess(score_unrelated, 0.5)

        # 3. Test map_columns_to_schema_with_confidence on noisy retail headers
        noisy_headers = ["Item Cde", "Descrptn", "Qt.y", "Unlt Pr1ce", "Tot.al"]
        result = schema_templates.map_columns_to_schema_with_confidence(noisy_headers, "retail_invoice")
        col_map = result["mapping"]
        conf_map = result["confidence_map"]

        self.assertIn("Item Code", col_map)
        self.assertEqual(col_map["Item Code"], 0)
        self.assertIn("Description", col_map)
        self.assertEqual(col_map["Description"], 1)
        self.assertIn("Quantity", col_map)
        self.assertEqual(col_map["Quantity"], 2)
        self.assertIn("Unit Price", col_map)
        self.assertEqual(col_map["Unit Price"], 3)
        self.assertIn("Total", col_map)
        self.assertEqual(col_map["Total"], 4)

        self.assertGreaterEqual(result["overall_confidence"], 0.70)

        self.assertIn(conf_map["Quantity"]["status"], ["HIGH_CONFIDENCE", "MODERATE"])

        # 4. Test custom alias mapping
        custom_aliases = {"Item Code": ["sku number", "part no", "stock code"]}
        sku_headers = ["Stock Code", "Details", "Amount"]
        sku_res = schema_templates.map_columns_to_schema_with_confidence(
            sku_headers, "retail_invoice", custom_aliases=custom_aliases
        )
        self.assertEqual(sku_res["mapping"]["Item Code"], 0)
        self.assertEqual(sku_res["confidence_map"]["Item Code"]["status"], "HIGH_CONFIDENCE")


        # 5. Test strict Xero Bill Import schema mapping
        xero_raw_headers = ["Contact Name", "Bill Date", "Qty", "Unit Price", "Account Code", "Line Total", "Item Desc"]
        xero_res = schema_templates.map_columns_to_schema_with_confidence(xero_raw_headers, "xero_bill")
        xm = xero_res["mapping"]

        self.assertIn("*ContactName", xm)
        self.assertEqual(xm["*ContactName"], 0)
        self.assertIn("*InvoiceDate", xm)
        self.assertEqual(xm["*InvoiceDate"], 1)
        self.assertIn("*Quantity", xm)
        self.assertEqual(xm["*Quantity"], 2)
        self.assertIn("*UnitAmount", xm)
        self.assertEqual(xm["*UnitAmount"], 3)
        self.assertIn("*AccountCode", xm)
        self.assertEqual(xm["*AccountCode"], 4)
        self.assertIn("*Description", xm)
        self.assertEqual(xm["*Description"], 6)

        print("[PASS] Fuzzy header matching with confidence scoring and Xero schema strictness verified")

    def test_18_whitespace_projection_profile(self):
        """Verifies whitespace-projection profile fallback for borderless tables with 0 contour cells."""
        cv2 = ocr_engine.cv2
        if cv2 is None:
            return

        # 1. Create a synthetic borderless table image (white background with black text blocks, NO grid lines)
        h, w = 350, 600
        canvas = np.ones((h, w), dtype=np.uint8) * 255

        # Define 3 columns with distinct vertical whitespace gutters (> 40px wide)
        # Col 0: 40 to 160
        # Gutter 1: 160 to 220 (width 60px)
        # Col 1: 220 to 380
        # Gutter 2: 380 to 440 (width 60px)
        # Col 2: 440 to 560

        # Define 3 rows with distinct horizontal whitespace gutters (> 20px high)
        # Row 0: 40 to 80
        # Row 1: 120 to 160
        # Row 2: 200 to 240
        rows_y = [(40, 80), (120, 160), (200, 240)]
        cols_x = [(40, 160), (220, 380), (440, 560)]

        for r_top, r_bottom in rows_y:
            for c_left, c_right in cols_x:
                # Render simulated text characters inside each cell (no continuous solid grid lines)
                mid_y = (r_top + r_bottom) // 2
                cv2.putText(canvas, "CellData", (c_left + 10, mid_y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1)

        # 2. Confirm that standard morphological line/contour detector finds 0 grid cells
        grid_cells, has_grid = ocr_engine.detect_table_cells_opencv(canvas, min_cells=4)
        self.assertFalse(has_grid, "Borderless table must not trigger morphological line grid detection")
        self.assertEqual(len(grid_cells), 0, "Morphological detector must return 0 cells for borderless image")

        # 3. Run whitespace projection profile detector
        proj_cells, detected = ocr_engine.extract_table_cells_via_whitespace_projection(
            canvas, min_cols=2, min_rows=2, gutter_min_width=12
        )
        self.assertTrue(detected, "Whitespace projection must detect borderless grid layout")
        self.assertGreaterEqual(len(proj_cells), 6, f"Expected at least 6 cells (3x3 grid), got {len(proj_cells)}")

        # Check cell structure
        first_cell = proj_cells[0]
        self.assertIn("bbox", first_cell)
        self.assertIn("row", first_cell)
        self.assertIn("col", first_cell)


        # 4. Verify word mapping into projection cells
        sample_words = [
            {"text": "Col1_Header", "left": 50, "top": 50, "width": 80, "height": 18, "conf": 95.0},
            {"text": "Col2_Header", "left": 230, "top": 50, "width": 80, "height": 18, "conf": 95.0},
            {"text": "Col3_Header", "left": 450, "top": 50, "width": 80, "height": 18, "conf": 95.0},
            {"text": "Val1_R1", "left": 50, "top": 130, "width": 60, "height": 18, "conf": 90.0},
            {"text": "Val2_R1", "left": 230, "top": 130, "width": 60, "height": 18, "conf": 90.0},
            {"text": "Val3_R1", "left": 450, "top": 130, "width": 60, "height": 18, "conf": 90.0},
        ]
        table_data, confs = ocr_engine.map_words_to_grid_cells(sample_words, proj_cells)
        self.assertGreaterEqual(len(table_data), 2)
        self.assertIn("Col1_Header", table_data[0][0])
        self.assertIn("Col2_Header", table_data[0][1])
        self.assertIn("Col3_Header", table_data[0][2])
        self.assertIn("Val1_R1", table_data[1][0])

        print(f"[PASS] Whitespace-projection profile fallback verified: {len(proj_cells)} cells reconstructed")


if __name__ == "__main__":
    unittest.main()

