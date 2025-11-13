from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import hashlib
import shutil
from pymongo.database import Database

class CacheManager:
    """
    Cache manager that uses MongoDB for metadata and filesystem for large files.
    Audio files and transcripts are too large for MongoDB, so we keep them on disk.
    Subscriptions and episodes are now in MongoDB via repositories.
    """

    def __init__(self, db: Database):
        """Initialize with MongoDB database instance"""
        self.db = db

        # Set up file cache directories
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.downloads_cache = self.cache_dir / "downloads"
        self.downloads_cache.mkdir(exist_ok=True)

        self.transcripts_cache = self.cache_dir / "transcripts"
        self.transcripts_cache.mkdir(exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a stable cache key"""
        return hashlib.sha256(key.encode()).hexdigest()

    # Audio file caching (filesystem-based)
    def cache_download(self, url: str, file_path: Path, metadata: Optional[Dict] = None) -> None:
        """Cache a downloaded audio file"""
        cache_key = self._get_cache_key(url)
        cache_path = self.downloads_cache / f"{cache_key}{file_path.suffix}"

        # Copy file to cache
        shutil.copy2(file_path, cache_path)

        # Store metadata in MongoDB if provided
        if metadata:
            self.db.download_cache.update_one(
                {"url": url},
                {
                    "$set": {
                        "url": url,
                        "cache_key": cache_key,
                        "cache_path": str(cache_path),
                        "original_path": str(file_path),
                        "cached_at": datetime.utcnow().isoformat(),
                        "metadata": metadata
                    }
                },
                upsert=True
            )

    def get_cached_download_path(self, url: str) -> Optional[Path]:
        """Get path to cached download if it exists"""
        cache_key = self._get_cache_key(url)
        # Try common audio extensions
        for ext in ['.wav', '.mp3', '.m4a']:
            cache_path = self.downloads_cache / f"{cache_key}{ext}"
            if cache_path.exists():
                return cache_path
        return None

    def is_download_cached(self, url: str) -> bool:
        """Check if a download is cached"""
        return bool(self.get_cached_download_path(url))

    def get_download_metadata(self, url: str) -> Optional[Dict]:
        """Get metadata for a cached download from MongoDB"""
        doc = self.db.download_cache.find_one({"url": url})
        return doc.get('metadata') if doc else None

    # Transcript caching (filesystem-based)
    def cache_transcript(self, audio_path: str, transcript_path: Path) -> None:
        """Cache a transcript file"""
        cache_key = self._get_cache_key(audio_path)
        cache_path = self.transcripts_cache / f"{cache_key}.txt"
        shutil.copy2(transcript_path, cache_path)

        # Store metadata in MongoDB
        self.db.transcript_cache.update_one(
            {"audio_path": audio_path},
            {
                "$set": {
                    "audio_path": audio_path,
                    "cache_key": cache_key,
                    "cache_path": str(cache_path),
                    "original_path": str(transcript_path),
                    "cached_at": datetime.utcnow().isoformat()
                }
            },
            upsert=True
        )

    def get_cached_transcript_path(self, audio_path: str) -> Optional[Path]:
        """Get path to cached transcript if it exists"""
        cache_key = self._get_cache_key(audio_path)
        cache_path = self.transcripts_cache / f"{cache_key}.txt"
        return cache_path if cache_path.exists() else None

    def is_transcript_cached(self, audio_path: str) -> bool:
        """Check if a transcript is cached"""
        return bool(self.get_cached_transcript_path(audio_path))

    # Subscription and episode management are now handled by repositories
    # These methods are kept for backward compatibility but delegate to repositories

    def save_subscription(self, subscription: Dict):
        """Backward compatibility - saves to MongoDB via repository"""
        from src.db import SubscriptionRepository
        from src.db.models import Subscription

        repo = SubscriptionRepository(self.db)
        sub_model = Subscription(
            id=subscription['id'],
            type=subscription['type'],
            title=subscription.get('title', ''),
            feed_url=subscription.get('feed_url'),
            url=subscription.get('url')
        )
        repo.create(sub_model)

    def get_all_subscriptions(self) -> List[Dict]:
        """Backward compatibility - retrieves from MongoDB via repository"""
        from src.db import SubscriptionRepository

        repo = SubscriptionRepository(self.db)
        subscriptions = repo.find_all()
        return [sub.to_dict() for sub in subscriptions]

    def remove_subscription(self, subscription_id: str) -> bool:
        """Backward compatibility - removes from MongoDB via repository"""
        from src.db import SubscriptionRepository

        repo = SubscriptionRepository(self.db)
        return repo.delete(subscription_id)
