from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    OVEN_TYPE_LABELS,
    OVEN_TYPES,
    Batch,
    ConflictLog,
    Oven,
    Product,
)
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
    Occupancy,
    RecipeDurations,
    build_occupancies,
    find_conflicts,
    next_free_window,
)

api_router = APIRouter()


def _recipe(p: Product) -> RecipeDurations:
    return RecipeDurations(p.ferment_min, p.bake_min)


def _type_label(t: str | None) -> str:
    return OVEN_TYPE_LABELS.get(t or "", t or "未知")


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
        product_oven_type=p.oven_type if p else None,
        oven_label=o.label if o else None,
        oven_oven_type=o.oven_type if o else None,
        type_mismatch=bool(p and o and p.oven_type != o.oven_type),
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
    if body.oven_type not in OVEN_TYPES:
        raise HTTPException(422, "未知炉型")
    product.oven_type = body.oven_type
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
    if body.oven_type not in OVEN_TYPES:
        raise HTTPException(422, "未知炉型")
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

    # 炉型匹配优先于时间检测：不符直接拒绝，且不算时间重叠
    if product.oven_type != oven.oven_type:
        detail = (
            f"炉型不符：产品「{product.name}」只可进{_type_label(product.oven_type)}，"
            f"炉位「{oven.label}」为{_type_label(oven.oven_type)}"
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
        # 炉型不符的批次不进入甘特占炉
        if p.oven_type != o.oven_type:
            continue
        for occ in build_occupancies(b.oven_id, b.id, b.start_min, _recipe(p)):
            blocks.append(
                GanttBlock(
                    batch_id=b.id,
                    code=b.code,
                    oven_id=o.id,
                    oven_label=o.label,
                    oven_type=o.oven_type,
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
        # 可开工窗口只列炉型相符的炉
        if oven.oven_type != product.oven_type:
            continue
        w = next_free_window(existing, oven.id, duration, search_from=8 * 60, search_to=22 * 60)
        if w:
            out.append(
                WindowOut(
                    oven_id=oven.id,
                    oven_label=oven.label,
                    oven_type=oven.oven_type,
                    start_min=w.start,
                    end_min=w.end,
                    duration_min=duration,
                )
            )
    return out
