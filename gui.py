"""
ImageSense - Desktop GUI Studio
A modern, native desktop application for Optical Character Recognition (OCR) and Table Extraction.
Features:
- Dual-pane interface: document preview with bounding box overlay and interactive spreadsheet grid
- Live preprocessing (Auto, Invoice/Table, Receipt, Clean Document, Raw) with Deskew
- In-place editable spreadsheet table with row/column manipulation
- Real-time confidence scoring metrics
- Multi-format export: Excel (.xlsx), CSV (.csv), Word (.docx), and Clipboard
- Multi-page PDF support with page navigation
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, List, Dict, Any
from PIL import Image, ImageTk

# Import core high-accuracy OCR engine, audit engine, and SMME schemas
import ocr_engine
import audit_engine
import schema_templates


class ImageSenseDesktopGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("ImageSense OCR Studio")
        self.geometry("1280x820")
        self.minsize(1000, 680)

        # Application state
        self.current_file_path: Optional[str] = None
        self.current_page: int = 1
        self.total_pages: int = 1
        self.original_image: Optional[Image.Image] = None
        self.preprocessed_image: Optional[Image.Image] = None
        self.overlay_image: Optional[Image.Image] = None
        self.active_preview_mode: str = "overlay"  # "original", "preprocessed", "overlay"
        self.ocr_result: Optional[Dict[str, Any]] = None
        self.table_data: List[List[str]] = []
        self.is_processing: bool = False
        self.detected_schema_id: str = "retail_invoice"
        self.audit_data: Dict[str, Any] = {}

        # Apply dark modern slate theme
        self.setup_theme()

        # Build UI layout
        self.build_top_bar()
        self.build_main_panels()
        self.build_status_bar()

        # Load sample file if available
        sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_data", "sample_invoice.png"))
        if os.path.exists(sample_path):
            self.load_file(sample_path)

    # -----------------------------------------------------------------------
    # Modern Slate Dark Styling
    # -----------------------------------------------------------------------
    def setup_theme(self):
        self.configure(bg="#0B132B")  # Dark background

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Color definitions
        self.colors = {
            "bg": "#0B132B",
            "panel_bg": "#1C2541",
            "card_bg": "#1F2937",
            "border": "#374151",
            "accent": "#4F46E5",       # Indigo
            "accent_hover": "#6366F1",
            "emerald": "#10B981",
            "amber": "#F59E0B",
            "rose": "#EF4444",
            "text": "#F9FAFB",
            "text_muted": "#9CA3AF"
        }

        # Global widget styling
        self.style.configure(".", background=self.colors["panel_bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("TFrame", background=self.colors["panel_bg"])
        self.style.configure("Card.TFrame", background=self.colors["card_bg"], relief="flat")
        self.style.configure("TLabel", background=self.colors["panel_bg"], foreground=self.colors["text"])
        self.style.configure("Card.TLabel", background=self.colors["card_bg"], foreground=self.colors["text"])
        self.style.configure("Muted.TLabel", foreground=self.colors["text_muted"], font=("Segoe UI", 9))
        self.style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground=self.colors["text"])
        self.style.configure("Badge.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.colors["emerald"])

        # Buttons
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.colors["accent"], foreground="#FFFFFF", borderwidth=0, padding=6)
        self.style.map("Primary.TButton", background=[("active", self.colors["accent_hover"])])

        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), background=self.colors["emerald"], foreground="#FFFFFF", borderwidth=0, padding=6)
        self.style.map("Success.TButton", background=[("active", "#059669")])

        self.style.configure("Secondary.TButton", font=("Segoe UI", 9), background=self.colors["card_bg"], foreground=self.colors["text"], borderwidth=1, bordercolor=self.colors["border"], padding=4)
        self.style.map("Secondary.TButton", background=[("active", "#374151")])

        # Notebook tabs
        self.style.configure("TNotebook", background=self.colors["panel_bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=self.colors["card_bg"], foreground=self.colors["text_muted"], font=("Segoe UI", 10, "bold"), padding=[12, 6])
        self.style.map("TNotebook.Tab", background=[("selected", self.colors["accent"])], foreground=[("selected", "#FFFFFF")])

        # Treeview (Spreadsheet)
        self.style.configure(
            "Treeview",
            background="#111827",
            foreground="#E5E7EB",
            fieldbackground="#111827",
            rowheight=26,
            font=("Consolas", 10),
            borderwidth=0
        )
        self.style.configure(
            "Treeview.Heading",
            background="#1E293B",
            foreground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=[6, 6]
        )
        self.style.map("Treeview", background=[("selected", self.colors["accent"])], foreground=[("selected", "#FFFFFF")])

        # Progress bar
        self.style.configure("Horizontal.TProgressbar", background=self.colors["accent"], troughcolor=self.colors["card_bg"], borderwidth=0)

    # -----------------------------------------------------------------------
    # Top Control Bar
    # -----------------------------------------------------------------------
    def build_top_bar(self):
        top_frame = tk.Frame(self, bg=self.colors["card_bg"], height=65, highlightthickness=1, highlightbackground=self.colors["border"])
        top_frame.pack(side=tk.TOP, fill=tk.X)
        top_frame.pack_propagate(False)

        # Brand Title
        brand_frame = tk.Frame(top_frame, bg=self.colors["card_bg"])
        brand_frame.pack(side=tk.LEFT, padx=16, pady=10)

        title_lbl = tk.Label(brand_frame, text=" ImageSense OCR", font=("Segoe UI", 13, "bold"), bg=self.colors["card_bg"], fg="#FFFFFF")
        title_lbl.pack(anchor="w")
        sub_lbl = tk.Label(brand_frame, text="Neural Document & Table Extractor", font=("Segoe UI", 8), bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        sub_lbl.pack(anchor="w")

        # Open File Button
        open_btn = tk.Button(
            top_frame,
            text=" Open Document",
            command=self.choose_file_dialog,
            bg="#374151",
            fg="#FFFFFF",
            activebackground="#4B5563",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2"
        )
        open_btn.pack(side=tk.LEFT, padx=6, pady=14)

        # Batch Process Button
        batch_btn = tk.Button(
            top_frame,
            text=" Batch Process",
            command=self.open_batch_dialog,
            bg="#1E293B",
            fg="#38BDF8",
            activebackground="#334155",
            activeforeground="#38BDF8",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2"
        )
        batch_btn.pack(side=tk.LEFT, padx=6, pady=14)

        # Separator
        sep1 = tk.Frame(top_frame, width=1, bg=self.colors["border"])
        sep1.pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=10)

        # Preprocessing Preset Selector
        preset_frame = tk.Frame(top_frame, bg=self.colors["card_bg"])
        preset_frame.pack(side=tk.LEFT, padx=6, pady=8)
        tk.Label(preset_frame, text="Preset Mode", font=("Segoe UI", 8), bg=self.colors["card_bg"], fg=self.colors["text_muted"]).pack(anchor="w")
        
        self.preset_var = tk.StringVar(value="auto")
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=["auto", "invoice", "receipt", "clean_document", "raw"],
            state="readonly",
            width=12,
            font=("Segoe UI", 9)
        )
        self.preset_combo.pack()

        # Industry SMME Schema Selector
        schema_frame = tk.Frame(top_frame, bg=self.colors["card_bg"])
        schema_frame.pack(side=tk.LEFT, padx=6, pady=8)
        tk.Label(schema_frame, text="Industry Schema", font=("Segoe UI", 8), bg=self.colors["card_bg"], fg=self.colors["text_muted"]).pack(anchor="w")

        self.schema_var = tk.StringVar(value="auto")
        schema_options = ["auto", "retail_invoice", "logistics_waybill", "construction_timesheet", "medical_lab", "education_grades", "manufacturing_qc", "generic_grid"]
        self.schema_combo = ttk.Combobox(
            schema_frame,
            textvariable=self.schema_var,
            values=schema_options,
            state="readonly",
            width=16,
            font=("Segoe UI", 9)
        )
        self.schema_combo.pack()

        # Preprocessing Toggles: Deskew, Perspective Flattening, Shadow Removal
        toggles_frame = tk.Frame(top_frame, bg=self.colors["card_bg"])
        toggles_frame.pack(side=tk.LEFT, padx=8, pady=8)

        self.deskew_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            toggles_frame, text="Deskew", variable=self.deskew_var,
            bg=self.colors["card_bg"], fg=self.colors["text"], selectcolor=self.colors["panel_bg"],
            activebackground=self.colors["card_bg"], activeforeground=self.colors["text"], font=("Segoe UI", 8), bd=0
        ).pack(side=tk.LEFT, padx=2)

        self.perspective_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            toggles_frame, text="Perspective", variable=self.perspective_var,
            bg=self.colors["card_bg"], fg=self.colors["text"], selectcolor=self.colors["panel_bg"],
            activebackground=self.colors["card_bg"], activeforeground=self.colors["text"], font=("Segoe UI", 8), bd=0
        ).pack(side=tk.LEFT, padx=2)

        self.shadows_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            toggles_frame, text="Shadow Clean", variable=self.shadows_var,
            bg=self.colors["card_bg"], fg=self.colors["text"], selectcolor=self.colors["panel_bg"],
            activebackground=self.colors["card_bg"], activeforeground=self.colors["text"], font=("Segoe UI", 8), bd=0
        ).pack(side=tk.LEFT, padx=2)

        # Page Segmentation Mode (PSM)
        psm_frame = tk.Frame(top_frame, bg=self.colors["card_bg"])
        psm_frame.pack(side=tk.LEFT, padx=6, pady=8)
        tk.Label(psm_frame, text="PSM", font=("Segoe UI", 8), bg=self.colors["card_bg"], fg=self.colors["text_muted"]).pack(anchor="w")

        self.psm_var = tk.IntVar(value=6)
        self.psm_combo = ttk.Combobox(
            psm_frame,
            textvariable=self.psm_var,
            values=[6, 3, 4, 11],
            state="readonly",
            width=4,
            font=("Segoe UI", 9)
        )
        self.psm_combo.pack()

        # Primary Action: Run OCR
        self.run_btn = tk.Button(
            top_frame,
            text=" Run OCR & Extract Table",
            command=self.start_ocr_thread,
            bg=self.colors["accent"],
            fg="#FFFFFF",
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2"
        )
        self.run_btn.pack(side=tk.RIGHT, padx=16, pady=14)

    # -----------------------------------------------------------------------
    # Main Panes: Document Preview & Extracted Spreadsheet
    # -----------------------------------------------------------------------
    def build_main_panels(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=self.colors["bg"], bd=0, sashwidth=4, sashrelief="flat")
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # LEFT PANE: Document Preview
        left_frame = tk.Frame(paned, bg=self.colors["panel_bg"], highlightthickness=1, highlightbackground=self.colors["border"])
        paned.add(left_frame, minsize=420, width=540)

        # Preview Header & View Mode Switcher
        prev_head = tk.Frame(left_frame, bg=self.colors["panel_bg"], height=42)
        prev_head.pack(fill=tk.X, padx=12, pady=6)

        tk.Label(prev_head, text="Document Preview", font=("Segoe UI", 11, "bold"), bg=self.colors["panel_bg"], fg="#FFFFFF").pack(side=tk.LEFT)

        # View Mode Radio Buttons
        self.view_mode_var = tk.StringVar(value="overlay")
        for mode, lbl in [("overlay", "Boxes"), ("preprocessed", "Preprocessed"), ("original", "Original")]:
            rb = tk.Radiobutton(
                prev_head,
                text=lbl,
                value=mode,
                variable=self.view_mode_var,
                command=self.update_preview_display,
                bg=self.colors["panel_bg"],
                fg=self.colors["text_muted"],
                activebackground=self.colors["panel_bg"],
                activeforeground=self.colors["text"],
                selectcolor=self.colors["card_bg"],
                font=("Segoe UI", 8),
                bd=0
            )
            rb.pack(side=tk.RIGHT, padx=4)

        # Preview Canvas
        self.canvas_frame = tk.Frame(left_frame, bg="#0F172A")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self.preview_canvas = tk.Canvas(self.canvas_frame, bg="#0F172A", bd=0, highlightthickness=0)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Configure>", lambda e: self.update_preview_display())

        # PDF Page Selector Bar (visible for PDFs)
        self.pdf_bar = tk.Frame(left_frame, bg=self.colors["panel_bg"], height=34)
        self.pdf_bar.pack(fill=tk.X, padx=10, pady=4)

        self.prev_page_btn = tk.Button(
            self.pdf_bar, text="◀ Prev Page", command=self.prev_pdf_page,
            bg=self.colors["card_bg"], fg=self.colors["text"], bd=0, padx=8, pady=2, font=("Segoe UI", 8), cursor="hand2"
        )
        self.prev_page_btn.pack(side=tk.LEFT)

        self.page_lbl = tk.Label(self.pdf_bar, text="Page 1 of 1", font=("Segoe UI", 8), bg=self.colors["panel_bg"], fg=self.colors["text_muted"])
        self.page_lbl.pack(side=tk.LEFT, padx=10)

        self.next_page_btn = tk.Button(
            self.pdf_bar, text="Next Page ▶", command=self.next_pdf_page,
            bg=self.colors["card_bg"], fg=self.colors["text"], bd=0, padx=8, pady=2, font=("Segoe UI", 8), cursor="hand2"
        )
        self.next_page_btn.pack(side=tk.LEFT)

        self.pdf_bar.pack_forget()  # Hidden until PDF loaded

        # RIGHT PANE: Results, Confidence, Spreadsheet Grid, Export
        right_frame = tk.Frame(paned, bg=self.colors["panel_bg"], highlightthickness=1, highlightbackground=self.colors["border"])
        paned.add(right_frame, minsize=520)

        # Top Stats & Metric Banner
        self.metric_bar = tk.Frame(right_frame, bg=self.colors["card_bg"], height=54, highlightthickness=1, highlightbackground=self.colors["border"])
        self.metric_bar.pack(fill=tk.X, padx=10, pady=8)
        self.metric_bar.pack_propagate(False)

        self.conf_badge = tk.Label(
            self.metric_bar,
            text="Accuracy: --",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.conf_badge.pack(side=tk.LEFT, padx=10, pady=12)

        self.audit_badge = tk.Label(
            self.metric_bar,
            text="Audit: Ready",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["emerald"]
        )
        self.audit_badge.pack(side=tk.LEFT, padx=8, pady=12)

        self.stats_lbl = tk.Label(
            self.metric_bar,
            text="No document analyzed yet",
            font=("Segoe UI", 8),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.stats_lbl.pack(side=tk.LEFT, padx=8, pady=12)

        # Export Action Buttons (Excel, Sage Pastel, Xero, QuickBooks, CSV, Word)
        export_frame = tk.Frame(self.metric_bar, bg=self.colors["card_bg"])
        export_frame.pack(side=tk.RIGHT, padx=6, pady=8)

        self.excel_btn = tk.Button(
            export_frame, text=" Excel", command=self.export_excel_action,
            bg=self.colors["emerald"], fg="#FFFFFF", font=("Segoe UI", 8, "bold"), bd=0, padx=8, pady=4, cursor="hand2"
        )
        self.excel_btn.pack(side=tk.LEFT, padx=2)

        self.sage_btn = tk.Button(
            export_frame, text=" Sage", command=self.export_sage_pastel_action,
            bg="#0284C7", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), bd=0, padx=6, pady=4, cursor="hand2"
        )
        self.sage_btn.pack(side=tk.LEFT, padx=2)

        self.xero_btn = tk.Button(
            export_frame, text=" Xero", command=self.export_xero_action,
            bg="#0369A1", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), bd=0, padx=6, pady=4, cursor="hand2"
        )
        self.xero_btn.pack(side=tk.LEFT, padx=2)

        self.qb_btn = tk.Button(
            export_frame, text=" QB", command=self.export_quickbooks_action,
            bg="#2E7D32", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), bd=0, padx=6, pady=4, cursor="hand2"
        )
        self.qb_btn.pack(side=tk.LEFT, padx=2)

        self.csv_btn = tk.Button(
            export_frame, text=" CSV", command=self.export_csv_action,
            bg="#374151", fg="#FFFFFF", font=("Segoe UI", 8), bd=0, padx=6, pady=4, cursor="hand2"
        )
        self.csv_btn.pack(side=tk.LEFT, padx=2)

        self.docx_btn = tk.Button(
            export_frame, text=" Word", command=self.export_docx_action,
            bg="#374151", fg="#FFFFFF", font=("Segoe UI", 8), bd=0, padx=6, pady=4, cursor="hand2"
        )
        self.docx_btn.pack(side=tk.LEFT, padx=2)

        # Results Notebook: Table vs Raw Text
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # TAB 1: Editable Spreadsheet Grid
        table_tab = tk.Frame(self.notebook, bg=self.colors["panel_bg"])
        self.notebook.add(table_tab, text="  Spreadsheet Grid  ")

        # Table Control Toolbar (Add/Delete row, Copy, Auto-Clean, Re-verify)
        grid_toolbar = tk.Frame(table_tab, bg=self.colors["panel_bg"], height=32)
        grid_toolbar.pack(fill=tk.X, pady=4)

        tk.Button(
            grid_toolbar, text=" Add Row", command=self.add_table_row,
            bg=self.colors["card_bg"], fg=self.colors["text"], font=("Segoe UI", 8), bd=0, padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            grid_toolbar, text=" Delete Row", command=self.delete_table_row,
            bg=self.colors["card_bg"], fg=self.colors["text"], font=("Segoe UI", 8), bd=0, padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            grid_toolbar, text=" Copy Table", command=self.copy_table_to_clipboard,
            bg=self.colors["card_bg"], fg=self.colors["text"], font=("Segoe UI", 8), bd=0, padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            grid_toolbar, text="✨ Auto-Clean Confusions", command=self.auto_clean_confusions_action,
            bg="#312E81", fg="#A5B4FC", font=("Segoe UI", 8, "bold"), bd=0, padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            grid_toolbar, text="🧮 Re-Verify Math", command=self.recalculate_audit_action,
            bg=self.colors["card_bg"], fg=self.colors["text"], font=("Segoe UI", 8), bd=0, padx=8, pady=3, cursor="hand2"
        ).pack(side=tk.LEFT, padx=2)

        tip_lbl = tk.Label(grid_toolbar, text=" Tip: Double-click any cell to edit in-place", font=("Segoe UI", 8, "italic"), bg=self.colors["panel_bg"], fg=self.colors["text_muted"])
        tip_lbl.pack(side=tk.RIGHT, padx=4)

        # Treeview + Scrollbars
        tree_container = tk.Frame(table_tab, bg="#111827")
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_container, selectmode="browse", show="headings")
        self.v_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.h_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Double click to edit cell
        self.tree.bind("<Double-1>", self.on_double_click_cell)

        # TAB 2: Raw Recognized OCR Text
        text_tab = tk.Frame(self.notebook, bg=self.colors["panel_bg"])
        self.notebook.add(text_tab, text="  Raw OCR Text  ")

        self.raw_text_box = tk.Text(
            text_tab,
            bg="#111827",
            fg="#E5E7EB",
            insertbackground="#FFFFFF",
            font=("Consolas", 10),
            bd=0,
            padx=12,
            pady=12,
            wrap=tk.WORD
        )
        text_v_scroll = ttk.Scrollbar(text_tab, orient=tk.VERTICAL, command=self.raw_text_box.yview)
        self.raw_text_box.configure(yscrollcommand=text_v_scroll.set)
        self.raw_text_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # -----------------------------------------------------------------------
    # Status Bar & Animated Progress
    # -----------------------------------------------------------------------
    def build_status_bar(self):
        status_frame = tk.Frame(self, bg=self.colors["card_bg"], height=28, highlightthickness=1, highlightbackground=self.colors["border"])
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)

        self.status_lbl = tk.Label(status_frame, text="Ready", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        self.status_lbl.pack(side=tk.LEFT, padx=12, pady=4)

        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate", length=140)
        # Pack only when processing

    def set_status(self, text: str, is_busy: bool = False):
        self.status_lbl.configure(text=text)
        if is_busy:
            self.progress_bar.pack(side=tk.RIGHT, padx=12, pady=4)
            self.progress_bar.start(10)
            self.run_btn.configure(state=tk.DISABLED, bg="#4B5563")
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.run_btn.configure(state=tk.NORMAL, bg=self.colors["accent"])

    # -----------------------------------------------------------------------
    # File Loading & Preview
    # -----------------------------------------------------------------------
    def choose_file_dialog(self):
        path = filedialog.askopenfilename(
            title="Select Image or PDF Document",
            filetypes=[
                ("All Supported Files", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp;*.pdf"),
                ("Images", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp"),
                ("PDF Documents", "*.pdf")
            ]
        )
        if path:
            self.load_file(path)

    def open_batch_dialog(self):
        paths = filedialog.askopenfilenames(
            title="Select Multiple Images or PDF Documents for Batch Processing",
            filetypes=[
                ("All Supported Files", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp;*.pdf"),
                ("Images", "*.png;*.jpg;*.jpeg;*.webp;*.tiff;*.bmp"),
                ("PDF Documents", "*.pdf")
            ]
        )
        if not paths:
            return

        export_target = filedialog.asksaveasfilename(
            title="Save Combined Master Excel Workbook",
            defaultextension=".xlsx",
            filetypes=[("Excel Master Workbook", "*.xlsx")]
        )
        if not export_target:
            return

        self.set_busy(True, f"Batch processing {len(paths)} files...")

        def _batch_worker():
            try:
                preset = self.preset_var.get()
                deskew = self.deskew_var.get()
                psm = self.psm_var.get()

                batch_res = ocr_engine.batch_process_files(
                    list(paths),
                    preset=preset,
                    deskew=deskew,
                    psm=psm,
                    max_workers=4
                )
                ocr_engine.export_batch_to_excel(batch_res, export_target)
                self.after(0, self._on_batch_complete, batch_res, export_target)
            except Exception as e:
                self.after(0, self._on_batch_error, str(e))

        threading.Thread(target=_batch_worker, daemon=True).start()

    def _on_batch_complete(self, batch_res: Dict[str, Any], dest: str):
        self.set_busy(False)
        self.set_status(f"Batch completed: {batch_res['processed_files']} files saved to {os.path.basename(dest)}")
        messagebox.showinfo(
            "Batch Processing Complete",
            f"Successfully processed {batch_res['processed_files']} files ({batch_res['total_pages']} pages)\n"
            f"Average Accuracy: {batch_res['average_confidence']}%\n"
            f"Saved Master Excel Workbook to:\n{dest}"
        )

    def _on_batch_error(self, err: str):
        self.set_busy(False)
        self.set_status("Batch processing failed.")
        messagebox.showerror("Batch Error", f"Batch processing failed:\n{err}")

    def load_file(self, file_path: str):
        self.current_file_path = file_path
        self.current_page = 1
        self.total_pages = 1

        is_pdf = file_path.lower().endswith(".pdf")
        if is_pdf:
            self.pdf_bar.pack(fill=tk.X, padx=10, pady=4)
            # Check page count
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                self.total_pages = len(reader.pages)
            except Exception:
                self.total_pages = 1
            self.page_lbl.configure(text=f"Page {self.current_page} of {self.total_pages}")
        else:
            self.pdf_bar.pack_forget()

        try:
            if is_pdf:
                from pdf2image import convert_from_path
                pages = convert_from_path(file_path, first_page=1, last_page=1)
                self.original_image = pages[0]
            else:
                self.original_image = Image.open(file_path).convert("RGB")

            self.preprocessed_image = None
            self.overlay_image = None
            self.view_mode_var.set("original")
            self.update_preview_display()
            self.set_status(f"Loaded: {os.path.basename(file_path)} ({self.original_image.width}x{self.original_image.height})")
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not load image:\n{e}")

    def prev_pdf_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.page_lbl.configure(text=f"Page {self.current_page} of {self.total_pages}")
            self.load_pdf_page(self.current_page)

    def next_pdf_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.page_lbl.configure(text=f"Page {self.current_page} of {self.total_pages}")
            self.load_pdf_page(self.current_page)

    def load_pdf_page(self, page_num: int):
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(self.current_file_path, first_page=page_num, last_page=page_num)
            self.original_image = pages[0]
            self.preprocessed_image = None
            self.overlay_image = None
            self.view_mode_var.set("original")
            self.update_preview_display()
            self.start_ocr_thread()
        except Exception as e:
            messagebox.showerror("Page Load Error", str(e))

    def update_preview_display(self):
        mode = self.view_mode_var.get()
        target_img = None

        if mode == "overlay" and self.overlay_image:
            target_img = self.overlay_image
        elif mode == "preprocessed" and self.preprocessed_image:
            target_img = self.preprocessed_image
        elif self.original_image:
            target_img = self.original_image

        if not target_img:
            return

        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 500, 600

        # Calculate scale to fit canvas while preserving aspect ratio
        iw, ih = target_img.size
        scale = min((cw - 20) / iw, (ch - 20) / ih)
        if scale <= 0:
            scale = 1.0

        disp_w = max(1, int(iw * scale))
        disp_h = max(1, int(ih * scale))

        resized = target_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        self.photo_img = ImageTk.PhotoImage(resized)

        self.preview_canvas.delete("all")
        # Center in canvas
        x = (cw - disp_w) // 2
        y = (ch - disp_h) // 2
        self.preview_canvas.create_image(x, y, anchor="nw", image=self.photo_img)

    # -----------------------------------------------------------------------
    # OCR Execution (Threaded for Non-Blocking UI)
    # -----------------------------------------------------------------------
    def start_ocr_thread(self):
        if not self.current_file_path:
            messagebox.showinfo("No Document", "Please open an image or PDF document first.")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.set_status("Analyzing document and running neural OCR...", is_busy=True)

        thread = threading.Thread(target=self._run_ocr_worker, daemon=True)
        thread.start()

    def _run_ocr_worker(self):
        start_time = time.time()
        preset = self.preset_var.get()
        deskew = self.deskew_var.get()
        perspective_correct = self.perspective_var.get()
        remove_shadows = self.shadows_var.get()
        schema_val = self.schema_var.get()
        psm = self.psm_var.get()

        try:
            result = ocr_engine.perform_high_accuracy_ocr(
                self.current_file_path,
                preset=preset,
                deskew=deskew,
                perspective_correct=perspective_correct,
                remove_shadows=remove_shadows,
                schema_id=schema_val,
                psm=psm,
                pdf_page=self.current_page
            )
            elapsed = time.time() - start_time
            self.after(0, self._on_ocr_success, result, elapsed)
        except Exception as e:
            self.after(0, self._on_ocr_error, str(e))

    def _on_ocr_success(self, result: Dict[str, Any], elapsed: float):
        self.is_processing = False
        self.ocr_result = result
        self.preprocessed_image = result["preprocessed_image"]
        self.overlay_image = result["overlay_image"]
        self.table_data = result["table_data"]
        self.detected_schema_id = result.get("schema_id", "retail_invoice")
        self.audit_data = result.get("audit", {})

        # Switch view to overlay boxes
        self.view_mode_var.set("overlay")
        self.update_preview_display()

        # Update metrics badge
        conf = result["confidence"]
        if conf >= 85:
            conf_color = self.colors["emerald"]
            rating = "High Accuracy"
        elif conf >= 65:
            conf_color = self.colors["amber"]
            rating = "Moderate Accuracy"
        else:
            conf_color = self.colors["rose"]
            rating = "Low Confidence"

        self.conf_badge.configure(text=f"Accuracy: {conf:.1f}% ({rating})", fg=conf_color)
        self.stats_lbl.configure(
            text=f"Words: {result['word_count']} | Rows: {result['row_count']} | Cols: {result['col_count']} | {elapsed:.2f}s"
        )

        # Update audit status badge
        self.update_audit_badge()

        # Populate Spreadsheet Treeview
        self.populate_treeview(self.table_data)

        # Populate Raw Text Tab
        self.raw_text_box.delete("1.0", tk.END)
        self.raw_text_box.insert(tk.END, result["raw_text"])

        self.set_status(f"OCR completed in {elapsed:.2f}s with {conf:.1f}% confidence.")

    def _on_ocr_error(self, err_msg: str):
        self.is_processing = False
        self.set_status("OCR processing failed.")
        messagebox.showerror("OCR Error", f"An error occurred during OCR processing:\n{err_msg}")

    # -----------------------------------------------------------------------
    # Interactive Spreadsheet Grid Handling
    # -----------------------------------------------------------------------
    def populate_treeview(self, data: List[List[str]]):
        self.tree.delete(*self.tree.get_children())

        if not data:
            self.tree["columns"] = ("Col 1",)
            self.tree.heading("Col 1", text="No Data Detected")
            return

        max_cols = max(len(row) for row in data)
        col_ids = [f"col_{i}" for i in range(max_cols)]
        self.tree["columns"] = col_ids

        # First row as headers if available, or generic Col 1..N
        headers = data[0] if data else []
        for i in range(max_cols):
            header_text = headers[i] if i < len(headers) and headers[i] else f"Column {i + 1}"
            self.tree.heading(col_ids[i], text=header_text)
            self.tree.column(col_ids[i], width=130, minwidth=70, anchor="w")

        # Insert rows (starting from row index 1 if first row is header, else 0)
        start_idx = 1 if len(data) > 1 else 0
        for r_idx in range(start_idx, len(data)):
            row_vals = data[r_idx]
            # Ensure proper length
            padded = row_vals + [""] * (max_cols - len(row_vals))
            self.tree.insert("", tk.END, values=padded)

    def on_double_click_cell(self, event):
        """Allows in-place editing of any cell in the spreadsheet grid."""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id or not column:
            return

        col_index = int(column.replace("#", "")) - 1
        current_vals = list(self.tree.item(row_id, "values"))
        if col_index >= len(current_vals):
            return

        old_val = current_vals[col_index]

        # Get cell bounding box
        bbox = self.tree.bbox(row_id, column)
        if not bbox:
            return

        x, y, width, height = bbox

        # Overlay an Entry widget on the cell
        entry = tk.Entry(self.tree, bg="#1E293B", fg="#FFFFFF", font=("Segoe UI", 10), insertbackground="#FFFFFF")
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, old_val)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def save_cell_edit(event=None):
            new_val = entry.get()
            current_vals[col_index] = new_val
            self.tree.item(row_id, values=current_vals)
            entry.destroy()
            self._sync_table_data_from_tree()

        entry.bind("<Return>", save_cell_edit)
        entry.bind("<FocusOut>", lambda e: entry.destroy())
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _sync_table_data_from_tree(self):
        """Syncs in-memory table_data with the treeview contents and recalculates audit."""
        col_names = [self.tree.heading(c)["text"] for c in self.tree["columns"]]
        rows = [col_names]
        for child in self.tree.get_children():
            rows.append(list(self.tree.item(child, "values")))
        self.table_data = rows

        # Recalculate audit
        schema_id = self.schema_var.get()
        if schema_id == "auto":
            schema_id = getattr(self, "detected_schema_id", "retail_invoice")
        self.audit_data = audit_engine.audit_document_table(self.table_data, schema_id=schema_id)
        self.update_audit_badge()

    def update_audit_badge(self):
        """Updates the top ribbon audit badge based on current audit metrics."""
        if not self.audit_data:
            self.audit_badge.configure(text="", bg=self.colors["card_bg"])
            return

        status = self.audit_data.get("status", "VERIFIED")
        math_summary = self.audit_data.get("math_summary", {})
        total_rows = math_summary.get("total_rows", 0)
        failed_rows = math_summary.get("failed", 0)

        if total_rows > 0:
            if failed_rows == 0:
                badge_text = f"✓ Math Verified ({math_summary.get('passed', 0)}/{total_rows} Rows)"
                badge_color = self.colors["emerald"]
            else:
                badge_text = f"⚠ Math Mismatch ({failed_rows} Alert{'s' if failed_rows > 1 else ''})"
                badge_color = self.colors["rose"]
        else:
            if status == "VERIFIED":
                badge_text = "✓ Schema Verified"
                badge_color = self.colors["emerald"]
            elif status == "WARNINGS":
                badge_text = "⚠ Audit Warnings"
                badge_color = self.colors["amber"]
            else:
                badge_text = "✕ Audit Flags"
                badge_color = self.colors["rose"]

        self.audit_badge.configure(text=badge_text, fg=badge_color)

    def auto_clean_confusions_action(self):
        """Auto-repairs common OCR character confusions (O vs 0, l vs 1) and standardizes dates."""
        self._sync_table_data_from_tree()
        if not self.table_data:
            return

        schema_id = self.schema_var.get()
        if schema_id == "auto":
            schema_id = getattr(self, "detected_schema_id", "retail_invoice")

        initial_audit = audit_engine.audit_document_table(self.table_data, schema_id=schema_id)
        repaired_table, changelog = audit_engine.auto_repair_table(self.table_data, initial_audit)

        self.table_data = repaired_table
        self.populate_treeview(self.table_data)
        self.recalculate_audit_action()

        if changelog:
            sample = changelog[0]
            messagebox.showinfo(
                "Auto-Clean OCR Complete",
                f"Applied {len(changelog)} character/date fixes.\n\n"
                f"Sample fix in row {sample['row']}, col {sample['col']}:\n"
                f"'{sample['original']}' → '{sample['repaired']}'\n({sample['reason']})"
            )
        else:
            messagebox.showinfo("Auto-Clean Complete", "No character confusions or date issues detected.")

    def recalculate_audit_action(self):
        """Recalculates table audit and arithmetic verification."""
        self._sync_table_data_from_tree()
        if not self.table_data:
            return

        schema_id = self.schema_var.get()
        if schema_id == "auto":
            schema_id = getattr(self, "detected_schema_id", "retail_invoice")

        self.audit_data = audit_engine.audit_document_table(self.table_data, schema_id=schema_id)
        self.update_audit_badge()

        math_summary = self.audit_data.get("math_summary", {})
        if math_summary.get("total_rows", 0) > 0:
            if math_summary.get("failed", 0) == 0:
                self.set_status(f"Math check: All {math_summary['passed']} line items verified (Qty × Unit Price == Total).")
            else:
                self.set_status(f"Math alert: {math_summary['failed']} rows have calculation mismatches.")
        else:
            self.set_status(f"Audit completed: {self.audit_data.get('overall_rating', 'Checked')}.")

    def add_table_row(self):
        if not self.tree["columns"]:
            return
        n_cols = len(self.tree["columns"])
        self.tree.insert("", tk.END, values=[""] * n_cols)
        self._sync_table_data_from_tree()

    def delete_table_row(self):
        selected = self.tree.selection()
        if selected:
            for item in selected:
                self.tree.delete(item)
            self._sync_table_data_from_tree()

    def copy_table_to_clipboard(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            return
        tsv_lines = ["\t".join(row) for row in self.table_data]
        tsv_text = "\n".join(tsv_lines)
        self.clipboard_clear()
        self.clipboard_append(tsv_text)
        self.set_status("Table copied to clipboard (TSV format).")

    # -----------------------------------------------------------------------
    # Multi-Format & Accounting Software Export Actions
    # -----------------------------------------------------------------------
    def export_excel_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to Excel Spreadsheet",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if dest:
            try:
                ocr_engine.export_to_excel(self.table_data, dest)
                self.set_status(f"Exported to Excel: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved styled Excel workbook to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export Excel file:\n{e}")

    def export_sage_pastel_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to Sage Pastel Import CSV",
            defaultextension=".csv",
            filetypes=[("Sage Pastel CSV", "*.csv")]
        )
        if dest:
            try:
                ocr_engine.export_to_sage_pastel(self.table_data, dest)
                self.set_status(f"Exported to Sage Pastel: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved Sage Pastel CSV to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export Sage Pastel file:\n{e}")

    def export_xero_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to Xero Invoice CSV",
            defaultextension=".csv",
            filetypes=[("Xero CSV Template", "*.csv")]
        )
        if dest:
            try:
                ocr_engine.export_to_xero(self.table_data, dest)
                self.set_status(f"Exported to Xero: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved Xero CSV to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export Xero file:\n{e}")

    def export_quickbooks_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to QuickBooks Online CSV",
            defaultextension=".csv",
            filetypes=[("QuickBooks Online CSV", "*.csv")]
        )
        if dest:
            try:
                ocr_engine.export_to_quickbooks(self.table_data, dest)
                self.set_status(f"Exported to QuickBooks: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved QuickBooks Online CSV to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export QuickBooks file:\n{e}")

    def export_csv_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to CSV File",
            defaultextension=".csv",
            filetypes=[("Comma Separated Values", "*.csv")]
        )
        if dest:
            try:
                ocr_engine.export_to_csv(self.table_data, dest)
                self.set_status(f"Exported to CSV: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved CSV file to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export CSV file:\n{e}")

    def export_docx_action(self):
        self._sync_table_data_from_tree()
        if not self.table_data:
            messagebox.showinfo("No Data", "No table data available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export to Word Document",
            defaultextension=".docx",
            filetypes=[("Microsoft Word Document", "*.docx")]
        )
        if dest:
            try:
                raw_txt = self.raw_text_box.get("1.0", tk.END).strip()
                ocr_engine.export_to_docx(self.table_data, raw_txt, dest)
                self.set_status(f"Exported to Word: {os.path.basename(dest)}")
                messagebox.showinfo("Export Successful", f"Saved Word document to:\n{dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export Word file:\n{e}")


def main():
    app = ImageSenseDesktopGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
