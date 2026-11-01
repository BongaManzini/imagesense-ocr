# ImageSense – Document-to-Spreadsheet & Accounting Pipeline for SMMEs

A dependable document intelligence, table extraction, and accounting import pipeline built for small businesses (SMMEs). Takes raw photos (WhatsApp slips, supplier notes, mobile camera snapshots) and scanned PDFs, removes shadows, flattens camera angles, extracts cell-by-cell table structures, validates arithmetic math (`Qty × Unit Price == Total`), and exports directly into **Sage Pastel, Xero, QuickBooks Online, and styled Microsoft Excel spreadsheets**.

---

## The Engineering Problem: Tesseract vs. Tables

Standard Optical Character Recognition (OCR) engines scan left-to-right and top-to-bottom. Without explicit structural layout bounding boxes, adjacent columns merge into garbled text strings, and empty cells cause column-shift errors.

**ImageSense solves this with an end-to-end SMME pipeline:**
1. **Camera Preprocessing** – Automatic 4-point perspective warp (flattening angled camera shots taken on smartphones) and morphological background subtraction for shadow/lighting removal.
2. **OpenCV Morphological Cell Detection** – Isolates horizontal and vertical grid lines to detect explicit table cells, mapping OCR tokens cell-by-cell to guarantee column separation.
3. **SMME Industry Schema Templates** – Classifies documents into standardized schemas for Retail, Logistics, Construction, Medical Clinics, Education, and Banking.
4. **Mathematical & Format Integrity Audit** – Verifies line item equations (`Quantity × Price == Total`), cleans OCR character confusions (e.g. `O` vs `0`, `l` vs `1` in numbers/SKUs), standardizes dates to ISO `YYYY-MM-DD`, and flags uncertain cells.
5. **Side-by-Side Review Station ("Human-in-the-Loop")** – Interactive dual-pane web UI: zoomable document on the left, live editable spreadsheet grid on the right with soft amber/red highlights for low-confidence or mismatched values.
6. **Direct Accounting Exports** – Formatted templates for **Sage Pastel / Sage Business Cloud**, **Xero Invoices & Bills**, **QuickBooks Online**, and typed **Microsoft Excel (.xlsx)** workbooks with formulas.

---

## Practical Use Cases Across SMME Sectors

| Sector | Source Document / Image | Extracted Output Structure | Business Value |
|---|---|---|---|
| **Retail & Spaza / Wholesale** | Handwritten delivery notes, supplier invoices, till slips | `Item Code, Description, Qty, Unit Price, VAT, Total` | Eliminates manual inventory re-keying into POS software. Math auto-verified. |
| **Logistics & Courier Services** | Photos of signed Proof of Delivery (POD) slips, waybills | `Waybill #, Recipient Name, Timestamp, Destination, Status` | Automates delivery confirmations and tracks shipment status. |
| **Construction & Contracting** | Handwritten site timesheets, material hardware slips | `Worker ID/Name, Date, Site Name, Hours/Material, Rate, Total` | Tracks daily job costing without waiting for paper dockets. |
| **Medical / Dental Clinics** | Scanned lab test results, intake forms, medicine rosters | `Date, Test/Marker, Measured Value, Unit, Reference Range` | Compiles patient trends and speeds up billing capture. |
| **Education & Tutoring Centres** | Scanned attendance registers, physical grade sheets | `Student ID, Student Name, Test 1, Test 2, Final Grade` | Instant CSV sync into school grading systems or Google Sheets. |
| **Finance & Bookkeeping** | Bank statements, merchant slips, cashbooks | `Date, Description, Debit, Credit, Balance` | Prepares bank reconciliation files for direct accounting package import. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.8+ |
| **Web Interface** | Flask, Jinja2, TailwindCSS, Lucide Icons |
| **Desktop GUI** | Tkinter, ttk |
| **OCR Engine** | Neural LSTM Tesseract 5+ (via `pytesseract`) |
| **Image Preprocessing** | OpenCV (`cv2`), Pillow (PIL), NumPy |
| **PDF Rendering** | Poppler (`pdf2image`) |
| **Accounting & Document Exports** | `openpyxl` (Excel with formulas), `python-docx` (Word), Sage / Xero / QuickBooks CSV engines |

---

## Prerequisites

Ensure Tesseract OCR and Poppler are available:

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install -y tesseract-ocr poppler-utils
```

**macOS (Homebrew):**
```bash
brew install tesseract poppler
```

**Windows:**
- Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
- Install [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases)
- Add both binaries to your system `PATH`

*(Note: On Linux, a local standalone Tesseract 5.3 binary and English trained models are pre-bundled under `./bin`).*

---

## Setup & Quick Start

1. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Web Application (Recommended):**
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:5000` in your web browser.

4. **Run the Native Desktop GUI:**
   ```bash
   python gui.py
   ```

5. **Deploy with Docker & Docker Compose (Production Ready):**
   ```bash
   # Build and start multi-worker container with Tesseract and OpenCV runtime
   docker compose up --build -d

   # Check health and live service logs
   docker compose ps
   docker compose logs -f
   ```

---

## Production Dockerization & Architecture

ImageSense-OCR includes a production-grade multi-stage `Dockerfile` and `docker-compose.yml`:
- **Stage 1 (`builder`)**: Compiles Python wheels inside `python:3.12-slim-bookworm` with minimal build dependencies.
- **Stage 2 (`runtime`)**: Minimal Bookworm image bundling `tesseract-ocr`, `libgl1`, `libglib2.0-0` (for OpenCV headless), `poppler-utils`, and `curl`. Runs as an unprivileged non-root user (`imagesense:1001`).
- **WSGI Concurrency**: Managed by `gunicorn` with 3 workers, 2 threads per worker, and 120s timeout for heavy OCR / vision workloads.
- **Persistent Storage**: Mounts `./uploads` and `./processed` directories with automated healthcheck probe (`GET /`).

---

## Fallback Architecture & Table Extraction Pipeline

When extracting tables from diverse real-world documents, ImageSense follows a multi-tier fallback pipeline:

```
[Uploaded Document / Receipt]
             │
             ▼
[Tier 1: Morphological Grid Contours] ──(Grid Found)──> [Reconstruct Structured Cells]
             │
      (0 Grid Lines / Borderless)
             ▼
[Tier 2: Whitespace Histogram Projection] ──(Gutters Found)──> [Cartesian Pseudo-Grid Cells]
  • Vertical Projection: v_proj = Σ(inv > 0, axis=0) -> Column Gutters
  • Horizontal Projection: h_proj = Σ(inv > 0, axis=1) -> Row Dividers
             │
      (Dense / Irregular)
             ▼
[Tier 3: Word Spatial Bounding Box Clustering] ──> [Dynamic Row/Col Band Slicing]
             │
      (If Hybrid / Premium Tier Enabled)
             ▼
[Tier 4: Multimodal Vision-Language Model (Gemini / Claude / Qwen-VL)]
```

---

## Accounting Schema Strictness & Fuzzy Header Matching

In `schema_templates.py`, ImageSense maps noisy OCR column text to strict accounting import specs like Xero Bill Import (`*ContactName`, `*InvoiceNumber`, `*InvoiceDate`, `*Quantity`, `*UnitAmount`, `*AccountCode`, `*TaxType`, `*Description`) and QuickBooks Online Bill Import:

- **Alphanumeric Punctuation Normalization**: Strips scanning artifacts (e.g. `Qt.y` -> `qty`, `Total:` -> `total`, `Item#` -> `item`).
- **Levenshtein Similarity Metric**: Normalizes character edit distances against target field names and synonyms.
- **Confidence Scoring & Audit Flags**:
  - `HIGH_CONFIDENCE` (Score $\ge 0.85$): Direct match or close synonym.
  - `MODERATE` (Score $0.65 - 0.84$): High token containment or slight OCR typo.
  - `LOW_CONFIDENCE` (Score $0.50 - 0.64$): Weak match flagged for human review.
  - `ORDINAL_FALLBACK` (Score $0.40$): Aligned by column index position.
  - `UNMAPPED` (Score $0.00$): Column left blank for manual mapping.
- **Custom Alias Injection**: Users can inject domain-specific aliases (e.g. `{"Item Code": ["sku number", "part no", "stock code"]}`).

---

## Interactive Review Station & REST APIs

The Web Studio features asynchronous endpoints for seamless Human-in-the-Loop workflows:

- `POST /upload` – Ingests single documents or large multi-document batches.
- `GET /preview/<filename>` – Serves original, preprocessed, or bounding box overlay images.
- `GET /batch/<batch_id>` – Restores batch processing summary from saved metadata.
- `GET /batch/<batch_id>/review/<item_index>` – Drills down into any document from a batch inside the dual-pane Review & Audit Station.
- `POST /api/audit` – Evaluates arithmetic expressions, dates, and column completeness on edited table grids.
- `POST /api/auto_repair` – One-click repair of OCR character confusions (e.g. `O` vs `0` in SKUs/numbers) and date standardization.
- `POST /api/llm_refine` – Hybrid Vision/LLM validation using Google Gemini Flash or offline heuristic fallback.
- `POST /api/save_and_export` – Saves modified grid data and regenerates all download formats (Excel, Sage Pastel, Xero, QuickBooks, CSV, Word, JSON) on the fly.

---

## Running the Automated Test Suite

Run the comprehensive 18-step test suite covering OCR reading, perspective warping, shadow removal, morphological grid extraction, whitespace histogram projection, schema classification, fuzzy header confidence scoring, arithmetic equations, accounting exports, web routes, batch drilldown, hybrid LLM validation, Strategy Pattern tiers, TEDS evaluation, and desktop GUI architecture:

```bash
python test_pipeline.py
```

---

## Project Structure

```
ImageSense-OCR/
├── app.py                # Flask web server, batch drill-down & review station API endpoints
├── ocr_engine.py         # Perspective warping, shadow removal, whitespace projection & grid OCR
├── audit_engine.py       # Equation auditing (Qty × Price == Total), date check & confusion repair
├── schema_templates.py   # SMME schemas, fuzzy header matcher & Sage/Xero/QuickBooks CSV formatters
├── engine_strategy.py    # Strategy Pattern (Free Local vs Premium VLM vs Hybrid Resilient)
├── teds_evaluator.py     # Academic Tree-Edit-Distance-based Similarity (TEDS) benchmark engine
├── llm_validator.py      # Hybrid Vision/LLM post-processing (Gemini Flash + heuristic fallback)
├── gui.py                # Native desktop GUI Studio with live audit badge & accounting exports
├── test_pipeline.py      # Automated 18-test validation suite
├── Dockerfile            # Multi-stage production container definition
├── docker-compose.yml    # Multi-container orchestration with resource limits and healthchecks
├── requirements.txt      # Python dependencies (OpenCV headless, NumPy, Gunicorn, Pillow, etc.)
├── bin/                  # Bundled Tesseract binary and tessdata models
├── templates/
│   ├── index.html        # Upload portal with SMME schema selectors & use-case showcase
│   └── result.html       # Dual-pane Review Station, interactive spreadsheet & AI refine modal
├── sample_data/          # Sample invoices, test data, and exports
├── uploads/              # Temporary upload directory (auto-purged)
└── processed/            # Exported workbooks, accounting CSVs & archives (auto-purged)
```

---

## License

This project is licensed under the **MIT License**.

