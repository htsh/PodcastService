import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_database: Optional[Database] = None

def get_mongo_uri() -> str:
    """Get MongoDB URI from environment variable or use default"""
    return os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')

def get_database_name() -> str:
    """Get database name from environment variable or use default"""
    return os.getenv('MONGODB_DATABASE', 'podcast_service')

def init_db() -> Database:
    """Initialize MongoDB connection and create indexes"""
    global _client, _database

    if _database is not None:
        return _database

    mongo_uri = get_mongo_uri()
    db_name = get_database_name()

    logger.info(f"Connecting to MongoDB at {mongo_uri}")

    try:
        _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Test the connection
        _client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")

        _database = _client[db_name]

        # Create indexes
        _create_indexes(_database)

        return _database
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

def _create_indexes(db: Database):
    """Create indexes for all collections"""
    logger.info("Creating database indexes...")

    # Episodes collection indexes
    episodes = db.episodes
    episodes.create_index([("url", ASCENDING)], unique=True)
    episodes.create_index([("file_hash", ASCENDING)])
    episodes.create_index([("processed_at", DESCENDING)])
    episodes.create_index([("subscription_id", ASCENDING)])
    episodes.create_index([("title", "text"), ("transcript", "text")],
                         name="text_search_index")

    # Subscriptions collection indexes
    subscriptions = db.subscriptions
    subscriptions.create_index([("id", ASCENDING)], unique=True)
    subscriptions.create_index([("type", ASCENDING)])

    # Settings collection - no indexes needed (single document)

    logger.info("Database indexes created successfully")

def get_database() -> Database:
    """Get the database instance, initializing if necessary"""
    if _database is None:
        return init_db()
    return _database

def close_connection():
    """Close the MongoDB connection"""
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed")
