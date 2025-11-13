#!/usr/bin/env python3
"""
Migration script to move existing JSON data to MongoDB.

This script migrates:
1. Episode history from data/history.json -> MongoDB episodes collection
2. Subscriptions from data/cache/subscriptions.json -> MongoDB subscriptions collection
3. Settings from data/settings.json -> MongoDB settings collection

Usage:
    python scripts/migrate_to_mongodb.py

Make sure MongoDB is running and configured in your .env file before running this script.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db, EpisodeRepository, SubscriptionRepository, SettingsRepository
from src.db.models import Episode, Subscription, Settings, Summary
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_history(data_dir: Path, episode_repo: EpisodeRepository):
    """Migrate episode history from JSON to MongoDB"""
    history_file = data_dir / "history.json"

    if not history_file.exists():
        logger.info("No history.json found - skipping history migration")
        return 0

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

        logger.info(f"Found {len(history)} episodes to migrate")

        migrated = 0
        for entry in history:
            try:
                # Convert summary dict to Summary model
                summary_data = entry.get('summary')
                summary = Summary.from_dict(summary_data) if summary_data else None

                # Create Episode model
                episode = Episode(
                    url=entry['url'],
                    title=entry['title'],
                    file_hash=entry['file_hash'],
                    audio_path=entry['audio_path'],
                    transcript_path=entry.get('transcript_path'),
                    summary_path=entry.get('summary_path'),
                    processed_at=entry.get('processed_at', datetime.utcnow().isoformat()),
                    duration=entry.get('duration', 0),
                    has_summary=entry.get('has_summary', False),
                    summary=summary,
                    subscription_id=entry.get('subscription_id'),
                    subscription_type=entry.get('subscription_type'),
                    metadata=entry.get('metadata', {}),
                    id=entry.get('id')
                )

                # Upsert to MongoDB
                episode_repo.upsert(episode)
                migrated += 1
                logger.info(f"Migrated episode: {episode.title}")

            except Exception as e:
                logger.error(f"Error migrating episode {entry.get('title', 'Unknown')}: {e}")
                continue

        logger.info(f"Successfully migrated {migrated} episodes")
        return migrated

    except Exception as e:
        logger.error(f"Error reading history file: {e}")
        return 0


def migrate_subscriptions(data_dir: Path, subscription_repo: SubscriptionRepository):
    """Migrate subscriptions from JSON to MongoDB"""
    subscriptions_file = data_dir / "cache" / "subscriptions.json"

    if not subscriptions_file.exists():
        logger.info("No subscriptions.json found - skipping subscription migration")
        return 0

    try:
        with open(subscriptions_file, 'r', encoding='utf-8') as f:
            subscriptions = json.load(f)

        logger.info(f"Found {len(subscriptions)} subscriptions to migrate")

        migrated = 0
        for sub_data in subscriptions:
            try:
                # Create Subscription model
                subscription = Subscription(
                    id=sub_data['id'],
                    type=sub_data['type'],
                    title=sub_data.get('title', ''),
                    feed_url=sub_data.get('feed_url'),
                    url=sub_data.get('url'),
                    created_at=sub_data.get('created_at', datetime.utcnow().isoformat()),
                    metadata=sub_data.get('metadata', {})
                )

                # Create (skip if already exists)
                subscription_repo.create(subscription)
                migrated += 1
                logger.info(f"Migrated subscription: {subscription.title}")

            except Exception as e:
                logger.warning(f"Subscription {sub_data.get('id')} may already exist or error occurred: {e}")
                continue

        logger.info(f"Successfully migrated {migrated} subscriptions")
        return migrated

    except Exception as e:
        logger.error(f"Error reading subscriptions file: {e}")
        return 0


def migrate_settings(data_dir: Path, settings_repo: SettingsRepository):
    """Migrate settings from JSON to MongoDB"""
    settings_file = data_dir / "settings.json"

    if not settings_file.exists():
        logger.info("No settings.json found - using default settings")
        return False

    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)

        # Create Settings model
        settings = Settings(
            default_model=settings_data.get('default_model', 'base'),
            output_format=settings_data.get('output_format', 'txt'),
            auto_summarize=settings_data.get('auto_summarize', True),
            additional_settings=settings_data
        )

        # Update MongoDB
        settings_repo.update(settings)
        logger.info("Successfully migrated settings")
        return True

    except Exception as e:
        logger.error(f"Error reading settings file: {e}")
        return False


def backup_json_files(data_dir: Path):
    """Create backups of JSON files before migration"""
    backup_dir = data_dir / "backup_pre_mongodb"
    backup_dir.mkdir(exist_ok=True)

    files_to_backup = [
        data_dir / "history.json",
        data_dir / "settings.json",
        data_dir / "cache" / "subscriptions.json",
        data_dir / "cache" / "episodes.json"
    ]

    backed_up = 0
    for file_path in files_to_backup:
        if file_path.exists():
            backup_path = backup_dir / file_path.name
            import shutil
            shutil.copy2(file_path, backup_path)
            logger.info(f"Backed up {file_path.name}")
            backed_up += 1

    logger.info(f"Backed up {backed_up} files to {backup_dir}")
    return backup_dir


def main():
    """Main migration function"""
    print("=" * 60)
    print("MongoDB Migration Script for Podcast Service")
    print("=" * 60)
    print()

    # Get data directory
    data_dir = Path("data")
    if not data_dir.exists():
        logger.warning("No data directory found - nothing to migrate")
        return

    # Initialize MongoDB
    try:
        logger.info("Connecting to MongoDB...")
        db = init_db()
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        logger.error("Make sure MongoDB is running and configured in your .env file")
        return

    # Create repositories
    episode_repo = EpisodeRepository(db)
    subscription_repo = SubscriptionRepository(db)
    settings_repo = SettingsRepository(db)

    # Backup JSON files first
    print("\n[Step 1/4] Creating backups...")
    backup_dir = backup_json_files(data_dir)

    # Migrate data
    print("\n[Step 2/4] Migrating settings...")
    migrate_settings(data_dir, settings_repo)

    print("\n[Step 3/4] Migrating subscriptions...")
    sub_count = migrate_subscriptions(data_dir, subscription_repo)

    print("\n[Step 4/4] Migrating episode history...")
    episode_count = migrate_history(data_dir, episode_repo)

    # Summary
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"Episodes migrated:      {episode_count}")
    print(f"Subscriptions migrated: {sub_count}")
    print(f"Backups saved to:       {backup_dir}")
    print()
    print("Next steps:")
    print("1. Verify your data in MongoDB")
    print("2. Test the application")
    print("3. If everything works, you can delete the JSON files")
    print()


if __name__ == "__main__":
    main()
