"""CSV import/export helpers (UI-facing).

Legacy Stocky used CSV uploads across many master-data screens. This module
provides:
  - tolerant decoding (UTF-8/Excel BOM + common Windows encodings),
  - header normalization compatible with legacy exports,
  - small parsing helpers for numbers/bools,
  - an import result structure suitable for web messaging.

Domain-specific upsert logic lives in each app's application layer.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


_HEADER_RE = re.compile(r"[^a-z0-9_]+")
_UNDERSCORES_RE = re.compile(r"_+")


def normalize_header(value: str) -> str:
    """Normalize a CSV header to a predictable snake-ish key.

    Examples:
      "Company Name" -> "company_name"
      "VAT Number"   -> "vat_number"
      "PhoneNumber"  -> "phonenumber" (legacy-compatible)

    Notes:
      - We keep digits and underscores.
      - We strip BOM characters that appear in some Excel-generated CSVs.
    """
    v = (value or "").strip().lower().replace("\ufeff", "")
    v = re.sub(r"\s+", "_", v)
    v = _HEADER_RE.sub("", v)
    v = _UNDERSCORES_RE.sub("_", v).strip("_")
    return v


def decode_csv_bytes(data: bytes) -> str:
    """Decode CSV bytes with a small set of practical encodings."""
    for enc in ("utf-8-sig", "utf-8", "cp1256", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: replace undecodable bytes.
    return data.decode("utf-8", errors="replace")


def sniff_dialect(sample: str) -> csv.Dialect:
    """Sniff delimiter/quoting from a text sample."""
    sniffer = csv.Sniffer()
    try:
        return sniffer.sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.get_dialect("excel")


@dataclass(frozen=True)
class CSVRowError:
    row_number: int
    message: str


@dataclass
class CSVImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[CSVRowError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_decimal(value: Any, *, default: Decimal | None = None) -> Decimal | None:
    if value is None:
        return default
    s = str(value).strip()
    if not s:
        return default
    s = s.replace(",", "")  # allow 1,234.56
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def parse_int(value: Any, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if not s:
        return default
    if s in {"1", "true", "t", "yes", "y", "active", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "inactive", "off"}:
        return False
    return default


def read_csv_rows(data: bytes) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Read CSV bytes into (normalized_headers, rows).

    Returns:
      headers: list[str] normalized header keys
      rows: list[(row_number, dict[header -> cell])]
    """
    text = decode_csv_bytes(data)
    dialect = sniff_dialect(text[:4096])
    buf = io.StringIO(text)
    reader = csv.reader(buf, dialect)

    raw_header = next(reader, [])
    headers = [normalize_header(h) for h in raw_header]

    rows: list[tuple[int, dict[str, str]]] = []
    for row_number, row in enumerate(reader, start=2):
        if not row or not any(str(c).strip() for c in row):
            continue
        if len(row) < len(headers):
            row = [*row, *[""] * (len(headers) - len(row))]
        data_row = {headers[i]: (str(row[i]).strip() if i < len(row) else "") for i in range(len(headers))}
        rows.append((row_number, data_row))
    return headers, rows


def csv_bytes(
    *,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any] | Mapping[str, Any]],
    include_bom: bool = True,
) -> bytes:
    """Serialize rows to CSV bytes (UTF-8, with optional BOM for Excel)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(list(headers))
    for row in rows:
        if isinstance(row, Mapping):
            writer.writerow([row.get(h, "") for h in headers])
        else:
            writer.writerow(list(row))
    text = out.getvalue()
    return text.encode("utf-8-sig" if include_bom else "utf-8")

