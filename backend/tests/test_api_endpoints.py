"""
API Endpoint Integration Tests
ForecastIQ Backend
"""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_upload_valid_csv():
    csv_content = b"""date,series_id,target,store_id
2024-01-01,SERIES_1,10.0,STORE_A
2024-01-02,SERIES_1,15.0,STORE_A
2024-01-03,SERIES_1,20.0,STORE_A
"""
    files = {"file": ("sales_data.csv", io.BytesIO(csv_content), "text/csv")}
    response = client.post("/api/data/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "dataset_id" in data
    assert data["rows"] == 3
    assert data["columns"] == 4
    assert data["status"] == "READY"
    assert data["detected_mapping"]["date"] == "date"
    assert data["detected_mapping"]["series_id"] == "series_id"
    assert data["detected_mapping"]["target"] == "target"


def test_upload_invalid_extension():
    files = {"file": ("data.txt", io.BytesIO(b"some,data"), "text/plain")}
    response = client.post("/api/data/upload", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


def test_profile_validation_features_readiness_endpoints():
    csv_content = b"""date,series_id,target,price
2024-01-01,SERIES_A,25.0,3.99
2024-01-02,SERIES_A,28.0,3.99
2024-01-03,SERIES_A,30.0,3.99
"""
    files = {"file": ("endpoint_test.csv", io.BytesIO(csv_content), "text/csv")}
    upload_res = client.post("/api/data/upload", files=files)
    dataset_id = upload_res.json()["dataset_id"]

    # 1. Profile
    prof_res = client.get(f"/api/data/{dataset_id}/profile")
    assert prof_res.status_code == 200
    assert prof_res.json()["rows_count"] == 3
    assert prof_res.json()["unique_series_count"] == 1

    # 2. Validation
    val_res = client.get(f"/api/data/{dataset_id}/validation")
    assert val_res.status_code == 200
    assert val_res.json()["status"] == "READY"

    # 3. Features
    feat_res = client.get(f"/api/data/{dataset_id}/features")
    assert feat_res.status_code == 200
    assert len(feat_res.json()) == 4

    # 4. Readiness
    readiness_res = client.get(f"/api/data/{dataset_id}/readiness")
    assert readiness_res.status_code == 200
    assert readiness_res.json()["status"] == "READY"

    # 5. Remap
    remap_payload = {
        "date": "date",
        "series_id": "series_id",
        "target": "price",
        "optional": {}
    }
    remap_res = client.post(f"/api/data/{dataset_id}/remap", json=remap_payload)
    assert remap_res.status_code == 200
    assert remap_res.json()["column_mapping"]["target"] == "price"


def test_nonexistent_dataset_404():
    res = client.get("/api/data/nonexistent-id-000/profile")
    assert res.status_code == 404
