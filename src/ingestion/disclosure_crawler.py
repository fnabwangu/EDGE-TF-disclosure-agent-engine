"""
disclosure_crawler.py
Minimal crawler stub that demonstrates fetching disclosures.
"""
import json
import requests

def fetch_daily_disclosures(url: str):
    """Fetch disclosure JSON from a URL. Returns parsed JSON or raises on HTTP error."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    print("Run fetch_daily_disclosures(url) to fetch disclosures")
## SEC EDGAR & Regulatory Disclosure Crawler (`src/ingestion/disclosure_crawler.py`)

The `disclosure_crawler.py` module extracts regulatory filings (10-K, 10-Q, 8-K, Form 4) and competitor ETF Portfolio Composition Files (PCFs) from SEC EDGAR and market data endpoints. It parses unstructured filing narratives, structures corporate disclosures, computes payload hashes, and routes sanitized data to the `raw` data tier for qualitative hypothesis extraction and compliance auditing.

---

### Key Capabilities

* **`SEC EDGAR API Ingestion`**: Fetches company submissions via official SEC REST endpoints using compliant `User-Agent` declarations and rate-limiting protocols.
* **`Structured Filing Categorization`**: Classifies documents across statutory forms (10-K, 10-Q, 8-K, 13F, Form 4 insider transactions).
* **`MD&A & Risk Factor Extraction`**: Strips raw HTML/XBRL tags and isolates Item 7 (MD&A), Item 1A (Risk Factors), and Item 8.01 (Other Events) for hypothesis generation.
* **`Bi-Temporal Data Storage`**: Persists raw immutable filing payloads under `data/raw/filings/` alongside SHA-256 integrity fingerprints.
Python
# src/ingestion/disclosure_crawler.py
"""
EDGE-TF Disclosure Agent Engine - Regulatory Disclosure & SEC EDGAR Crawler.

Automates compliant ingestion of SEC EDGAR corporate filings, competitor ETF PCFs,
and unstructured narrative sections for qualitative hypothesis testing and compliance audits.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional
import requests

from src.ingestion import DataSourceType, IngestionBatchReport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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
    ingested_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filing_id": self.filing_id,
            "ticker": self.ticker,
            "cik": self.cik,
            "filing_type": self.filing_type.value,
            "filing_date_utc": self.filing_date_utc,
            "accession_number": self.accession_number,
            "primary_document_url": self.primary_document_url,
            "extracted_text_preview": self.extracted_text[:300] + "..." if self.extracted_text else "",
            "sections_extracted": list(self.sections_map.keys()),
            "raw_payload_hash": self.raw_payload_hash,
            "ingested_at_utc": self.ingested_at_utc,
        }


class DisclosureCrawler:
    """
    Crawls SEC EDGAR submissions and normalizes regulatory filings into
    structured document objects for downstream hypothesis scoring.
    """

    SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
    SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary_doc}"

    def __init__(
        self,
        user_agent_header: str = "EDGE-TF-Agent Research@edge-tf.internal",
        raw_storage_dir: Optional[Path] = None,
        rate_limit_delay_seconds: float = 0.12,  # Respects SEC 10 requests/sec limit
    ):
        self.headers = {
            "User-Agent": user_agent_header,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"
        }
        self.raw_dir = raw_storage_dir or Path("data/raw/filings")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_delay = rate_limit_delay_seconds
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    @staticmethod
    def _compute_sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _clean_html_xbrl(raw_html: str) -> str:
        """Strips HTML tags, XML wrappers, and inline styles from raw SEC filings."""
        text = re.sub(r"<style[\s\S]*?</style>", "", raw_html, flags=re.IGNORECASE)
        text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-z]{1,8};", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_key_sections(self, clean_text: str, filing_type: FilingType) -> Dict[str, str]:
        """Isolates specific Item blocks like MD&A or Risk Factors."""
        sections = {}
        if filing_type in (FilingType.FORM_10K, FilingType.FORM_10Q):
            # Attempt basic regex partitioning for Item 7 / Item 2 (MD&A)
            mda_match = re.search(
                r"(Item\s+(?:7|2)\.?\s+Management['’]s Discussion and Analysis[\s\S]*?)(?=Item\s+(?:7A|3)\.|\Z)",
                clean_text,
                re.IGNORECASE
            )
            if mda_match:
                sections["MDA"] = mda_match.group(1)[:15000]

            # Attempt partition for Item 1A (Risk Factors)
            risk_match = re.search(
                r"(Item\s+1A\.?\s+Risk Factors[\s\S]*?)(?=Item\s+(?:1B|2)\.|\Z)",
                clean_text,
                re.IGNORECASE
            )
            if risk_match:
                sections["RISK_FACTORS"] = risk_match.group(1)[:15000]

        elif filing_type == FilingType.FORM_8K:
            sections["CURRENT_REPORT_NARRATIVE"] = clean_text[:10000]

        if not sections:
            sections["FULL_BODY_EXCERPT"] = clean_text[:20000]

        return sections

    def fetch_company_submissions_metadata(self, cik: str) -> Dict[str, Any]:
        """Fetches the master JSON submission manifest for a given CIK."""
        cik_padded = str(cik).zfill(10)
        url = self.SEC_SUBMISSIONS_URL.format(cik_padded=cik_padded)
        time.sleep(self.rate_limit_delay)

        response = self.session.get(url, timeout=10)
        if response.status_code != 200:
            logging.error(f"Failed to fetch metadata for CIK {cik}: {response.status_code}")
            return {}
        return response.json()

    def download_filing(
        self,
        ticker: str,
        cik: str,
        accession_number: str,
        primary_document_name: str,
        filing_type: FilingType,
        filing_date_utc: str
    ) -> Optional[ExtractedDisclosure]:
        """Downloads, cleans, and stores a specific SEC filing document."""
        cik_clean = str(int(cik))  # Strips leading zeros for archive URL
        accession_nodash = accession_number.replace("-", "")
        url = self.SEC_ARCHIVES_URL.format(
            cik=cik_clean,
            accession_nodash=accession_nodash,
            primary_doc=primary_document_name
        )

        headers = {**self.headers, "Host": "www.sec.gov"}
        time.sleep(self.rate_limit_delay)

        try:
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logging.error(f"Failed to download doc {url}: {response.status_code}")
                return None

            raw_content = response.text
            payload_hash = self._compute_sha256(raw_content)
            clean_text = self._clean_html_xbrl(raw_content)
            sections = self._extract_key_sections(clean_text, filing_type)

            filing_id = f"SEC-{ticker}-{accession_number}"
            extracted = ExtractedDisclosure(
                filing_id=filing_id,
                ticker=ticker,
                cik=cik,
                filing_type=filing_type,
                filing_date_utc=filing_date_utc,
                accession_number=accession_number,
                primary_document_url=url,
                extracted_text=clean_text,
                sections_map=sections,
                raw_payload_hash=payload_hash
            )

            # Persist raw extracted JSON payload to disk
            out_file = self.raw_dir / f"{filing_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(extracted.to_dict(), f, indent=2)

            logging.info(f"Successfully ingested {filing_type.value} for {ticker} ({accession_number}).")
            return extracted

        except Exception as exc:
            logging.error(f"Exception downloading filing {accession_number} for {ticker}: {exc}")
            return None

    def crawl_recent_filings(
        self,
        ticker: str,
        cik: str,
        target_forms: Optional[List[FilingType]] = None,
        max_filings: int = 3
    ) -> IngestionBatchReport:
        """Crawls the most recent filings for a specific target company."""
        target_forms = target_forms or [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K]
        now_ts = datetime.now(timezone.utc).isoformat()
        batch_id = f"BATCH-SEC-{ticker}-{int(time.time())}"

        metadata = self.fetch_company_submissions_metadata(cik)
        if not metadata or "filings" not in metadata:
            return IngestionBatchReport(
                batch_id=batch_id,
                timestamp_utc=now_ts,
                source=DataSourceType.SEC_EDGAR,
                tickers_ingested=[ticker],
                records_count=0,
                validation_passed=False,
                quarantined_records_count=0
            )

        recent = metadata["filings"]["recent"]
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        doc_names = recent.get("primaryDocument", [])
        filing_dates = recent.get("filingDate", [])

        ingested_count = 0
        for form_str, acc, doc, fdate in zip(forms, accessions, doc_names, filing_dates):
            if ingested_count >= max_filings:
                break

            matched_type = next((t for t in target_forms if t.value == form_str), None)
            if matched_type:
                res = self.download_filing(
                    ticker=ticker,
                    cik=cik,
                    accession_number=acc,
                    primary_document_name=doc,
                    filing_type=matched_type,
                    filing_date_utc=fdate
                )
                if res:
                    ingested_count += 1

        return IngestionBatchReport(
            batch_id=batch_id,
            timestamp_utc=now_ts,
            source=DataSourceType.SEC_EDGAR,
            tickers_ingested=[ticker],
            records_count=ingested_count,
            validation_passed=ingested_count > 0,
            raw_storage_path=str(self.raw_dir)
        )


__all__ = [
    "FilingType",
    "ExtractedDisclosure",
    "DisclosureCrawler",
]
