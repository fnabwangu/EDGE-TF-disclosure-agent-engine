"""
EDGE-TF Agents Module

Layer 2: LLM Extraction & Semantic Validation
Contains hypothesis generation agents, falsification passes, and meta-prompts
for structured extraction from unstructured disclosures.
"""

from .hypothesis_agent import HypothesisAgent, HypothesisScoreOutput
from .falsification_pass import FalsificationEngine, FalsificationReport, FalsificationVerdict
from .meta_prompts import DISCLOSURE_EXTRACTION_SYSTEM_PROMPT

__all__ = [
    "HypothesisAgent",
    "HypothesisScoreOutput",
    "FalsificationEngine",
    "FalsificationReport",
    "FalsificationVerdict",
    "DISCLOSURE_EXTRACTION_SYSTEM_PROMPT",
]
