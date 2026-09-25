import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import (
    OVEN_TYPE_STONE,
    OVEN_TYPE_TRAY,
    Batch,
    ConflictLog,
    Oven,
    Product,
)


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    p_tray = Product(name="盘式产品", ferment_min=40, bake_min=35, oven_type=OVEN_TYPE_TRAY)
    p_stone = Product(name="石板产品", ferment_min=45, bake_min=30, oven_type=OVEN_TYPE_STONE)
    o1 = Oven(label="一层 1 号炉", capacity_note="盘炉", oven_type=OVEN_TYPE_TRAY)
    o2 = Oven(label="一层 2 号炉", capacity_note="盘炉", oven_type=OVEN_TYPE_TRAY)
    o3 = Oven(label="二层石板炉", capacity_note="石板", oven_type=OVEN_TYPE_STONE)
    db.add_all([p_tray, p_stone, o1, o2, o3])
    db.flush()
    db.add(Batch(product_id=p_tray.id, oven_id=o1.id, code="BO-0900", start_min=9 * 60))
    db.commit()
    ids = dict(
        p_tray=p_tray.id, p_stone=p_stone.id, o1=o1.id, o2=o2.id, o3=o3.id
    )
    db.close()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    # 不使用 with：避免触发 lifespan 去连真实数据库（建表已在上面完成）
    c = TestClient(app)
    yield c, Session, ids
    app.dependency_overrides.clear()


def test_stone_product_into_tray_oven_rejected_as_type_mismatch(client):
    c, Session, ids = client
    r = c.post("/api/batches", json={"product_id": ids["p_stone"], "oven_id": ids["o1"], "start_min": 12 * 60})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "炉型不符" in detail
    assert "重叠" not in detail

    # 写入冲突日志，且没有创建批次
    s = Session()
    log = s.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).first()
    assert log is not None and "炉型不符" in log.detail
    assert s.scalars(select(Batch).where(Batch.code.like("BO-%"))).all().__len__() == 1
    s.close()


def test_stone_product_into_stone_oven_free_succeeds(client):
    c, _Session, ids = client
    r = c.post("/api/batches", json={"product_id": ids["p_stone"], "oven_id": ids["o3"], "start_min": 12 * 60})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["oven_oven_type"] == OVEN_TYPE_STONE
    assert body["product_oven_type"] == OVEN_TYPE_STONE
    assert body["type_mismatch"] is False


def test_same_type_overlap_still_reported_as_overlap(client):
    c, _Session, ids = client
    # 既有 9:00 盘式批次占 [540,615)，9:10 同炉再排必然重叠
    r = c.post("/api/batches", json={"product_id": ids["p_tray"], "oven_id": ids["o1"], "start_min": 9 * 60 + 10})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "重叠" in detail
    assert "炉型不符" not in detail


def test_same_type_half_open_touch_allowed(client):
    c, _Session, ids = client
    # 既有批次 10:15 结束，半开区间下 10:15 整开工不冲突
    r = c.post("/api/batches", json={"product_id": ids["p_tray"], "oven_id": ids["o1"], "start_min": 10 * 60 + 15})
    assert r.status_code == 200, r.text


def test_windows_only_list_matching_oven_type(client):
    c, _Session, ids = client
    r = c.get(f"/api/windows?product_id={ids['p_stone']}")
    assert r.status_code == 200
    oven_ids = {w["oven_id"] for w in r.json()}
    assert oven_ids == {ids["o3"]}

    r = c.get(f"/api/windows?product_id={ids['p_tray']}")
    oven_ids = {w["oven_id"] for w in r.json()}
    assert ids["o3"] not in oven_ids
    assert {ids["o1"], ids["o2"]} <= oven_ids


def test_gantt_excludes_type_mismatched_batches(client):
    c, Session, ids = client
    # 直接落一条炉型不符的批次（绕过排入接口）
    s = Session()
    s.add(Batch(product_id=ids["p_stone"], oven_id=ids["o1"], code="BO-MISMATCH", start_min=13 * 60))
    s.commit()
    s.close()

    r = c.get("/api/gantt")
    codes = {b["code"] for b in r.json()}
    assert "BO-MISMATCH" not in codes
    assert "BO-0900" in codes


def test_batches_mark_type_mismatch(client):
    c, Session, ids = client
    s = Session()
    s.add(Batch(product_id=ids["p_stone"], oven_id=ids["o1"], code="BO-MISMATCH", start_min=13 * 60))
    s.commit()
    s.close()

    r = c.get("/api/batches")
    row = next(b for b in r.json() if b["code"] == "BO-MISMATCH")
    assert row["type_mismatch"] is True


def test_oven_type_change_persists(client):
    c, Session, ids = client
    r = c.patch(f"/api/ovens/{ids['o1']}", json={"oven_type": OVEN_TYPE_STONE})
    assert r.status_code == 200
    assert r.json()["oven_type"] == OVEN_TYPE_STONE

    s = Session()
    assert s.get(Oven, ids["o1"]).oven_type == OVEN_TYPE_STONE
    s.close()

    r = c.get("/api/ovens")
    assert next(o for o in r.json() if o["id"] == ids["o1"])["oven_type"] == OVEN_TYPE_STONE


def test_product_type_change_persists_and_then_enforced(client):
    c, _Session, ids = client
    r = c.patch(f"/api/products/{ids['p_tray']}", json={"oven_type": OVEN_TYPE_STONE})
    assert r.status_code == 200
    # 改成石板后再排进盘炉应被拒
    r = c.post("/api/batches", json={"product_id": ids["p_tray"], "oven_id": ids["o2"], "start_min": 8 * 60})
    assert r.status_code == 409
    assert "炉型不符" in r.json()["detail"]
