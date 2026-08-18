"""SEC EDGAR disclosure ingestion and deterministic text normalization."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

import requests

from core.schemas import DataSourceType, IngestionBatchReport


class FilingType(str, Enum):
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_13F = "13F-HR"
    FORM_4 = "4"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractedDisclosure:
    filing_id: str
    ticker: str
    cik: str
    filing_type: FilingType
    filing_date_utc: str
    accession_number: str
    primary_document_url: str
    extracted_text: str
    sections_map: Dict[str, str]
    raw_payload_hash: str
    ingested_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filing_id": self.filing_id,
            "ticker": self.ticker,
            "cik": self.cik,
            "filing_type": self.filing_type.value,
            "filing_date_utc": self.filing_date_utc,
            "accession_number": self.accession_number,
            "primary_document_url": self.primary_document_url,
            "extracted_text_preview": self.extracted_text[:300],
            "sections_extracted": list(self.sections_map),
            "raw_payload_hash": self.raw_payload_hash,
            "ingested_at_utc": self.ingested_at_utc,
        }


class DisclosureCrawler:
    """Fetches SEC submissions, strips markup, and persists hashed payloads."""

    SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
    SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary_doc}"

    def __init__(self, user_agent_header: str = "EDGE-TF-Agent Research@edge-tf.internal", raw_storage_dir: Optional[Path] = None, rate_limit_delay_seconds: float = 0.12):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent_header, "Accept-Encoding": "gzip, deflate"})
        self.raw_dir = raw_storage_dir or Path("data/raw/filings")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_delay = rate_limit_delay_seconds

    @staticmethod
    def _compute_sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _clean_html_xbrl(raw_html: str) -> str:
        text = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>", "", raw_html, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z0-9#]{1,8};", " ", text, flags=re.I)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_key_sections(clean_text: str, filing_type: FilingType) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        if filing_type in (FilingType.FORM_10K, FilingType.FORM_10Q):
            patterns = {
                "MDA": r"(Item\s+(?:7|2)\.?\s+Management['’]s Discussion and Analysis[\s\S]*?)(?=Item\s+(?:7A|3)\.|\Z)",
                "RISK_FACTORS": r"(Item\s+1A\.?\s+Risk Factors[\s\S]*?)(?=Item\s+(?:1B|2)\.|\Z)",
            }
            for name, pattern in patterns.items():
                match = re.search(pattern, clean_text, re.I)
                if match:
                    sections[name] = match.group(1)[:15000]
        elif filing_type == FilingType.FORM_8K:
            sections["CURRENT_REPORT_NARRATIVE"] = clean_text[:10000]
        return sections or {"FULL_BODY_EXCERPT": clean_text[:20000]}

    def fetch_company_submissions_metadata(self, cik: str) -> Dict[str, Any]:
        time.sleep(self.rate_limit_delay)
        response = self.session.get(self.SEC_SUBMISSIONS_URL.format(cik_padded=str(cik).zfill(10)), timeout=10)
        response.raise_for_status()
        return response.json()

    def download_filing(self, ticker: str, cik: str, accession_number: str, primary_document_name: str, filing_type: FilingType, filing_date_utc: str) -> Optional[ExtractedDisclosure]:
        url = self.SEC_ARCHIVES_URL.format(cik=str(int(cik)), accession_nodash=accession_number.replace("-", ""), primary_doc=primary_document_name)
        time.sleep(self.rate_limit_delay)
        response = self.session.get(url, timeout=15)
        if response.status_code != 200:
            return None
        clean_text = self._clean_html_xbrl(response.text)
        extracted = ExtractedDisclosure(
            filing_id=f"SEC-{ticker}-{accession_number}", ticker=ticker, cik=cik, filing_type=filing_type,
            filing_date_utc=filing_date_utc, accession_number=accession_number, primary_document_url=url,
            extracted_text=clean_text, sections_map=self._extract_key_sections(clean_text, filing_type),
            raw_payload_hash=self._compute_sha256(response.text),
        )
        with (self.raw_dir / f"{extracted.filing_id}.json").open("w", encoding="utf-8") as handle:
            json.dump(extracted.to_dict(), handle, indent=2)
        return extracted

    def crawl_recent_filings(self, ticker: str, cik: str, target_forms: Optional[List[FilingType]] = None, max_filings: int = 3) -> IngestionBatchReport:
        target_forms = target_forms or [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K]
        batch_id = f"BATCH-SEC-{ticker}-{int(time.time())}"
        recent = self.fetch_company_submissions_metadata(cik).get("filings", {}).get("recent", {})
        count = 0
        for form, accession, document, filing_date in zip(recent.get("form", []), recent.get("accessionNumber", []), recent.get("primaryDocument", []), recent.get("filingDate", [])):
            if count >= max_filings:
                break
            filing_type = next((item for item in target_forms if item.value == form), None)
            if filing_type and self.download_filing(ticker, cik, accession, document, filing_type, filing_date):
                count += 1
        return IngestionBatchReport(
            batch_id=batch_id, timestamp_utc=datetime.now(timezone.utc).isoformat(), source=DataSourceType.SEC_EDGAR,
            tickers_ingested=[ticker], records_count=count, validation_passed=count > 0, raw_storage_path=str(self.raw_dir),
        )


__all__ = ["FilingType", "ExtractedDisclosure", "DisclosureCrawler"]
