"""
Unit tests for MongoDB Persistence and Fallback Repository Layer
"""
import pytest
from unittest.mock import MagicMock, patch
from app.db.mongo import MongoManager, MongoRepository
from app.config.settings import settings


def test_mongo_manager_graceful_offline_fallback():
    """Verify system does not crash when MongoDB is offline."""
    with patch("app.db.mongo.MongoClient", side_effect=Exception("Connection refused")):
        MongoManager._client = None
        MongoManager._db = None
        MongoManager._connected = False
        
        db = MongoManager.get_db()
        assert db is None
        assert not MongoManager.is_connected()


def test_mongo_repository_offline_returns_none_safely():
    """Verify repository returns safe fallback values when offline."""
    with patch.object(MongoManager, "get_db", return_value=None):
        # Save operations return False safely
        assert MongoRepository.save_dataset_metadata("ds-1", {"rows": 10}) is False
        assert MongoRepository.save_forecast_result({"dataset_id": "ds-1"}) is False
        assert MongoRepository.save_evaluation_comparison("ds-1", {}) is False
        assert MongoRepository.save_business_insights({"dataset_id": "ds-1"}) is False
        assert MongoRepository.save_monitoring_report("ds-1", {}) is False

        # Retrieval operations return None safely
        assert MongoRepository.get_dataset_metadata("ds-1") is None
        assert MongoRepository.get_forecast_result("ds-1", "s1", "ARIMA", 28) is None
        assert MongoRepository.get_evaluation_comparison("ds-1") is None
        assert MongoRepository.get_business_insights("ds-1", "s1", 28, "ARIMA") is None
        assert MongoRepository.get_monitoring_report("ds-1") is None


def test_mongo_repository_online_operations():
    """Verify repository saves and reads documents when connected."""
    mock_db = MagicMock()
    mock_db.datasets = MagicMock()
    mock_db.forecast_results = MagicMock()
    mock_db.evaluations = MagicMock()
    mock_db.business_insights = MagicMock()
    mock_db.monitoring_reports = MagicMock()

    mock_db.datasets.find_one.return_value = {"dataset_id": "ds-100", "metadata": {"rows": 500}}
    mock_db.forecast_results.find_one.return_value = {"dataset_id": "ds-100", "forecast": [10.0, 12.0]}
    mock_db.evaluations.find_one.return_value = {"dataset_id": "ds-100", "best_model_overall": {"model": "LightGBM"}}

    with patch.object(MongoManager, "get_db", return_value=mock_db):
        # Test saves
        assert MongoRepository.save_dataset_metadata("ds-100", {"rows": 500}) is True
        mock_db.datasets.update_one.assert_called_once()

        assert MongoRepository.save_forecast_result({
            "dataset_id": "ds-100",
            "series_id": "s-1",
            "model": "LightGBM",
            "forecast_horizon": 28
        }) is True
        mock_db.forecast_results.update_one.assert_called_once()

        # Test gets
        meta = MongoRepository.get_dataset_metadata("ds-100")
        assert meta == {"rows": 500}

        fc = MongoRepository.get_forecast_result("ds-100", "s-1", "LightGBM", 28)
        assert fc["forecast"] == [10.0, 12.0]

        ev = MongoRepository.get_evaluation_comparison("ds-100")
        assert ev["best_model_overall"]["model"] == "LightGBM"
