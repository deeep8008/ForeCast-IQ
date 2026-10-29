"""
Backend regression tests for dataset persistence and backend restart restoration.
Validates:
1. Full CSV content compressed persistence in MongoDB alongside metadata.
2. Complete restoration of DataFrame into DATASET_STORE after simulated backend restart (memory clear).
3. Exact row counts and temporal split counts preservation across restarts.
4. Graceful handling when dataset does not exist.
"""
import io
import zlib
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.mongo import MongoRepository, MongoManager
from app.data.loader import (
    DATASET_STORE,
    save_dataset,
    get_dataset,
    load_csv_from_bytes,
)
from app.data.cleaner import CLEANED_DATASET_STORE

client = TestClient(app)

SAMPLE_CSV = """date,series_id,target,store_id,item_id
2024-01-01,STORE_01_ITEM_A,10.0,STORE_01,ITEM_A
2024-01-02,STORE_01_ITEM_A,12.0,STORE_01,ITEM_A
2024-01-03,STORE_01_ITEM_A,15.0,STORE_01,ITEM_A
2024-01-04,STORE_01_ITEM_A,14.0,STORE_01,ITEM_A
2024-01-05,STORE_01_ITEM_A,18.0,STORE_01,ITEM_A
"""

def test_mongo_dataset_record_compression_roundtrip():
    """Verify raw CSV compresses and decompresses with exact fidelity in MongoRepository."""
    mock_db = MagicMock()
    stored_doc = {}
    def fake_update(query, update, upsert=False):
        stored_doc.update(update["$set"])
        return MagicMock()
    def fake_find(query):
        if query.get("dataset_id") == stored_doc.get("dataset_id"):
            return stored_doc
        return None

    mock_db.datasets.update_one.side_effect = fake_update
    mock_db.datasets.find_one.side_effect = fake_find

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        meta = {"filename": "test.csv", "rows": 5, "canonical_columns": ["date", "series_id", "target"]}
        save_success = MongoRepository.save_dataset_record("ds_test_123", meta, SAMPLE_CSV)
        assert save_success is True
        assert "csv_compressed" in stored_doc
        assert isinstance(stored_doc["csv_compressed"], bytes)

        # Retrieve record
        record = MongoRepository.get_dataset_record("ds_test_123")
        assert record is not None
        retrieved_meta, retrieved_csv = record
        assert retrieved_meta["rows"] == 5
        assert retrieved_csv == SAMPLE_CSV


def test_loader_restores_from_mongo_after_restart():
    """Verify get_dataset restores DataFrame from MongoDB when in-memory cache is empty."""
    DATASET_STORE.clear()
    compressed_csv = zlib.compress(SAMPLE_CSV.encode("utf-8"), level=6)
    mock_doc = {
        "dataset_id": "ds_restart_sim",
        "metadata": {"filename": "sim.csv", "rows": 5},
        "csv_compressed": compressed_csv
    }

    mock_db = MagicMock()
    mock_db.datasets.find_one.return_value = mock_doc

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        # Cache is initially empty
        assert "ds_restart_sim" not in DATASET_STORE

        # get_dataset should automatically recover from MongoDB
        entry = get_dataset("ds_restart_sim")
        assert entry is not None
        df = entry["df"]
        assert len(df) == 5
        assert list(df.columns) == ["date", "series_id", "target", "store_id", "item_id"]
        # And should now be re-cached in DATASET_STORE
        assert "ds_restart_sim" in DATASET_STORE


def test_edge_case_dataset_persistence_and_endpoints_after_restart():
    """Verify 03_edge_case_retail.csv retains exact row counts and temporal splits after restart."""
    import os
    edge_csv_path = r"c:\Users\BHARGAV709\Downloads\Major Project\Major Project\datasets\03_edge_case_retail.csv"
    if not os.path.exists(edge_csv_path):
        edge_csv_path = r"C:\Users\BHARGAV709\Downloads\03_edge_case_retail.csv"
    if not os.path.exists(edge_csv_path):
        pytest.skip("03_edge_case_retail.csv not found at expected path")

    with open(edge_csv_path, "r", encoding="utf-8") as f:
        edge_csv_content = f.read()

    # Emulate real upload via load_csv_from_bytes
    dataset_id, audit = load_csv_from_bytes(edge_csv_content.encode("utf-8"), filename="03_edge_case_retail.csv")
    entry_raw = get_dataset(dataset_id)
    assert len(entry_raw["df"]) == 625

    mock_db = MagicMock()
    mongo_storage = {}
    def fake_update(query, update, upsert=False):
        mongo_storage[query["dataset_id"]] = dict(update["$set"])
        return MagicMock()
    def fake_find(query):
        return mongo_storage.get(query.get("dataset_id"))

    mock_db.datasets.update_one.side_effect = fake_update
    mock_db.datasets.find_one.side_effect = fake_find

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        save_dataset(dataset_id, entry_raw["df"], "03_edge_case_retail.csv", metadata={"filename": "03_edge_case_retail.csv"})
        assert dataset_id in DATASET_STORE

        # SIMULATE BACKEND RESTART: Clear memory store and cleaned store
        DATASET_STORE.clear()
        if dataset_id in CLEANED_DATASET_STORE:
            del CLEANED_DATASET_STORE[dataset_id]
        assert dataset_id not in DATASET_STORE

        # Query endpoints via TestClient after restart
        # 1. Preview
        r_prev = client.get(f"/api/data/{dataset_id}/preview")
        assert r_prev.status_code == 200
        prev_data = r_prev.json()
        assert "headers" in prev_data
        assert "date" in prev_data["headers"]
        assert len(prev_data["rows"]) == 5

        # 2. Readiness and Profile
        r_ready = client.get(f"/api/data/{dataset_id}/readiness")
        assert r_ready.status_code == 200
        ready_data = r_ready.json()
        assert ready_data["profile"]["rows_count"] == 625

        # 3. Clean
        r_clean = client.post(f"/api/data/{dataset_id}/clean")
        assert r_clean.status_code == 200
        clean_data = r_clean.json()
        assert clean_data["raw_row_count"] == 625
        assert clean_data["cleaned_row_count"] == 621

        # 4. Splits
        r_splits = client.get(f"/api/data/{dataset_id}/splits?test_horizon=28&val_horizon=14")
        assert r_splits.status_code == 200
        splits_data = r_splits.json()
        assert splits_data["train_row_count"] == 538
        assert splits_data["validation_row_count"] == 28
        assert splits_data["test_row_count"] == 55
        assert splits_data["train_row_count"] + splits_data["validation_row_count"] + splits_data["test_row_count"] == 621


def test_get_nonexistent_dataset_returns_none():
    """Verify query for nonexistent dataset returns None and 404 in API."""
    DATASET_STORE.clear()
    mock_db = MagicMock()
    mock_db.datasets.find_one.return_value = None

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        df = get_dataset("non_existent_dataset_999")
        assert df is None

        r = client.get("/api/data/non_existent_dataset_999/preview")
        assert r.status_code == 404


def test_forecast_and_evaluation_persistence_in_mongo():
    """Verify that forecast endpoints and evaluation endpoints persist results to MongoDB."""
    mock_db = MagicMock()
    eval_docs = {}
    forecast_docs = {}

    def fake_eval_update(query, update, upsert=False):
        eval_docs[query["dataset_id"]] = update["$set"]
        return MagicMock()

    def fake_forecast_update(query, update, upsert=False):
        forecast_docs[query["dataset_id"]] = update["$set"]
        return MagicMock()

    mock_db.evaluations.update_one.side_effect = fake_eval_update
    mock_db.forecast_results.update_one.side_effect = fake_forecast_update

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        ds_id = "test_persist_ds_1"
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=60, freq="D"),
            "series_id": ["S1"] * 60,
            "target": [float(i) for i in range(60)]
        })
        save_dataset(ds_id, df, "test_p.csv")

        # 1. Test forecast route persists
        r_fc = client.post(f"/api/forecast/arima?dataset_id={ds_id}&series_id=S1&horizon=7")
        assert r_fc.status_code == 200
        assert ds_id in forecast_docs
        assert forecast_docs[ds_id]["forecast_horizon"] == 7

        # 2. Test evaluation backtest persists
        r_bt = client.post("/api/evaluation/backtest", json={
            "dataset_id": ds_id,
            "series_ids": ["S1"],
            "models": ["arima"],
            "horizons": [7],
            "n_folds": 2
        })
        assert r_bt.status_code == 200
        assert ds_id in eval_docs
        assert "arima" in eval_docs[ds_id]["models_evaluated"]

