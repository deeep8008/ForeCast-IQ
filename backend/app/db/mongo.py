"""
ForecastIQ MongoDB Persistence & Repository Layer

Provides clean repository pattern implementations for saving and retrieving:
1. Datasets & metadata
2. Forecast runs & Forecast results
3. Evaluation & Backtesting comparisons
4. Business insights
5. Model monitoring reports

Gracefully handles environments where MongoDB is unreachable or unconfigured,
falling back without disrupting in-memory or file-based operations.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import pymongo
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, PyMongoError

from ..config.settings import settings

logger = logging.getLogger(__name__)


class MongoManager:
    """Singleton connection manager for MongoDB with health-check and index management."""
    _client: Optional[MongoClient] = None
    _db = None
    _connected: bool = False
    _initialized_indexes: bool = False

    @classmethod
    def get_db(cls):
        """Returns the database instance if connected, else None."""
        if not settings.MONGODB_ENABLED:
            return None

        # Re-check or attempt connection if not yet connected
        if cls._client is None or not cls._connected:
            try:
                # 5s timeout is optimal for remote Atlas clusters while failing fast if offline
                cls._client = MongoClient(
                    settings.MONGODB_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000
                )
                # Check connection
                cls._client.admin.command('ping')
                cls._db = cls._client[settings.MONGODB_DATABASE]
                cls._connected = True
                logger.info(f"Connected successfully to MongoDB database '{settings.MONGODB_DATABASE}'")
                cls.ensure_indexes()
            except Exception as e:
                cls._connected = False
                cls._db = None
                cls._client = None
                logger.debug(f"MongoDB not available ({e}). Running in memory/file mode.")

        return cls._db

    @classmethod
    def is_connected(cls) -> bool:
        """Check if active connection exists."""
        db = cls.get_db()
        return db is not None and cls._connected

    @classmethod
    def ensure_indexes(cls):
        """Build required indexes according to specification."""
        if cls._db is None or cls._initialized_indexes:
            return

        try:
            # 1. datasets collection: dataset_id unique
            cls._db.datasets.create_index([("dataset_id", ASCENDING)], unique=True)

            # 2. forecast_runs: dataset_id + series_id + model + horizon
            cls._db.forecast_runs.create_index([
                ("dataset_id", ASCENDING),
                ("series_id", ASCENDING),
                ("model", ASCENDING),
                ("forecast_horizon", ASCENDING)
            ])

            # 3. forecast_results: dataset_id + series_id + model + horizon
            cls._db.forecast_results.create_index([
                ("dataset_id", ASCENDING),
                ("series_id", ASCENDING),
                ("model", ASCENDING),
                ("forecast_horizon", ASCENDING)
            ], unique=True)

            # 4. evaluations: dataset_id + series_id + model + horizon
            cls._db.evaluations.create_index([
                ("dataset_id", ASCENDING),
                ("series_id", ASCENDING),
                ("model", ASCENDING),
                ("horizon", ASCENDING)
            ])
            # dataset_id index (non-unique: multiple scopes per dataset allowed)
            cls._db.evaluations.create_index([("dataset_id", ASCENDING)])

            # 5. business_insights: dataset_id + series_id + horizon
            cls._db.business_insights.create_index([
                ("dataset_id", ASCENDING),
                ("series_id", ASCENDING),
                ("horizon", ASCENDING),
                ("model", ASCENDING)
            ], unique=True)

            # 6. monitoring_reports: dataset_id + model
            cls._db.monitoring_reports.create_index([
                ("dataset_id", ASCENDING)
            ], unique=True)

            # 7. users: normalized email unique
            cls._db.users.create_index([("email", ASCENDING)], unique=True)

            # 8. sessions: session_token_hash unique, and expires_at for indexing
            cls._db.sessions.create_index([("session_token_hash", ASCENDING)], unique=True)
            cls._db.sessions.create_index([("user_id", ASCENDING)])
            cls._db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

            cls._initialized_indexes = True
            logger.info("MongoDB indexes successfully created and verified.")
        except Exception as e:
            logger.warning(f"Could not build MongoDB indexes: {e}")


class MongoRepository:
    """Repository handling document storage and retrieval."""

    @staticmethod
    def save_dataset_metadata(dataset_id: str, metadata: Dict[str, Any]) -> bool:
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            doc = {
                "dataset_id": dataset_id,
                "metadata": metadata,
                "updated_at": datetime.utcnow()
            }
            db.datasets.update_one(
                {"dataset_id": dataset_id},
                {"$set": doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving dataset metadata to MongoDB: {e}")
            return False

    @staticmethod
    def save_dataset_record(dataset_id: str, metadata: Dict[str, Any], csv_content: str) -> bool:
        """Persist dataset metadata and compressed CSV text to MongoDB for durable restoration."""
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            import zlib
            compressed_bytes = zlib.compress(csv_content.encode("utf-8"), level=6)
            doc = {
                "dataset_id": dataset_id,
                "metadata": metadata,
                "csv_compressed": compressed_bytes,
                "updated_at": datetime.utcnow()
            }
            db.datasets.update_one(
                {"dataset_id": dataset_id},
                {"$set": doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving dataset record to MongoDB: {e}")
            return False

    @staticmethod
    def get_dataset_metadata(dataset_id: str) -> Optional[Dict[str, Any]]:
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            res = db.datasets.find_one({"dataset_id": dataset_id})
            if res and "metadata" in res:
                return res["metadata"]
            return None
        except Exception as e:
            logger.warning(f"Error fetching dataset metadata from MongoDB: {e}")
            return None

    @staticmethod
    def get_dataset_record(dataset_id: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Retrieve dataset metadata and decompressed CSV text from MongoDB."""
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            res = db.datasets.find_one({"dataset_id": dataset_id})
            if not res or "metadata" not in res:
                return None
            metadata = res["metadata"]
            csv_content = ""
            if "csv_compressed" in res and res["csv_compressed"]:
                import zlib
                csv_content = zlib.decompress(res["csv_compressed"]).decode("utf-8")
            elif "csv_text" in res and res["csv_text"]:
                csv_content = res["csv_text"]
            return metadata, csv_content
        except Exception as e:
            logger.warning(f"Error fetching dataset record from MongoDB: {e}")
            return None

    @staticmethod
    def save_forecast_result(forecast_result_dict: Dict[str, Any]) -> bool:
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            query = {
                "dataset_id": forecast_result_dict.get("dataset_id"),
                "series_id": forecast_result_dict.get("series_id"),
                "model": forecast_result_dict.get("model"),
                "forecast_horizon": forecast_result_dict.get("forecast_horizon")
            }
            doc = {
                **forecast_result_dict,
                "updated_at": datetime.utcnow()
            }
            db.forecast_results.update_one(query, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.warning(f"Error saving forecast result to MongoDB: {e}")
            return False

    @staticmethod
    def get_forecast_result(dataset_id: str, series_id: str, model: str, horizon: int) -> Optional[Dict[str, Any]]:
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            res = db.forecast_results.find_one({
                "dataset_id": dataset_id,
                "series_id": series_id,
                "model": model,
                "forecast_horizon": horizon
            }, {"_id": 0, "updated_at": 0})
            return res
        except Exception as e:
            logger.warning(f"Error getting forecast result from MongoDB: {e}")
            return None

    @staticmethod
    def save_evaluation_comparison(dataset_id: str, evaluation_dict: Dict[str, Any], scope_key: Optional[str] = None) -> bool:
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            sk = scope_key or evaluation_dict.get("scope_key") or "default"
            doc = {
                "dataset_id": dataset_id,
                "scope_key": sk,
                **evaluation_dict,
                "updated_at": datetime.utcnow()
            }
            db.evaluations.update_one(
                {"dataset_id": dataset_id, "scope_key": sk},
                {"$set": doc},
                upsert=True
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving evaluation comparison to MongoDB: {e}")
            return False

    @staticmethod
    def get_evaluation_comparison(dataset_id: str, scope_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            q = {"dataset_id": dataset_id}
            if scope_key:
                q["scope_key"] = scope_key
            res = db.evaluations.find_one(q, {"_id": 0, "updated_at": 0})
            return res
        except Exception as e:
            logger.warning(f"Error fetching evaluation comparison from MongoDB: {e}")
            return None

    @staticmethod
    def save_business_insights(insights_dict: Dict[str, Any]) -> bool:
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            query = {
                "dataset_id": insights_dict.get("dataset_id"),
                "series_id": insights_dict.get("series_id"),
                "horizon": insights_dict.get("horizon"),
                "model": insights_dict.get("model")
            }
            doc = {
                **insights_dict,
                "updated_at": datetime.utcnow()
            }
            db.business_insights.update_one(query, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.warning(f"Error saving business insights to MongoDB: {e}")
            return False

    @staticmethod
    def get_business_insights(dataset_id: str, series_id: str, horizon: int, model: str) -> Optional[Dict[str, Any]]:
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            res = db.business_insights.find_one({
                "dataset_id": dataset_id,
                "series_id": series_id,
                "horizon": horizon,
                "model": model
            }, {"_id": 0, "updated_at": 0})
            return res
        except Exception as e:
            logger.warning(f"Error getting business insights from MongoDB: {e}")
            return None

    @staticmethod
    def save_monitoring_report(dataset_id: str, report_dict: Dict[str, Any]) -> bool:
        db = MongoManager.get_db()
        if db is None:
            return False
        try:
            doc = {
                "dataset_id": dataset_id,
                **report_dict,
                "updated_at": datetime.utcnow()
            }
            db.monitoring_reports.update_one({"dataset_id": dataset_id}, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.warning(f"Error saving monitoring report to MongoDB: {e}")
            return False

    @staticmethod
    def get_monitoring_report(dataset_id: str) -> Optional[Dict[str, Any]]:
        db = MongoManager.get_db()
        if db is None:
            return None
        try:
            res = db.monitoring_reports.find_one({"dataset_id": dataset_id}, {"_id": 0, "updated_at": 0})
            return res
        except Exception as e:
            logger.warning(f"Error getting monitoring report from MongoDB: {e}")
            return None

    # ---------------------------------------------------------------------------
    # Authentication & User Management Repository Methods
    # ---------------------------------------------------------------------------
    @staticmethod
    def create_user(user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new user document into the users collection."""
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        now = datetime.utcnow()
        doc = {
            **user_doc,
            "created_at": user_doc.get("created_at") or now,
            "updated_at": user_doc.get("updated_at") or now,
            "is_active": user_doc.get("is_active", True),
        }
        res = db.users.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user by normalized email."""
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        normalized = email.strip().lower()
        user = db.users.find_one({"email": normalized})
        if user:
            user["_id"] = str(user["_id"])
        return user

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user by user_id string or ObjectId."""
        from bson import ObjectId
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        query = {"$or": [{"user_id": user_id}]}
        if ObjectId.is_valid(user_id):
            query["$or"].append({"_id": ObjectId(user_id)})
        
        user = db.users.find_one(query)
        if user:
            user["_id"] = str(user["_id"])
        return user

    @staticmethod
    def create_session(session_token_hash: str, user_id: str, email: str, expires_at: datetime) -> bool:
        """Store a hashed session token in the sessions collection."""
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        now = datetime.utcnow()
        doc = {
            "session_token_hash": session_token_hash,
            "user_id": user_id,
            "email": email.strip().lower(),
            "created_at": now,
            "expires_at": expires_at
        }
        db.sessions.update_one(
            {"session_token_hash": session_token_hash},
            {"$set": doc},
            upsert=True
        )
        return True

    @staticmethod
    def get_session(session_token_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve an active, non-expired session."""
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        now = datetime.utcnow()
        session = db.sessions.find_one({
            "session_token_hash": session_token_hash,
            "expires_at": {"$gt": now}
        })
        if session:
            session["_id"] = str(session["_id"])
        return session

    @staticmethod
    def delete_session(session_token_hash: str) -> bool:
        """Delete/invalidate a session token."""
        db = MongoManager.get_db()
        if db is None:
            raise ConnectionFailure("MongoDB is offline or unreachable.")
        
        db.sessions.delete_one({"session_token_hash": session_token_hash})
        return True

