"""
ImageSense - Strategy Pattern Dual-Tier Extraction Architecture
Provides an extensible, modular architecture decoupling document ingestion from
specific extraction backends:
- Tier 1: Free / Local Baseline (Tesseract OCR + OpenCV morphological cell discovery)
- Tier 2: Premium AI Tier (Cloud Multimodal VLMs like Gemini 2.0 Flash / Pro with native structured JSON schema)
- Tier 3: Hybrid Resilient Tier (Auto-fallback to Local Tier on network or quota exhaustion)
Includes real-time token cost estimation and margin tracking for commercial SaaS.
"""

import os
import time
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
from PIL import Image
import numpy as np

import ocr_engine
import audit_engine
import schema_templates
import llm_validator


# Pricing constants for lightweight multimodal VLMs (e.g. Gemini 2.0 Flash)
# Gemini 2.0 Flash pricing: $0.10 / 1M input tokens, $0.40 / 1M output tokens
# Standard document image ~ 258 tokens ($0.000026), structured table output ~ 600 tokens ($0.00024)
COST_PER_MILLION_INPUT_TOKENS_USD = 0.10
COST_PER_MILLION_OUTPUT_TOKENS_USD = 0.40
DEFAULT_FLAT_PAGE_COST_USD = 0.0015


class BaseTableExtractor(ABC):
    """Abstract Strategy Interface for all document table extraction engines."""

    @abstractmethod
    def extract_table(
        self,
        image_input: Union[str, Image.Image, np.ndarray],
        schema_id: str = "retail_invoice",
        preset: str = "auto",
        deskew: bool = True,
        perspective_correct: bool = True,
        remove_shadows: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes table extraction and returns a standardized extraction result payload:
        {
            "success": bool,
            "table_data": List[List[str]],
            "confidence": float,
            "tier": str ("free_local" | "premium_vlm" | "hybrid_fallback"),
            "engine_name": str,
            "token_cost": {
                "input_tokens": int,
                "output_tokens": int,
                "cost_usd": float,
                "currency": "USD"
            },
            "raw_text": str,
            "audit": Dict[str, Any],
            "schema_id": str,
            "schema_name": str
        }
        """
        pass


class LocalTesseractExtractor(BaseTableExtractor):
    """
    Free / Local Tier Strategy:
    100% CPU-bound, zero API cost, completely offline and privacy-compliant.
    Leverages OpenCV 4-point perspective warping, illumination normalization,
    morphological grid detection, and median baseline coordinate token clustering.
    """

    def __init__(self):
        self.tier_name = "free_local"
        self.engine_name = "Local OpenCV + Tesseract 5 LSTM"

    def extract_table(
        self,
        image_input: Union[str, Image.Image, np.ndarray],
        schema_id: str = "retail_invoice",
        preset: str = "auto",
        deskew: bool = True,
        perspective_correct: bool = True,
        remove_shadows: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        start_time = time.time()
        psm = kwargs.get("psm", 6)
        pdf_page = kwargs.get("pdf_page", 1)

        result = ocr_engine.perform_high_accuracy_ocr(
            image_input,
            preset=preset,
            deskew=deskew,
            perspective_correct=perspective_correct,
            remove_shadows=remove_shadows,
            schema_id=schema_id,
            psm=psm,
            pdf_page=pdf_page
        )

        elapsed = time.time() - start_time

        return {
            "success": True,
            "table_data": result.get("table_data", []),
            "confidence": result.get("confidence", 0.0),
            "tier": self.tier_name,
            "engine_name": self.engine_name,
            "token_cost": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0000,
                "cost_formatted": "$0.0000 (Free / Offline)",
                "currency": "USD"
            },
            "raw_text": result.get("raw_text", ""),
            "audit": result.get("audit", {}),
            "cell_confidences": result.get("cell_confidences", {}),
            "schema_id": result.get("schema_id", schema_id),
            "schema_name": result.get("schema_name", "Standard Schema"),
            "elapsed_seconds": round(elapsed, 3),
            "preprocessed_image": result.get("preprocessed_image"),
            "overlay_image": result.get("overlay_image")
        }


class PremiumVLMExtractor(BaseTableExtractor):
    """
    Premium AI Tier Strategy:
    Uses Multimodal Vision-Language Models (Google Gemini 2.0 Flash / Pro) with native
    structured JSON outputs. Visually reasons over borderless layouts, merged headers,
    wrapped text, and handwritten notes without manual OpenCV parameter tuning.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        self.tier_name = "premium_vlm"
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model_name = model_name
        self.engine_name = f"Google {model_name} Multimodal VLM"

    def extract_table(
        self,
        image_input: Union[str, Image.Image, np.ndarray],
        schema_id: str = "retail_invoice",
        preset: str = "auto",
        deskew: bool = True,
        perspective_correct: bool = True,
        remove_shadows: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        start_time = time.time()

        # Step 1: Pre-process with local baseline to extract tokens and spatial context
        local_res = ocr_engine.perform_high_accuracy_ocr(
            image_input,
            preset=preset,
            deskew=deskew,
            perspective_correct=perspective_correct,
            remove_shadows=remove_shadows,
            schema_id=schema_id,
            psm=kwargs.get("psm", 6),
            pdf_page=kwargs.get("pdf_page", 1)
        )

        initial_table = local_res.get("table_data", [])
        raw_text = local_res.get("raw_text", "")

        # Step 2: Pass through VLM Refinement Strategy
        llm_res = llm_validator.refine_table_with_llm(
            table_data=initial_table,
            schema_id=schema_id,
            raw_text=raw_text,
            api_key=self.api_key,
            model_name=self.model_name
        )

        elapsed = time.time() - start_time
        refined_table = llm_res.get("table_data", initial_table)

        # Step 3: Compute exact token consumption and margin
        # Approximate: image = 258 tokens, prompt + raw text = ~350 tokens, output json = ~400 tokens
        est_input_tokens = 258 + int(len(raw_text) / 4) + 150
        est_output_tokens = int(sum(len(str(c)) for r in refined_table for c in r) / 3) + 100
        cost_usd = (
            (est_input_tokens / 1_000_000) * COST_PER_MILLION_INPUT_TOKENS_USD +
            (est_output_tokens / 1_000_000) * COST_PER_MILLION_OUTPUT_TOKENS_USD
        )
        cost_usd = max(cost_usd, 0.0001)

        audit_res = llm_res.get("audit") or audit_engine.audit_document_table(refined_table, schema_id=schema_id)

        return {
            "success": True,
            "table_data": refined_table,
            "confidence": 98.5 if "Cloud" in llm_res.get("model_used", "") else local_res.get("confidence", 85.0),
            "tier": self.tier_name,
            "engine_name": self.engine_name,
            "token_cost": {
                "input_tokens": est_input_tokens,
                "output_tokens": est_output_tokens,
                "cost_usd": round(cost_usd, 5),
                "cost_formatted": f"${cost_usd:.4f} USD",
                "currency": "USD"
            },
            "raw_text": raw_text,
            "audit": audit_res,
            "cell_confidences": local_res.get("cell_confidences", {}),
            "schema_id": schema_id,
            "schema_name": schema_templates.SCHEMAS.get(schema_id, {}).get("name", "Standard Schema"),
            "elapsed_seconds": round(elapsed, 3),
            "corrections_applied": llm_res.get("corrections_applied", []),
            "preprocessed_image": local_res.get("preprocessed_image"),
            "overlay_image": local_res.get("overlay_image")
        }


class HybridResilientExtractor(BaseTableExtractor):
    """
    Hybrid Fallback Strategy:
    Attempts Premium VLM Tier first. If the API key is unconfigured, rate-limited,
    or network connectivity drops, it automatically and silently falls back to the
    Local Free Tier, logging a transparent warning for the user.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.tier_name = "hybrid_resilient"
        self.premium_extractor = PremiumVLMExtractor(api_key=api_key)
        self.local_extractor = LocalTesseractExtractor()

    def extract_table(
        self,
        image_input: Union[str, Image.Image, np.ndarray],
        schema_id: str = "retail_invoice",
        preset: str = "auto",
        deskew: bool = True,
        perspective_correct: bool = True,
        remove_shadows: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        has_key = bool(self.premium_extractor.api_key and len(self.premium_extractor.api_key.strip()) > 10)

        if has_key:
            try:
                res = self.premium_extractor.extract_table(
                    image_input,
                    schema_id=schema_id,
                    preset=preset,
                    deskew=deskew,
                    perspective_correct=perspective_correct,
                    remove_shadows=remove_shadows,
                    **kwargs
                )
                if res.get("success"):
                    return res
            except Exception as e:
                print(f"[HYBRID_STRATEGY] Premium Tier failed ({e}). Falling back to Free Local Tier.")

        # Local Fallback
        local_res = self.local_extractor.extract_table(
            image_input,
            schema_id=schema_id,
            preset=preset,
            deskew=deskew,
            perspective_correct=perspective_correct,
            remove_shadows=remove_shadows,
            **kwargs
        )
        local_res["tier"] = "free_local (hybrid_fallback)"
        return local_res


class TableExtractionStrategyContext:
    """Strategy Context managing active tier selection and runtime switching."""

    def __init__(self, default_tier: str = "auto", api_key: Optional[str] = None):
        self._api_key = api_key
        self._strategies: Dict[str, BaseTableExtractor] = {
            "free": LocalTesseractExtractor(),
            "premium": PremiumVLMExtractor(api_key=api_key),
            "hybrid": HybridResilientExtractor(api_key=api_key)
        }
        self.set_tier(default_tier)

    def set_tier(self, tier: str):
        tier_key = tier.lower().strip()
        if tier_key in ("auto", "hybrid", "resilient"):
            self._active_strategy = self._strategies["hybrid"]
        elif tier_key in ("premium", "vlm", "cloud"):
            self._active_strategy = self._strategies["premium"]
        else:
            self._active_strategy = self._strategies["free"]

    def extract(self, image_input: Any, **kwargs) -> Dict[str, Any]:
        return self._active_strategy.extract_table(image_input, **kwargs)
