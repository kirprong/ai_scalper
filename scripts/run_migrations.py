#!/usr/bin/env python3
"""
ClickHouse Migration Runner

This script executes SQL migration files against the ClickHouse database.
Migrations are executed in order based on their filename prefix.

Usage:
    python scripts/run_migrations.py [--host HOST] [--port PORT] [--user USER] [--password PASSWORD]
"""

import os
import sys
import glob
import logging
from pathlib import Path
from urllib.parse import quote_plus
from typing import List, Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
DEFAULT_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
DEFAULT_USER = os.getenv('CLICKHOUSE_USER', 'admin')
DEFAULT_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'admin123')
DEFAULT_DATABASE = os.getenv('CLICKHOUSE_DB', 'market_data')
MIGRATIONS_DIR = Path(__file__).parent.parent / 'db' / 'migrations'


class ClickHouseClient:
    """Simple ClickHouse HTTP client for executing queries."""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.base_url = f"http://{host}:{port}"
        self.user = user
        self.password = password
        self.database = database
    
    def execute(self, query: str) -> Optional[str]:
        """Execute a SQL query and return the result."""
        params = {
            'user': self.user,
            'password': self.password,
            'database': self.database,
        }
        
        try:
            response = requests.post(
                self.base_url,
                params=params,
                data=query,
                timeout=30
            )
            response.raise_for_status()
            return response.text.strip() if response.text else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def ping(self) -> bool:
        """Check if ClickHouse is reachable."""
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


def get_migration_files() -> List[Path]:
    """Get all migration SQL files sorted by filename."""
    migration_files = sorted(MIGRATIONS_DIR.glob('*.sql'))
    return migration_files


def run_migrations(client: ClickHouseClient, dry_run: bool = False) -> bool:
    """
    Execute all pending migrations.
    
    Args:
        client: ClickHouse client instance
        dry_run: If True, only print what would be executed
    
    Returns:
        True if all migrations succeeded, False otherwise
    """
    migration_files = get_migration_files()
    
    if not migration_files:
        logger.warning(f"No migration files found in {MIGRATIONS_DIR}")
        return True
    
    logger.info(f"Found {len(migration_files)} migration file(s)")
    
    for migration_file in migration_files:
        logger.info(f"Processing migration: {migration_file.name}")
        
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            if dry_run:
                logger.info(f"[DRY RUN] Would execute:\n{sql_content[:500]}...")
                continue
            
            # Execute the migration
            result = client.execute(sql_content)
            
            if result:
                logger.info(f"Migration result: {result}")
            
            logger.info(f"✓ Successfully executed: {migration_file.name}")
            
        except Exception as e:
            logger.error(f"✗ Failed to execute {migration_file.name}: {e}")
            return False
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run ClickHouse migrations')
    parser.add_argument('--host', default=DEFAULT_HOST, help='ClickHouse host')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='ClickHouse HTTP port')
    parser.add_argument('--user', default=DEFAULT_USER, help='ClickHouse user')
    parser.add_argument('--password', default=DEFAULT_PASSWORD, help='ClickHouse password')
    parser.add_argument('--database', default=DEFAULT_DATABASE, help='Database name')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed')
    args = parser.parse_args()
    
    logger.info(f"Connecting to ClickHouse at {args.host}:{args.port}")
    
    client = ClickHouseClient(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    # Check connection
    if not client.ping():
        logger.error("Cannot connect to ClickHouse. Is it running?")
        logger.info("Start ClickHouse with: docker-compose up -d")
        sys.exit(1)
    
    logger.info("✓ Connected to ClickHouse")
    
    # Run migrations
    success = run_migrations(client, dry_run=args.dry_run)
    
    if success:
        logger.info("✓ All migrations completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Migration failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
