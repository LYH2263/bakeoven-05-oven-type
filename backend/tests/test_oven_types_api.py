"""API-level tests for oven-type matching (盘炉 vs 石板).

Runs against a throwaway sqlite database seeded by the app lifespan.
"""

import os
import tempfile

_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SEED_ON_EMPTY"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# Seed ids: products 1=乡村欧包(石板) 2=黄油可颂(盘炉) 3=布朗尼(盘炉,石板)
# ovens 1=一层 1 号炉(盘炉) 2=一层 2 号炉(盘炉) 3=二层石板炉(石板)
STONE_PRODUCT = 1
DECK_PRODUCT = 2
DECK_OVEN = 1
STONE_OVEN = 3


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_stone_only_product_rejected_on_deck_oven(client):
    r = client.post(
        "/api/batches",
        json={"product_id": STONE_PRODUCT, "oven_id": DECK_OVEN, "start_min": 14 * 60, "code": "T-TYPE"},
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "炉型不符" in detail
    assert "重叠" not in detail


def test_type_mismatch_logged_in_conflicts(client):
    rows = client.get("/api/conflicts").json()
    mine = [c for c in rows if c["batch_code"] == "T-TYPE"]
    assert mine, "mismatch should be logged"
    assert "炉型不符" in mine[0]["detail"]
    assert "重叠" not in mine[0]["detail"]


def test_type_mismatch_not_on_gantt(client):
    codes = {b["code"] for b in client.get("/api/gantt").json()}
    assert "T-TYPE" not in codes


def test_stone_only_product_accepted_on_stone_oven(client):
    r = client.post(
        "/api/batches",
        json={"product_id": STONE_PRODUCT, "oven_id": STONE_OVEN, "start_min": 14 * 60, "code": "T-STONE"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "T-STONE"
    codes = {b["code"] for b in client.get("/api/gantt").json()}
    assert "T-STONE" in codes


def test_overlap_still_rejected_with_overlap_wording(client):
    # 黄油可颂(盘炉) on 一层 1 号炉 at 10:40 overlaps seeded BO-1030 (10:30–11:15)
    r = client.post(
        "/api/batches",
        json={"product_id": DECK_PRODUCT, "oven_id": DECK_OVEN, "start_min": 10 * 60 + 40, "code": "T-OVERLAP"},
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "重叠" in detail
    assert "炉型不符" not in detail


def test_windows_only_list_matching_ovens(client):
    stone = client.get("/api/windows", params={"product_id": STONE_PRODUCT}).json()
    assert stone and {w["oven_id"] for w in stone} == {STONE_OVEN}
    deck = client.get("/api/windows", params={"product_id": DECK_PRODUCT}).json()
    assert deck and {w["oven_id"] for w in deck} == {1, 2}


def test_patch_product_oven_types_persists(client):
    r = client.patch(f"/api/products/{DECK_PRODUCT}", json={"oven_types": "石板"})
    assert r.status_code == 200
    assert r.json()["oven_types"] == "石板"
    got = {p["id"]: p for p in client.get("/api/products").json()}[DECK_PRODUCT]
    assert got["oven_types"] == "石板"
    # windows for the product now only list stone ovens
    stone = client.get("/api/windows", params={"product_id": DECK_PRODUCT}).json()
    assert stone and {w["oven_id"] for w in stone} == {STONE_OVEN}
    client.patch(f"/api/products/{DECK_PRODUCT}", json={"oven_types": "盘炉"})
    assert {p["id"]: p for p in client.get("/api/products").json()}[DECK_PRODUCT]["oven_types"] == "盘炉"


def test_patch_oven_type_persists(client):
    r = client.patch("/api/ovens/2", json={"oven_type": "石板"})
    assert r.status_code == 200
    assert r.json()["oven_type"] == "石板"
    got = {o["id"]: o for o in client.get("/api/ovens").json()}[2]
    assert got["oven_type"] == "石板"
    client.patch("/api/ovens/2", json={"oven_type": "盘炉"})
    assert {o["id"]: o for o in client.get("/api/ovens").json()}[2]["oven_type"] == "盘炉"


def test_patch_rejects_invalid_oven_type(client):
    assert client.patch(f"/api/products/{DECK_PRODUCT}", json={"oven_types": "微波炉"}).status_code == 422
    assert client.patch("/api/ovens/2", json={"oven_type": "盘炉,石板"}).status_code == 422
