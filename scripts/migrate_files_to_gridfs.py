#!/usr/bin/env python3
"""
Migration script to move existing files from filesystem to GridFS.

This script migrates:
1. Audio files from data/downloads/ -> GridFS audio_files bucket
2. Transcripts from data/transcripts/ -> GridFS transcripts bucket
3. Updates MongoDB episodes collection with new GridFS file IDs

Usage:
    python scripts/migrate_files_to_gridfs.py

Make sure MongoDB is running and you've already run migrate_to_mongodb.py first!
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import init_db, EpisodeRepository, GridFSManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_audio_files(data_dir: Path, gridfs: GridFSManager, episode_repo: EpisodeRepository):
    """Migrate audio files from filesystem to GridFS"""
    downloads_dir = data_dir / "downloads"

    if not downloads_dir.exists():
        logger.info("No downloads directory found - skipping audio migration")
        return 0

    audio_files = list(downloads_dir.glob("*"))
    audio_files = [f for f in audio_files if f.is_file() and f.suffix in ['.mp3', '.m4a', '.wav', '.ogg']]

    if not audio_files:
        logger.info("No audio files found to migrate")
        return 0

    logger.info(f"Found {len(audio_files)} audio files to migrate")

    migrated = 0
    for audio_file in audio_files:
        try:
            logger.info(f"Migrating audio file: {audio_file.name}")

            # Try to find matching episode in database by audio_path
            episode = None
            episodes = episode_repo.find_all()
            for ep in episodes:
                if ep.audio_path and Path(ep.audio_path).name == audio_file.name:
                    episode = ep
                    break

            # Store in GridFS
            if episode and episode.url:
                file_id = gridfs.store_audio(
                    file_path=audio_file,
                    url=episode.url,
                    metadata={
                        "episode_title": episode.title,
                        "migrated_from": str(audio_file),
                        "migrated_at": datetime.utcnow().isoformat()
                    }
                )
            else:
                # No matching episode found, store with minimal metadata
                file_id = gridfs.store_audio(
                    file_path=audio_file,
                    url=f"file://{audio_file}",
                    metadata={
                        "migrated_from": str(audio_file),
                        "migrated_at": datetime.utcnow().isoformat()
                    }
                )

            logger.info(f"  -> Stored in GridFS: {file_id}")

            # Update episode with new file_id
            if episode:
                episode.audio_path = file_id
                episode_repo.upsert(episode)
                logger.info(f"  -> Updated episode: {episode.title}")

            migrated += 1

        except Exception as e:
            logger.error(f"Error migrating {audio_file.name}: {e}")
            continue

    logger.info(f"Successfully migrated {migrated} audio files")
    return migrated


def migrate_transcripts(data_dir: Path, gridfs: GridFSManager, episode_repo: EpisodeRepository):
    """Migrate transcript files from filesystem to GridFS"""
    transcripts_dir = data_dir / "transcripts"

    if not transcripts_dir.exists():
        logger.info("No transcripts directory found - skipping transcript migration")
        return 0

    transcript_files = list(transcripts_dir.glob("*.txt"))

    if not transcript_files:
        logger.info("No transcript files found to migrate")
        return 0

    logger.info(f"Found {len(transcript_files)} transcript files to migrate")

    migrated = 0
    for transcript_file in transcript_files:
        try:
            logger.info(f"Migrating transcript: {transcript_file.name}")

            # Read transcript text
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_text = f.read()

            # Try to find matching episode
            episode = None
            episodes = episode_repo.find_all()
            for ep in episodes:
                if ep.transcript_path and Path(ep.transcript_path).name == transcript_file.name:
                    episode = ep
                    break

            # Store in GridFS
            if episode and episode.audio_path:
                file_id = gridfs.store_transcript(
                    transcript_text=transcript_text,
                    audio_path=episode.audio_path,
                    episode_url=episode.url,
                    metadata={
                        "episode_title": episode.title,
                        "migrated_from": str(transcript_file),
                        "migrated_at": datetime.utcnow().isoformat()
                    }
                )
            else:
                # No matching episode, store with minimal metadata
                file_id = gridfs.store_transcript(
                    transcript_text=transcript_text,
                    audio_path=transcript_file.stem,
                    episode_url=f"file://{transcript_file}",
                    metadata={
                        "migrated_from": str(transcript_file),
                        "migrated_at": datetime.utcnow().isoformat()
                    }
                )

            logger.info(f"  -> Stored in GridFS: {file_id}")

            # Update episode with new file_id and full transcript
            if episode:
                episode.transcript_path = file_id
                episode.transcript = transcript_text  # Store in episode document too
                episode_repo.upsert(episode)
                logger.info(f"  -> Updated episode: {episode.title}")

            migrated += 1

        except Exception as e:
            logger.error(f"Error migrating {transcript_file.name}: {e}")
            continue

    logger.info(f"Successfully migrated {migrated} transcript files")
    return migrated


def create_filesystem_backup(data_dir: Path):
    """Create a backup manifest of files before migration"""
    backup_file = data_dir / "filesystem_backup_manifest.json"

    manifest = {
        "created_at": datetime.utcnow().isoformat(),
        "audio_files": [],
        "transcripts": []
    }

    # List audio files
    downloads_dir = data_dir / "downloads"
    if downloads_dir.exists():
        for audio_file in downloads_dir.glob("*"):
            if audio_file.is_file():
                manifest["audio_files"].append({
                    "filename": audio_file.name,
                    "size": audio_file.stat().st_size,
                    "modified": datetime.fromtimestamp(audio_file.stat().st_mtime).isoformat()
                })

    # List transcripts
    transcripts_dir = data_dir / "transcripts"
    if transcripts_dir.exists():
        for transcript_file in transcripts_dir.glob("*.txt"):
            manifest["transcripts"].append({
                "filename": transcript_file.name,
                "size": transcript_file.stat().st_size,
                "modified": datetime.fromtimestamp(transcript_file.stat().st_mtime).isoformat()
            })

    with open(backup_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Created backup manifest: {backup_file}")
    return manifest


def main():
    """Main migration function"""
    print("=" * 60)
    print("GridFS File Migration Script for Podcast Service")
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

    # Create repositories and GridFS manager
    episode_repo = EpisodeRepository(db)
    gridfs = GridFSManager(db)

    # Create backup manifest
    print("\n[Step 1/4] Creating backup manifest...")
    manifest = create_filesystem_backup(data_dir)
    print(f"  Audio files: {len(manifest['audio_files'])}")
    print(f"  Transcripts: {len(manifest['transcripts'])}")

    # Migrate audio files
    print("\n[Step 2/4] Migrating audio files to GridFS...")
    audio_count = migrate_audio_files(data_dir, gridfs, episode_repo)

    # Migrate transcripts
    print("\n[Step 3/4] Migrating transcripts to GridFS...")
    transcript_count = migrate_transcripts(data_dir, gridfs, episode_repo)

    # Get storage stats
    print("\n[Step 4/4] Getting GridFS storage statistics...")
    stats = gridfs.get_storage_stats()

    # Summary
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"Audio files migrated:      {audio_count}")
    print(f"Transcripts migrated:      {transcript_count}")
    print()
    print("GridFS Storage:")
    print(f"  Audio files: {stats['audio_files']['count']} files, {stats['audio_files']['size'] / 1024 / 1024:.2f} MB")
    print(f"  Transcripts: {stats['transcripts']['count']} files, {stats['transcripts']['size'] / 1024 / 1024:.2f} MB")
    print()
    print("Next steps:")
    print("1. Verify your data in MongoDB and test the application")
    print("2. Test audio streaming at /api/audio/{file_id}")
    print("3. If everything works, you can delete the old files:")
    print(f"   - data/downloads/")
    print(f"   - data/transcripts/")
    print()
    print("Backup manifest saved to: data/filesystem_backup_manifest.json")
    print()


if __name__ == "__main__":
    main()
