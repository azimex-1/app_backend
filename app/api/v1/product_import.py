import csv
import io
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.products import _build_name, _slug
from app.api.deps import DbSession
from app.models.product import Product
from app.models.reference import Brand, Category, Unit

router = APIRouter()

TEMPLATE_HEADERS = [
    "manufacturer_code", "brand", "category", "unit", "barcode",
    "selling_price", "selling_currency", "cost_price", "cost_currency",
    "reorder_level", "track_stock", "description",
]
REQUIRED_HEADERS = {"manufacturer_code", "brand", "category", "unit"}
KNOWN_HEADERS = set(TEMPLATE_HEADERS)
SUPPORTED_CURRENCIES = {"GMD", "EUR", "USD", "GBP", "CNY", "AED"}
TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}

# Fields an existing item may be UPDATED on (key fields + name/sku/quantity excluded).
UPDATE_FIELDS = [
    "category", "unit", "barcode", "price_minor", "selling_currency",
    "cost_price_minor", "cost_currency", "reorder_level", "track_stock", "description",
]
FIELD_LABELS = {
    "category": "category", "unit": "unit", "barcode": "barcode",
    "price_minor": "selling price", "selling_currency": "selling currency",
    "cost_price_minor": "cost price", "cost_currency": "cost currency",
    "reorder_level": "reorder level", "track_stock": "track stock", "description": "description",
}

WARN_BARCODE_EXISTS = "Barcode already exists in the system"
WARN_DUP_ITEM_DB = "Possible duplicate of an existing item (same barcode & code)"
WARN_DUP_ITEM_FILE = "Possible duplicate item in file (same barcode & code)"
WARN_DUP_BARCODE_FILE = "Duplicate barcode within the file"


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _parse_bool(v: str, default: bool = True) -> bool:
    t = v.strip().lower()
    if t == "":
        return default
    return t in TRUE_VALUES


# ── Schemas ──
class ImportRowResult(BaseModel):
    row: int
    manufacturer_code: str | None
    brand: str | None
    status: Literal["ready", "warning", "error"]
    errors: list[str]
    warnings: list[str]
    is_update: bool = False
    changed_fields: list[str] = []


class ImportIssue(BaseModel):
    kind: str                    # unknown_brand | unknown_category | unknown_unit | other
    label: str                   # human text
    value: str | None = None     # the thing to add, for fixable kinds
    action: str | None = None    # add_brand | add_category | add_unit | None
    severity: Literal["error", "warning"]
    count: int
    rows: list[int]


class ImportPreview(BaseModel):
    filename: str
    total: int
    ready: int
    warnings: int
    errors: int
    header_errors: list[str]
    issues: list[ImportIssue]
    rows: list[ImportRowResult]


class ImportResult(BaseModel):
    success: bool
    imported: int
    updated: int = 0
    total: int
    errors: int
    message: str
    header_errors: list[str]


# ── Export template ──
@router.get("/template")
async def download_template() -> Response:
    example = [
        "OX123", "MANN", "Oil Filter", "piece", "4009026501234",
        "250", "GMD", "", "", "5", "TRUE", "Spin-on oil filter",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow(example)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=azimex_items_template.csv"},
    )


async def _load_reference(db: DbSession):
    brands = {b.lower(): b for b in (await db.scalars(select(Brand.name))).all()}
    categories = {c.lower(): c for c in (await db.scalars(select(Category.name))).all()}
    units = {u.lower(): u for u in (await db.scalars(select(Unit.name))).all()}
    existing_by_key: dict[tuple[str, str], Product] = {}
    existing_barcodes: set[str] = set()
    existing_barcode_slugs: set[tuple[str, str]] = set()
    for prod in (await db.scalars(select(Product))).all():
        if prod.brand and prod.manufacturer_code:
            existing_by_key[(prod.brand.lower(), prod.manufacturer_code.upper())] = prod
        if prod.barcode:
            existing_barcodes.add(prod.barcode)
            if prod.manufacturer_code:
                existing_barcode_slugs.add((prod.barcode, _slug(prod.manufacturer_code)))
    return brands, categories, units, existing_by_key, existing_barcodes, existing_barcode_slugs


def _read_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid text (expected UTF-8 CSV)")


def _validate(text: str, refs):
    (brands, categories, units, existing_by_key,
     existing_barcodes, existing_barcode_slugs) = refs

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    normalized = [_norm(h).lower() for h in fieldnames]

    header_errors: list[str] = []
    if any(h == "" for h in normalized):
        header_errors.append("There is a blank column header.")
    dups = sorted({h for h in normalized if h != "" and normalized.count(h) > 1})
    if dups:
        header_errors.append(f"Duplicate column headers: {', '.join(dups)}")
    missing = REQUIRED_HEADERS - set(normalized)
    if missing:
        header_errors.append(f"Missing required columns: {', '.join(sorted(missing))}")
    unknown = sorted(set(normalized) - KNOWN_HEADERS - {""})
    if unknown:
        header_errors.append(f"Unknown columns (ignored): {', '.join(unknown)}")

    if bool(missing or dups) or any(h == "" for h in normalized):
        return header_errors, True, [], []

    header_map: dict[str, str] = {}
    for original, norm in zip(fieldnames, normalized):
        header_map.setdefault(norm, original)

    def cell(rowdict: dict, key: str) -> str:
        return _norm(rowdict.get(header_map.get(key, "")))

    rows: list[tuple[ImportRowResult, dict | None]] = []
    seen_pairs: set[tuple[str, str]] = set()
    barcode_slugs_seen: dict[str, set[str]] = {}

    # structured issue collection
    unknown_brands: dict[str, list[int]] = {}
    unknown_categories: dict[str, list[int]] = {}
    unknown_units: dict[str, list[int]] = {}
    other_errors: dict[str, list[int]] = {}
    warn_groups: dict[str, list[int]] = {}
    update_rows: list[int] = []

    def err(bucket: dict, key: str, i: int):
        bucket.setdefault(key, []).append(i)

    for i, rowdict in enumerate(reader, start=1):
        errors: list[str] = []
        warnings: list[str] = []

        code = cell(rowdict, "manufacturer_code").upper()  # normalize to CAPS
        brand = cell(rowdict, "brand")
        category = cell(rowdict, "category")
        unit = cell(rowdict, "unit")
        barcode = cell(rowdict, "barcode")
        selling_price = cell(rowdict, "selling_price")
        selling_currency = cell(rowdict, "selling_currency")
        cost_price = cell(rowdict, "cost_price")
        cost_currency = cell(rowdict, "cost_currency")
        reorder_level = cell(rowdict, "reorder_level")
        track_stock = cell(rowdict, "track_stock")
        description = cell(rowdict, "description")

        if not code:
            errors.append("manufacturer_code is required")
            err(other_errors, "manufacturer_code is required", i)
        if not brand:
            errors.append("brand is required")
            err(other_errors, "brand is required", i)
        elif brand.lower() not in brands:
            errors.append(f"Unknown brand: {brand}")
            err(unknown_brands, brand.upper(), i)
        if not category:
            errors.append("category is required")
            err(other_errors, "category is required", i)
        elif category.lower() not in categories:
            errors.append(f"Unknown category: {category}")
            err(unknown_categories, category, i)
        if not unit:
            errors.append("unit is required")
            err(other_errors, "unit is required", i)
        elif unit.lower() not in units:
            errors.append(f"Unknown unit: {unit}")
            err(unknown_units, unit, i)

        if code and brand:
            pair = (brand.lower(), code)
            if pair in seen_pairs:
                errors.append("Duplicate brand + manufacturer_code within the file")
                err(other_errors, "Duplicate brand + manufacturer_code within the file", i)
            seen_pairs.add(pair)

        # Barcode + similar-code checks (warnings)
        if barcode:
            cslug = _slug(code) if code else ""
            if barcode in existing_barcodes:
                warnings.append(WARN_BARCODE_EXISTS)
                err(warn_groups, WARN_BARCODE_EXISTS, i)
            if code and (barcode, cslug) in existing_barcode_slugs:
                warnings.append(WARN_DUP_ITEM_DB)
                err(warn_groups, WARN_DUP_ITEM_DB, i)
            seen = barcode_slugs_seen.get(barcode)
            if seen is not None:
                if cslug in seen:
                    warnings.append(WARN_DUP_ITEM_FILE)
                    err(warn_groups, WARN_DUP_ITEM_FILE, i)
                else:
                    warnings.append(WARN_DUP_BARCODE_FILE)
                    err(warn_groups, WARN_DUP_BARCODE_FILE, i)
            barcode_slugs_seen.setdefault(barcode, set()).add(cslug)

        if selling_price:
            try:
                if float(selling_price) < 0:
                    errors.append("selling_price cannot be negative")
                    err(other_errors, "selling_price cannot be negative", i)
                elif not selling_currency:
                    errors.append("selling_currency is required when selling_price is set")
                    err(other_errors, "selling_currency is required when selling_price is set", i)
                elif selling_currency.upper() not in SUPPORTED_CURRENCIES:
                    errors.append(f"Unsupported selling_currency: {selling_currency}")
                    err(other_errors, "Unsupported selling_currency", i)
            except ValueError:
                errors.append(f"selling_price is not a number: {selling_price}")
                err(other_errors, "selling_price is not a number", i)

        if cost_price:
            try:
                if float(cost_price) < 0:
                    errors.append("cost_price cannot be negative")
                    err(other_errors, "cost_price cannot be negative", i)
                elif not cost_currency:
                    errors.append("cost_currency is required when cost_price is set")
                    err(other_errors, "cost_currency is required when cost_price is set", i)
                elif cost_currency.upper() not in SUPPORTED_CURRENCIES:
                    errors.append(f"Unsupported cost_currency: {cost_currency}")
                    err(other_errors, "Unsupported cost_currency", i)
            except ValueError:
                errors.append(f"cost_price is not a number: {cost_price}")
                err(other_errors, "cost_price is not a number", i)

        if reorder_level:
            try:
                if int(reorder_level) < 0:
                    errors.append("reorder_level cannot be negative")
                    err(other_errors, "reorder_level cannot be negative", i)
            except ValueError:
                errors.append(f"reorder_level must be a whole number: {reorder_level}")
                err(other_errors, "reorder_level must be a whole number", i)

        if track_stock and track_stock.lower() not in (TRUE_VALUES | FALSE_VALUES):
            errors.append(f"track_stock: invalid value '{track_stock}'")
            err(other_errors, "track_stock: invalid value", i)

        if len(description) > 1000:
            errors.append("description is too long (max 1000)")
            err(other_errors, "description is too long (max 1000)", i)

        parsed: dict | None = None
        if not errors:
            parsed = {
                "manufacturer_code": code,
                "brand": brands[brand.lower()],
                "category": categories[category.lower()],
                "unit": units[unit.lower()],
                "barcode": barcode or None,
                "price_minor": round(float(selling_price) * 100) if selling_price else 0,
                "selling_currency": selling_currency.upper() if selling_price else "GMD",
                "cost_price_minor": round(float(cost_price) * 100) if cost_price else None,
                "cost_currency": cost_currency.upper() if cost_price else None,
                "reorder_level": int(reorder_level) if reorder_level else 0,
                "track_stock": _parse_bool(track_stock),
                "description": description or None,
            }

        # Existing item (same brand + code)? -> UPDATE (warning), not an error.
        is_update = False
        changed_fields: list[str] = []
        if parsed is not None and code and brand:
            existing = existing_by_key.get((brand.lower(), code))
            if existing is not None:
                is_update = True
                update_rows.append(i)
                for f in UPDATE_FIELDS:
                    if parsed[f] != getattr(existing, f):
                        changed_fields.append(FIELD_LABELS[f])
                warnings.append(
                    "Updates existing item" + (f" ({', '.join(changed_fields)})" if changed_fields else " (no field changes)")
                )

        status: Literal["ready", "warning", "error"] = (
            "error" if errors else ("warning" if (warnings or is_update) else "ready")
        )

        rows.append((
            ImportRowResult(
                row=i, manufacturer_code=code or None, brand=brand or None,
                status=status, errors=errors, warnings=warnings,
                is_update=is_update, changed_fields=changed_fields,
            ),
            parsed,
        ))

    # Build grouped issues
    issues: list[ImportIssue] = []

    def add_fixable(mapping, kind, action, noun):
        for value, rowlist in mapping.items():
            issues.append(ImportIssue(
                kind=kind, label=f'Unknown {noun} "{value}"', value=value,
                action=action, severity="error", count=len(rowlist), rows=rowlist[:50],
            ))

    add_fixable(unknown_brands, "unknown_brand", "add_brand", "brand")
    add_fixable(unknown_categories, "unknown_category", "add_category", "category")
    add_fixable(unknown_units, "unknown_unit", "add_unit", "unit")

    for msg, rowlist in other_errors.items():
        issues.append(ImportIssue(kind="other", label=msg, severity="error",
                                  count=len(rowlist), rows=rowlist[:50]))
    for msg, rowlist in warn_groups.items():
        issues.append(ImportIssue(kind="other", label=msg, severity="warning",
                                  count=len(rowlist), rows=rowlist[:50]))
    if update_rows:
        issues.append(ImportIssue(
            kind="existing_update",
            label="Already in the system — will be updated, not duplicated",
            severity="warning", count=len(update_rows), rows=update_rows[:50],
        ))

    # errors first, actionable first, then by count desc
    issues.sort(key=lambda g: (g.severity != "error", g.action is None, -g.count))

    return header_errors, False, rows, issues


# ── Preview ──
@router.post("/preview", response_model=ImportPreview)
async def preview_import(db: DbSession, file: UploadFile = File(...)) -> ImportPreview:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    text = _read_text(await file.read())
    refs = await _load_reference(db)
    header_errors, _fatal, rows, issues = _validate(text, refs)
    results = [r for (r, _) in rows]

    return ImportPreview(
        filename=file.filename or "",
        total=len(results),
        ready=sum(1 for r in results if r.status == "ready"),
        warnings=sum(1 for r in results if r.status == "warning"),
        errors=sum(1 for r in results if r.status == "error"),
        header_errors=header_errors,
        issues=issues,
        rows=results,
    )


# ── Confirm ──
async def _unique_sku(db: DbSession, base: str, used: set[str]) -> str:
    candidate, n = base, 1
    while candidate in used or await db.scalar(select(Product.id).where(Product.sku == candidate)):
        n += 1
        candidate = f"{base}-{n}"
    used.add(candidate)
    return candidate


@router.post("/confirm", response_model=ImportResult)
async def confirm_import(db: DbSession, file: UploadFile = File(...)) -> ImportResult:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    text = _read_text(await file.read())
    refs = await _load_reference(db)
    header_errors, fatal, rows, _issues = _validate(text, refs)
    error_count = sum(1 for (r, _) in rows if r.status == "error")

    if fatal or error_count > 0:
        return ImportResult(
            success=False, imported=0, total=len(rows), errors=error_count,
            message="Import cancelled — fix the errors and try again.",
            header_errors=header_errors,
        )

    existing_by_key = refs[3]
    used_skus: set[str] = set()
    created = 0
    updated = 0
    try:
        for _result, parsed in rows:
            assert parsed is not None
            existing = existing_by_key.get((parsed["brand"].lower(), parsed["manufacturer_code"]))
            if existing is not None:
                for f in UPDATE_FIELDS:
                    setattr(existing, f, parsed[f])
                updated += 1
            else:
                base = (f"{_slug(parsed['brand'])}-{_slug(parsed['manufacturer_code'])}"
                        if parsed["brand"] else _slug(parsed["manufacturer_code"]))
                base = base.strip("-") or "ITEM"
                sku = await _unique_sku(db, base, used_skus)
                name = _build_name(parsed["brand"], parsed["category"], parsed["manufacturer_code"])
                db.add(Product(name=name, sku=sku, **parsed))
                created += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Import failed while saving; nothing was written.")

    parts = []
    if created:
        parts.append(f"imported {created} new")
    if updated:
        parts.append(f"updated {updated}")
    msg = (", ".join(parts).capitalize() + " item(s).") if parts else "Nothing to import."
    return ImportResult(
        success=True, imported=created, updated=updated, total=len(rows), errors=0,
        message=msg, header_errors=header_errors,
    )