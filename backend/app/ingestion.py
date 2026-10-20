import csv
import hashlib
import io
import math
import re
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath

from defusedxml import ElementTree
from pypdf import PdfReader
from sqlalchemy import select

from .config import settings
from .db import Source

CONTRACTS = {
    "orders": {
        "id": "id",
        "date": "date",
        "customer_id": "id",
        "product_id": "id",
        "quantity": "positive_integer",
        "revenue": "money",
        "status": "status",
    },
    "products": {"id": "id", "name": "text", "category": "text", "price": "money", "cost": "money"},
    "inventory": {"date": "date", "product_id": "id", "supplier_id": "id", "stock": "integer"},
    "suppliers": {
        "id": "id",
        "name": "text",
        "product_id": "id",
        "promised_date": "date",
        "received_date": "optional_date",
    },
    "deliveries": {"order_id": "id", "promised_date": "date", "delivered_date": "optional_date", "route": "text"},
    "marketing": {"date": "date", "channel": "text", "spend": "money", "impressions": "integer", "clicks": "integer"},
    "customers": {"id": "id", "segment": "text", "location": "text", "signup_date": "date"},
    "expenses": {"date": "date", "category": "text", "amount": "money"},
    "purchases": {
        "date": "date",
        "supplier_id": "id",
        "product_id": "id",
        "quantity": "positive_integer",
        "unit_cost": "money",
    },
}
# Columns that may be left out of the header entirely; blank values are stored as null.
OPTIONAL_COLUMNS = {"deliveries": {"courier": "optional_text", "fee": "optional_money"}}
STATUSES = {"delivered", "completed", "cancelled", "returned", "pending", "shipped"}


def parse_date(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()


def xlsx_rows(data):
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 32 * 1024 * 1024:
            raise ValueError("Spreadsheet expands beyond the 32 MB limit")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(item.itertext()) for item in root.findall("s:si", ns)]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find("s:sheets/s:sheet", ns)
        if sheet is None:
            raise ValueError("Spreadsheet has no worksheets")
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next((r.attrib["Target"] for r in relations if r.attrib["Id"] == rel_id), "")
        target = target.lstrip("/") if target.startswith("/") else "xl/" + target
        if ".." in target or target not in archive.namelist():
            raise ValueError("Invalid worksheet reference")
        root = ElementTree.fromstring(archive.read(target))
        result = []
        for row in root.findall("s:sheetData/s:row", ns):
            cells = {}
            for cell in row.findall("s:c", ns):
                if cell.find("s:f", ns) is not None:
                    raise ValueError("Export formulas as values before uploading")
                letters = re.match(r"[A-Z]+", cell.attrib.get("r", "A1")).group()
                col = 0
                for letter in letters:
                    col = col * 26 + ord(letter) - 64
                if col > 100:
                    raise ValueError("Maximum 100 spreadsheet columns")
                value = cell.findtext("s:v", default="", namespaces=ns)
                if cell.attrib.get("t") == "s":
                    value = strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", ns).itertext())
                cells[col - 1] = value
            if cells:
                result.append([cells.get(i, "") for i in range(max(cells) + 1)])
            if len(result) > settings().max_rows + 1:
                raise ValueError("Too many spreadsheet rows")
        if len(result) < 2:
            raise ValueError("Spreadsheet needs a header and at least one data row")
        headers = result[0]
        if len(set(headers)) != len(headers):
            raise ValueError("Column names must be unique")
        return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in result[1:]]


def validate_rows(rows, kind):
    if not rows:
        raise ValueError("Dataset is empty")
    if len(rows) > settings().max_rows:
        raise ValueError(f"Maximum {settings().max_rows:,} rows per file")
    optional = {column: field for column, field in OPTIONAL_COLUMNS.get(kind, {}).items() if column in rows[0]}
    contract = {**CONTRACTS[kind], **optional}
    missing = set(CONTRACTS[kind]) - set(rows[0])
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    normalized = []
    unique = set()
    for number, row in enumerate(rows, 2):
        result = {}
        for column, field_type in contract.items():
            value = str(row.get(column, "") or "").strip()
            try:
                if field_type.startswith("optional_") and not value:
                    result[column] = None
                    continue
                if not value:
                    raise ValueError("value is required")
                if "date" in field_type:
                    value = parse_date(value)
                elif field_type in {"money", "optional_money", "integer", "positive_integer"}:
                    numeric = Decimal(value)
                    if (
                        not numeric.is_finite()
                        or not math.isfinite(float(numeric))
                        or numeric < 0
                        or numeric > Decimal("1e12")
                    ):
                        raise ValueError("must be a finite number between 0 and 1 trillion")
                    if "integer" in field_type and (
                        numeric != int(numeric) or (field_type == "positive_integer" and numeric < 1)
                    ):
                        raise ValueError("must be a valid whole number")
                    value = str(numeric)
                elif field_type == "status" and value not in STATUSES:
                    raise ValueError("status must be one of: " + ", ".join(sorted(STATUSES)))
                elif len(value) > 500:
                    raise ValueError("text is too long (500 characters maximum)")
            except (ValueError, InvalidOperation, OverflowError) as error:
                raise ValueError(f"Row {number}, {column}: {error}") from error
            result[column] = value
        key_fields = {
            "orders": ["id"],
            "products": ["id"],
            "customers": ["id"],
            "deliveries": ["order_id"],
            "inventory": ["date", "product_id"],
            "marketing": ["date", "channel"],
        }.get(kind)
        if key_fields:
            key = tuple(result[field] for field in key_fields)
            if key in unique:
                raise ValueError(f"Row {number}: duplicate key ({', '.join(key_fields)})")
            unique.add(key)
        if kind in {"suppliers", "deliveries"}:
            actual = result.get("received_date") or result.get("delivered_date")
            if actual and actual < "1900-01-01":
                raise ValueError(f"Row {number}: date is outside the supported range")
        normalized.append(result)
    return normalized


def parse_upload(data, filename, kind):
    if not data:
        raise ValueError("File is empty")
    suffix = PurePath(filename).suffix.lower()
    if kind == "document":
        pages = []
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ValueError("PDF must be unencrypted and no longer than 100 pages")
            pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        elif suffix in {".txt", ".md"}:
            pages = [(1, data.decode("utf-8-sig"))]
        else:
            raise ValueError("Documents must be PDF, TXT or Markdown")
        chunks = []
        for page, text in pages:
            text = text.replace("\x00", "").strip()
            for start in range(0, len(text), 1000):
                chunks.append({"page": page, "chunk": len(chunks) + 1, "text": text[start : start + 1200]})
        if not chunks:
            raise ValueError("No readable text found. Scanned PDFs require OCR first.")
        if len(chunks) > 500:
            raise ValueError("Document exceeds 500 text chunks")
        return {"chunks": chunks}, len(chunks)
    if kind not in CONTRACTS:
        raise ValueError("Unknown dataset type")
    if suffix == ".csv":
        csv.field_size_limit(100000)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        if reader.fieldnames and len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Column names must be unique")
        rows = []
        for row in reader:
            if None in row:
                raise ValueError("A row has more values than the header")
            rows.append(row)
            if len(rows) > settings().max_rows:
                raise ValueError("Dataset exceeds the row limit")
    elif suffix == ".xlsx":
        rows = xlsx_rows(data)
    else:
        raise ValueError("Datasets must be CSV or XLSX. Use ISO dates (YYYY-MM-DD).")
    rows = validate_rows(rows, kind)
    return {"rows": rows}, len(rows)


def store_source(db, data, filename, kind):
    checksum = hashlib.sha256(kind.encode() + b"\0" + data).hexdigest()
    existing = db.scalar(select(Source).where(Source.checksum == checksum))
    if existing:
        return existing, False
    content, count = parse_upload(data, filename, kind)
    name = filename.replace("\\", "/").split("/")[-1][:200]
    source = Source(name=name, kind=kind, checksum=checksum, content=content, row_count=count)
    db.add(source)
    db.flush()
    return source, True


def active_sources(db):
    sources = list(db.scalars(select(Source).order_by(Source.created_at.desc(), Source.id.desc())))
    selected = []
    seen = set()
    for source in sources:
        if source.kind == "document" or source.kind not in seen:
            selected.append(source)
            seen.add(source.kind)
    return selected
