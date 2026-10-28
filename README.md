# ImageSense – OCR to Excel Converter

A web-based application that leverages Optical Character Recognition (OCR) to extract text from images and PDF documents and export the results into structured Excel spreadsheets.

---

## Features

- **Image Upload** – Accepts common image formats (PNG, JPG, JPEG, TIFF, BMP)
- **PDF Upload** – Processes single and multi-page PDF documents
- **OCR Text Extraction** – Uses Tesseract OCR to accurately extract text from uploaded files
- **Excel Export** – Outputs extracted text into neatly formatted `.xlsx` Excel files
- **Web Interface** – Clean, browser-based UI powered by Flask — no desktop app required
- **Multi-page PDF Support** – Each PDF page is processed individually via Poppler

---

## Tech Stack

| Layer    | Technology             |
|--------------|-------------------------------------|
| Language   | Python 3.8+             |
| Web Framework| Flask                |
| OCR Engine  | Tesseract OCR (via `pytesseract`)  |
| PDF Renderer | Poppler (via `pdf2image`)      |
| Image Processing | Pillow (PIL)          |
| Excel Output | openpyxl              |
| Word Support | python-docx             |

---

## Prerequisites

Before running the application, install the following system dependencies:

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
- Add both to your system `PATH`

---

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/ImageSense.git
   cd ImageSense/ocr-to-excel
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Linux / macOS
   source venv/bin/activate
   # Windows
   venv\Scripts\activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open your browser and navigate to:**
   ```
   http://127.0.0.1:5000
   ```

---

## Usage

1. Open the web interface at `http://127.0.0.1:5000`.
2. Click **Upload** and select an image (PNG, JPG, TIFF, BMP) or a PDF file.
3. Click **Convert** to start the OCR extraction process.
4. Once processing is complete, click **Download** to save the generated `.xlsx` Excel file.

> **Tip:** For best OCR accuracy, use high-resolution, well-lit images with clear, legible text.

---

## Project Structure

```
ImageSense/
├── ocr-to-excel/
│  ├── app.py       # Main Flask application
│  ├── requirements.txt  # Python dependencies
│  ├── templates/     # HTML templates (Jinja2)
│  ├── uploads/      # Temporary uploaded files
│  └── processed/     # Generated Excel output files
└── project_root/
    └── app/
        ├── static/         # CSS, JS, and static assets
        ├── templates/      # Additional HTML templates
        ├── uploads/        # Upload storage
        └── excel_files/    # Exported Excel files
```

---

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2024 ImageSense Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
