from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Batch, ConflictLog, Oven, Product
from app.schemas.schemas import (
    BatchCreate,
    BatchOut,
    ConflictOut,
    GanttBlock,
    OvenOut,
    OvenUpdate,
    ProductOut,
    ProductUpdate,
    WindowOut,
)
from app.services.oven_engine import (
    OVEN_TYPES,
    Occupancy,
    RecipeDurations,
    build_occupancies,
    find_conflicts,
    next_free_window,
    parse_oven_types,
    type_matches,
)

api_router = APIRouter()


def _normalize_oven_types(raw: str) -> str:
    """Validate a comma-separated oven-type list and store it in canonical order."""
    parts = parse_oven_types(raw)
    if not parts or any(t not in OVEN_TYPES for t in parts):
        raise HTTPException(422, f"炉型无效：{raw}（可选：{'、'.join(OVEN_TYPES)}）")
    return ",".join(t for t in OVEN_TYPES if t in parts)


def _recipe(p: Product) -> RecipeDurations:
    return RecipeDurations(p.ferment_min, p.bake_min)


def _all_occupancies(db: Session) -> list[Occupancy]:
    batches = db.scalars(select(Batch)).all()
    out: list[Occupancy] = []
    for b in batches:
        p = db.get(Product, b.product_id)
        if not p:
            continue
        out.extend(build_occupancies(b.oven_id, b.id, b.start_min, _recipe(p)))
    return out


def _batch_out(db: Session, b: Batch) -> BatchOut:
    p = db.get(Product, b.product_id)
    o = db.get(Oven, b.oven_id)
    ferment_end = b.start_min + (p.ferment_min if p else 0)
    bake_end = ferment_end + (p.bake_min if p else 0)
    return BatchOut(
        id=b.id,
        product_id=b.product_id,
        oven_id=b.oven_id,
        code=b.code,
        start_min=b.start_min,
        status=b.status,
        product_name=p.name if p else None,
        oven_label=o.label if o else None,
        ferment_end=ferment_end,
        bake_end=bake_end,
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/products", response_model=list[ProductOut])
def products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id)).all()


@api_router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "产品不存在")
    if body.oven_types is not None:
        product.oven_types = _normalize_oven_types(body.oven_types)
    db.commit()
    db.refresh(product)
    return product


@api_router.get("/ovens", response_model=list[OvenOut])
def ovens(db: Session = Depends(get_db)):
    return db.scalars(select(Oven).order_by(Oven.id)).all()


@api_router.patch("/ovens/{oven_id}", response_model=OvenOut)
def update_oven(oven_id: int, body: OvenUpdate, db: Session = Depends(get_db)):
    oven = db.get(Oven, oven_id)
    if not oven:
        raise HTTPException(404, "炉位不存在")
    if body.oven_type is not None:
        if body.oven_type not in OVEN_TYPES:
            raise HTTPException(422, f"炉型无效：{body.oven_type}（可选：{'、'.join(OVEN_TYPES)}）")
        oven.oven_type = body.oven_type
    db.commit()
    db.refresh(oven)
    return oven


@api_router.get("/batches", response_model=list[BatchOut])
def batches(db: Session = Depends(get_db)):
    rows = db.scalars(select(Batch).order_by(Batch.start_min)).all()
    return [_batch_out(db, b) for b in rows]


@api_router.post("/batches", response_model=BatchOut)
def create_batch(body: BatchCreate, db: Session = Depends(get_db)):
    product = db.get(Product, body.product_id)
    oven = db.get(Oven, body.oven_id)
    if not product or not oven:
        raise HTTPException(404, "产品或炉位不存在")
    code = body.code or f"BO-{body.start_min}"
    if not type_matches(product.oven_types, oven.oven_type):
        detail = (
            f"炉型不符：产品「{product.name}」可进 {product.oven_types}，"
            f"炉位「{oven.label}」为 {oven.oven_type}"
        )
        db.add(ConflictLog(batch_code=code, oven_id=oven.id, detail=detail))
        db.commit()
        raise HTTPException(409, detail)
    recipe = _recipe(product)
    candidates = build_occupancies(oven.id, -1, body.start_min, recipe)
    existing = _all_occupancies(db)
    hits = find_conflicts(existing, candidates)
    if hits:
        ex, cand = hits[0]
        detail = (
            f"与批次#{ex.batch_id} 的 {ex.phase} 段重叠："
            f"[{cand.interval.start},{cand.interval.end})"
        )
        db.add(ConflictLog(batch_code=code, oven_id=oven.id, detail=detail))
        db.commit()
        raise HTTPException(409, detail)
    batch = Batch(
        product_id=product.id,
        oven_id=oven.id,
        code=code,
        start_min=body.start_min,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _batch_out(db, batch)


@api_router.get("/gantt", response_model=list[GanttBlock])
def gantt(db: Session = Depends(get_db)):
    blocks: list[GanttBlock] = []
    for b in db.scalars(select(Batch).order_by(Batch.start_min)).all():
        p = db.get(Product, b.product_id)
        o = db.get(Oven, b.oven_id)
        if not p or not o:
            continue
        for occ in build_occupancies(b.oven_id, b.id, b.start_min, _recipe(p)):
            blocks.append(
                GanttBlock(
                    batch_id=b.id,
                    code=b.code,
                    oven_id=o.id,
                    oven_label=o.label,
                    phase=occ.phase,
                    start_min=occ.interval.start,
                    end_min=occ.interval.end,
                )
            )
    return blocks


@api_router.get("/conflicts", response_model=list[ConflictOut])
def conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.get("/windows", response_model=list[WindowOut])
def windows(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "产品不存在")
    duration = product.ferment_min + product.bake_min
    existing = _all_occupancies(db)
    out: list[WindowOut] = []
    for oven in db.scalars(select(Oven).order_by(Oven.id)).all():
        if not type_matches(product.oven_types, oven.oven_type):
            continue
        w = next_free_window(existing, oven.id, duration, search_from=8 * 60, search_to=22 * 60)
        if w:
            out.append(
                WindowOut(
                    oven_id=oven.id,
                    oven_label=oven.label,
                    start_min=w.start,
                    end_min=w.end,
                    duration_min=duration,
                )
            )
    return out
