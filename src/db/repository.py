from typing import Optional, List, Dict, Any
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo import DESCENDING
import logging

from .models import Episode, Subscription, Settings

logger = logging.getLogger(__name__)


class EpisodeRepository:
    """Repository for Episode operations"""

    def __init__(self, db: Database):
        self.collection: Collection = db.episodes

    def create(self, episode: Episode) -> str:
        """Create a new episode"""
        try:
            result = self.collection.insert_one(episode.to_dict())
            logger.info(f"Created episode: {episode.title}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating episode: {e}")
            raise

    def upsert(self, episode: Episode) -> bool:
        """Update existing episode or create if doesn't exist"""
        try:
            result = self.collection.update_one(
                {"url": episode.url},
                {"$set": episode.to_dict()},
                upsert=True
            )
            logger.info(f"Upserted episode: {episode.title}")
            return True
        except Exception as e:
            logger.error(f"Error upserting episode: {e}")
            raise

    def find_by_url(self, url: str) -> Optional[Episode]:
        """Find episode by URL"""
        try:
            doc = self.collection.find_one({"url": url})
            return Episode.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error finding episode by URL: {e}")
            return None

    def find_by_id(self, episode_id: str) -> Optional[Episode]:
        """Find episode by custom id field"""
        try:
            doc = self.collection.find_one({"id": episode_id})
            return Episode.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error finding episode by ID: {e}")
            return None

    def find_all(self, limit: Optional[int] = None) -> List[Episode]:
        """Get all episodes, optionally limited"""
        try:
            cursor = self.collection.find().sort("processed_at", DESCENDING)
            if limit:
                cursor = cursor.limit(limit)
            return [Episode.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error finding all episodes: {e}")
            return []

    def find_by_subscription(self, subscription_id: str) -> List[Episode]:
        """Find all episodes for a subscription"""
        try:
            cursor = self.collection.find(
                {"subscription_id": subscription_id}
            ).sort("processed_at", DESCENDING)
            return [Episode.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error finding episodes by subscription: {e}")
            return []

    def search_text(self, query: str, limit: int = 10) -> List[Episode]:
        """Full-text search in title and transcript"""
        try:
            cursor = self.collection.find(
                {"$text": {"$search": query}}
            ).limit(limit)
            return [Episode.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error searching episodes: {e}")
            return []

    def update_summary(self, url: str, summary: Dict, summary_path: Optional[str] = None) -> bool:
        """Update episode summary"""
        try:
            update_data = {
                "summary": summary,
                "has_summary": True
            }
            if summary_path:
                update_data["summary_path"] = summary_path

            self.collection.update_one(
                {"url": url},
                {"$set": update_data}
            )
            logger.info(f"Updated summary for episode: {url}")
            return True
        except Exception as e:
            logger.error(f"Error updating summary: {e}")
            return False

    def delete_by_url(self, url: str) -> bool:
        """Delete episode by URL"""
        try:
            result = self.collection.delete_one({"url": url})
            logger.info(f"Deleted episode: {url}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting episode: {e}")
            return False

    def count(self) -> int:
        """Get total episode count"""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"Error counting episodes: {e}")
            return 0


class SubscriptionRepository:
    """Repository for Subscription operations"""

    def __init__(self, db: Database):
        self.collection: Collection = db.subscriptions

    def create(self, subscription: Subscription) -> bool:
        """Create a new subscription if it doesn't exist"""
        try:
            # Check if already exists
            existing = self.collection.find_one({"id": subscription.id})
            if existing:
                logger.info(f"Subscription already exists: {subscription.id}")
                return False

            self.collection.insert_one(subscription.to_dict())
            logger.info(f"Created subscription: {subscription.title}")
            return True
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise

    def find_by_id(self, subscription_id: str) -> Optional[Subscription]:
        """Find subscription by ID"""
        try:
            doc = self.collection.find_one({"id": subscription_id})
            return Subscription.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error finding subscription: {e}")
            return None

    def find_all(self) -> List[Subscription]:
        """Get all subscriptions"""
        try:
            cursor = self.collection.find()
            return [Subscription.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error finding all subscriptions: {e}")
            return []

    def find_by_type(self, subscription_type: str) -> List[Subscription]:
        """Find subscriptions by type (podcast or youtube)"""
        try:
            cursor = self.collection.find({"type": subscription_type})
            return [Subscription.from_dict(doc) for doc in cursor]
        except Exception as e:
            logger.error(f"Error finding subscriptions by type: {e}")
            return []

    def delete(self, subscription_id: str) -> bool:
        """Delete subscription by ID"""
        try:
            result = self.collection.delete_one({"id": subscription_id})
            logger.info(f"Deleted subscription: {subscription_id}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting subscription: {e}")
            return False

    def count(self) -> int:
        """Get total subscription count"""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"Error counting subscriptions: {e}")
            return 0


class SettingsRepository:
    """Repository for Settings operations (single document)"""

    def __init__(self, db: Database):
        self.collection: Collection = db.settings
        self._ensure_settings_exist()

    def _ensure_settings_exist(self):
        """Ensure a settings document exists"""
        if self.collection.count_documents({}) == 0:
            default_settings = Settings()
            self.collection.insert_one(default_settings.to_dict())
            logger.info("Created default settings document")

    def get(self) -> Settings:
        """Get settings (always returns a Settings object)"""
        try:
            doc = self.collection.find_one()
            return Settings.from_dict(doc) if doc else Settings()
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return Settings()

    def update(self, settings: Settings) -> bool:
        """Update settings"""
        try:
            # Replace the entire settings document
            self.collection.delete_many({})
            self.collection.insert_one(settings.to_dict())
            logger.info("Updated settings")
            return True
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False

    def update_field(self, field: str, value: Any) -> bool:
        """Update a single settings field"""
        try:
            self.collection.update_one(
                {},
                {"$set": {field: value}},
                upsert=True
            )
            logger.info(f"Updated settings field: {field}")
            return True
        except Exception as e:
            logger.error(f"Error updating settings field: {e}")
            return False
