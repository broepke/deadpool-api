#!/usr/bin/env python3
"""
Enhanced Deadpool Game 2025 to 2026 Migration Script

This script migrates ACTIVE PICKS ONLY from 2025 to 2026, preserving only
celebrities who are still alive (did not die in 2025). This allows players
to draft new celebrities to replace those who died in 2025.

Usage:
    python utilities/migrate_2025_to_2026_enhanced.py [--dry-run] [--verbose]

Options:
    --dry-run    Show what would be done without making changes
    --verbose    Show detailed progress information
"""

import boto3
import json
import argparse
import sys
import time
import random
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore
import os


class CircuitBreaker:
    """Circuit breaker pattern for handling DynamoDB throttling"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, operation):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN - too many failures")
        
        try:
            result = operation()
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            raise


class CheckpointManager:
    """Manages migration checkpoints for resume capability"""
    
    def __init__(self, checkpoint_file: str = 'migration_checkpoint.json'):
        self.checkpoint_file = checkpoint_file
    
    def save_checkpoint(self, completed_players: List[str], failed_players: List[str], stats: Dict):
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'completed_players': completed_players,
            'failed_players': failed_players,
            'stats': stats
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def load_checkpoint(self) -> Optional[Dict]:
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return None
    
    def clear_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)


class PerformanceMonitor:
    """Monitors migration performance and provides metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.player_times = []
        self.error_count = 0
        self.throttle_count = 0
    
    def record_player_migration(self, duration: float, pick_count: int, success: bool):
        self.player_times.append(duration)
        if not success:
            self.error_count += 1
    
    def record_throttle_event(self):
        self.throttle_count += 1
    
    def get_performance_report(self) -> Dict:
        elapsed = time.time() - self.start_time
        avg_time = sum(self.player_times) / len(self.player_times) if self.player_times else 0
        
        return {
            'total_duration': elapsed,
            'players_processed': len(self.player_times),
            'avg_time_per_player': avg_time,
            'error_rate': self.error_count / len(self.player_times) if self.player_times else 0,
            'throttle_events': self.throttle_count,
            'players_per_minute': len(self.player_times) / (elapsed / 60) if elapsed > 0 else 0
        }


class EnhancedDeadpoolMigration:
    def __init__(self, table_name: str = "Deadpool", dry_run: bool = False, verbose: bool = False):
        self.table_name = table_name
        self.dry_run = dry_run
        self.verbose = verbose
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
        # Migration components
        self.circuit_breaker = CircuitBreaker()
        self.checkpoint_manager = CheckpointManager()
        self.performance_monitor = PerformanceMonitor()
        self.rate_limiter = Semaphore(5)  # Max 5 concurrent operations
        
        # Migration timestamp
        self.migration_timestamp = "2026-01-01T00:00:00.000Z"
        
        # Statistics
        self.stats = {
            'players_processed': 0,
            'active_picks_migrated': 0,
            'deceased_picks_skipped': 0,
            'draft_orders_created': 0,
            'errors': [],
            'completed_players': [],
            'failed_players': []
        }

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        
        if level == "ERROR":
            print(f"{prefix} {message}", file=sys.stderr)
        elif self.verbose or level in ["ERROR", "WARN"]:
            print(f"{prefix} {message}")

    def retry_with_backoff(self, operation, max_retries: int = 3):
        """Execute operation with exponential backoff retry"""
        for attempt in range(max_retries):
            try:
                return operation()
            except ClientError as e:
                if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                    self.performance_monitor.record_throttle_event()
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    self.log(f"Throttled, waiting {wait_time:.2f}s before retry {attempt + 1}")
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                self.log(f"Attempt {attempt + 1} failed: {str(e)}, retrying...")
                time.sleep(1)

    def get_2025_leaderboard(self) -> List[Dict[str, Any]]:
        """Get final 2025 leaderboard to determine 2026 draft order"""
        self.log("Calculating 2025 final leaderboard...")
        
        try:
            players = self.get_all_players()
            leaderboard = []
            
            for player in players:
                player_id = player['id']
                picks = self.get_player_picks(player_id, 2025)
                
                # Calculate 2025 score
                total_score = 0
                for pick in picks:
                    person = self.get_person(pick['person_id'])
                    if person and person.get('death_date'):
                        # Check if death was in 2025
                        death_year = int(person['death_date'][:4])
                        if death_year == 2025:
                            age = person.get('age', 0)
                            score = 50 + (100 - age)
                            total_score += score
                
                leaderboard.append({
                    'player_id': player_id,
                    'player_name': player['name'],
                    'score': total_score,
                    'pick_count': len(picks)
                })
            
            # Sort by score (highest first)
            leaderboard.sort(key=lambda x: x['score'], reverse=True)
            
            self.log(f"2025 Final Leaderboard:")
            for i, entry in enumerate(leaderboard, 1):
                self.log(f"  {i}. {entry['player_name']}: {entry['score']} points ({entry['pick_count']} picks)")
            
            return leaderboard
            
        except Exception as e:
            self.log(f"Error calculating 2025 leaderboard: {str(e)}", "ERROR")
            raise

    def get_all_players(self) -> List[Dict[str, Any]]:
        """Get all active players"""
        def _get_players():
            response = self.table.scan(
                FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
                ExpressionAttributeValues={
                    ':pk_prefix': 'PLAYER#',
                    ':sk': 'DETAILS'
                }
            )
            return response
        
        try:
            response = self.retry_with_backoff(_get_players)
            
            players = []
            for item in response['Items']:
                player_id = item['PK'].replace('PLAYER#', '')
                players.append({
                    'id': player_id,
                    'name': f"{item.get('FirstName', '')} {item.get('LastName', '')}".strip(),
                    'first_name': item.get('FirstName', ''),
                    'last_name': item.get('LastName', ''),
                    'phone_verified': item.get('PhoneVerified', False),
                    'sms_notifications_enabled': item.get('SmsNotificationsEnabled', False)
                })
            
            self.log(f"Found {len(players)} active players")
            return players
            
        except Exception as e:
            self.log(f"Error getting players: {str(e)}", "ERROR")
            raise

    def get_player_picks(self, player_id: str, year: int) -> List[Dict[str, Any]]:
        """Get all picks for a player in a specific year"""
        def _get_picks():
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ':pk': f'PLAYER#{player_id}',
                    ':sk_prefix': f'PICK#{year}#'
                }
            )
            return response
        
        try:
            response = self.retry_with_backoff(_get_picks)
            
            picks = []
            for item in response['Items']:
                # Extract person_id from SK: PICK#2025#person_id
                person_id = item['SK'].split('#')[2]
                picks.append({
                    'person_id': person_id,
                    'year': item.get('Year', year),
                    'timestamp': item.get('Timestamp', '')
                })
            
            return picks
            
        except Exception as e:
            self.log(f"Error getting picks for player {player_id}: {str(e)}", "ERROR")
            return []

    def get_person(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Get person details"""
        def _get_person():
            response = self.table.get_item(
                Key={
                    'PK': f'PERSON#{person_id}',
                    'SK': 'DETAILS'
                }
            )
            return response
        
        try:
            response = self.retry_with_backoff(_get_person)
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'id': person_id,
                    'name': item.get('Name', ''),
                    'death_date': item.get('DeathDate'),
                    'age': item.get('Age', 0)
                }
            return None
            
        except Exception as e:
            self.log(f"Error getting person {person_id}: {str(e)}", "ERROR")
            return None

    def is_celebrity_active_for_2026(self, person_id: str) -> Tuple[bool, Optional[str]]:
        """Check if celebrity should be migrated to 2026 (still alive or didn't die in 2025)"""
        person = self.get_person(person_id)
        if not person:
            return False, "Person not found"
        
        death_date = person.get('death_date')
        if not death_date:
            return True, "Still alive"
        
        # Check if death was in 2025
        if death_date.startswith('2025'):
            return False, f"Died in 2025 ({death_date})"
        
        return True, f"Died in different year ({death_date})"

    def get_active_picks_2025(self, player_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Get active and deceased picks for a player from 2025"""
        picks_2025 = self.get_player_picks(player_id, 2025)
        active_picks = []
        deceased_picks = []
        
        for pick in picks_2025:
            is_active, reason = self.is_celebrity_active_for_2026(pick['person_id'])
            if is_active:
                active_picks.append(pick)
            else:
                deceased_picks.append({**pick, 'skip_reason': reason})
        
        return active_picks, deceased_picks

    def create_2026_draft_order(self, leaderboard: List[Dict[str, Any]]) -> bool:
        """Create 2026 draft order based on reverse 2025 standings"""
        self.log("Creating 2026 draft order...")
        
        try:
            # Reverse the leaderboard (worst performing player gets first pick)
            reversed_leaderboard = list(reversed(leaderboard))
            
            draft_order_items = []
            for position, entry in enumerate(reversed_leaderboard, 1):
                player_id = entry['player_id']
                
                item = {
                    'PK': 'YEAR#2026',
                    'SK': f'ORDER#{position:02d}#PLAYER#{player_id}',
                    'Type': 'DraftOrder',
                    'Year': 2026,
                    'DraftOrder': position,
                    'PlayerID': player_id
                }
                
                draft_order_items.append(item)
                self.log(f"  Draft position {position}: {entry['player_name']} (2025 score: {entry['score']})")
            
            if not self.dry_run:
                def _batch_write():
                    with self.table.batch_writer() as batch:
                        for item in draft_order_items:
                            batch.put_item(Item=item)
                
                self.retry_with_backoff(_batch_write)
                self.stats['draft_orders_created'] = len(draft_order_items)
                self.log(f"Successfully created 2026 draft order for {len(draft_order_items)} players")
            else:
                self.log(f"DRY RUN: Would create 2026 draft order for {len(draft_order_items)} players")
            
            return True
            
        except Exception as e:
            self.log(f"Error creating 2026 draft order: {str(e)}", "ERROR")
            self.stats['errors'].append(f"Draft order creation: {str(e)}")
            return False

    def migrate_player_picks(self, player_id: str, player_name: str) -> bool:
        """Migrate active 2025 picks for a player to 2026"""
        start_time = time.time()
        
        try:
            self.log(f"Migrating picks for {player_name} ({player_id})...")
            
            # Get active and deceased picks
            active_picks, deceased_picks = self.get_active_picks_2025(player_id)
            
            self.log(f"  Active picks to migrate: {len(active_picks)}")
            self.log(f"  Deceased picks to skip: {len(deceased_picks)}")
            
            if deceased_picks:
                for deceased in deceased_picks:
                    person = self.get_person(deceased['person_id'])
                    person_name = person['name'] if person else deceased['person_id']
                    self.log(f"    Skipping {person_name}: {deceased['skip_reason']}")
            
            # Create 2026 picks for active celebrities only
            pick_items = []
            for pick in active_picks:
                item = {
                    'PK': f'PLAYER#{player_id}',
                    'SK': f'PICK#2026#{pick["person_id"]}',
                    'Year': 2026,
                    'PersonID': pick['person_id'],
                    'Timestamp': self.migration_timestamp
                }
                pick_items.append(item)
            
            # Create draft slots tracking item
            available_slots = 20 - len(active_picks)
            draft_slots_item = {
                'PK': f'PLAYER#{player_id}',
                'SK': 'DRAFT_SLOTS#2026',
                'Type': 'DraftSlots',
                'Year': 2026,
                'MaxPicks': 20,
                'CurrentPicks': len(active_picks),
                'AvailableSlots': available_slots,
                'LastUpdated': self.migration_timestamp
            }
            
            if not self.dry_run:
                def _batch_write():
                    with self.table.batch_writer() as batch:
                        for item in pick_items:
                            batch.put_item(Item=item)
                        batch.put_item(Item=draft_slots_item)
                
                self.retry_with_backoff(_batch_write)
                
                self.stats['active_picks_migrated'] += len(active_picks)
                self.stats['deceased_picks_skipped'] += len(deceased_picks)
                self.log(f"  Successfully migrated {len(active_picks)} active picks for {player_name}")
                self.log(f"  Available draft slots: {available_slots}")
            else:
                self.log(f"  DRY RUN: Would migrate {len(active_picks)} active picks for {player_name}")
                self.log(f"  DRY RUN: Would create draft slots record (available: {available_slots})")
            
            duration = time.time() - start_time
            self.performance_monitor.record_player_migration(duration, len(active_picks), True)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.performance_monitor.record_player_migration(duration, 0, False)
            self.log(f"Error migrating picks for {player_name}: {str(e)}", "ERROR")
            self.stats['errors'].append(f"Player {player_name}: {str(e)}")
            return False

    def migrate_player_with_rate_limit(self, player: Dict[str, Any]) -> bool:
        """Migrate a player with rate limiting"""
        with self.rate_limiter:
            return self.migrate_player_picks(player['id'], player['name'])

    def validate_migration(self) -> bool:
        """Validate that migration was successful"""
        self.log("Validating migration...")
        
        try:
            players = self.get_all_players()
            validation_errors = []
            
            for player in players:
                player_id = player['id']
                player_name = player['name']
                
                # Get original and migrated picks
                picks_2025 = self.get_player_picks(player_id, 2025)
                picks_2026 = self.get_player_picks(player_id, 2026)
                
                # Get active picks count
                active_picks, deceased_picks = self.get_active_picks_2025(player_id)
                expected_2026_count = len(active_picks)
                
                if len(picks_2026) != expected_2026_count:
                    error = f"{player_name}: Expected {expected_2026_count} picks, got {len(picks_2026)}"
                    validation_errors.append(error)
                    self.log(f"  VALIDATION ERROR: {error}", "ERROR")
                else:
                    self.log(f"  ✓ {player_name}: {len(picks_2026)} active picks migrated correctly")
                    if deceased_picks:
                        self.log(f"    {len(deceased_picks)} deceased picks correctly skipped")
            
            # Validate no deceased celebrities were migrated
            for player in players:
                picks_2026 = self.get_player_picks(player['id'], 2026)
                for pick in picks_2026:
                    is_active, reason = self.is_celebrity_active_for_2026(pick['person_id'])
                    if not is_active:
                        error = f"Deceased celebrity {pick['person_id']} was migrated to 2026"
                        validation_errors.append(error)
                        self.log(f"  VALIDATION ERROR: {error}", "ERROR")
            
            if validation_errors:
                self.log(f"Validation failed with {len(validation_errors)} errors", "ERROR")
                return False
            else:
                self.log("✓ Migration validation successful")
                return True
                
        except Exception as e:
            self.log(f"Error during validation: {str(e)}", "ERROR")
            return False

    def run_migration(self) -> bool:
        """Execute the complete migration process"""
        self.log("Starting Enhanced Deadpool 2025 to 2026 Migration (Active Picks Only)...")
        
        if self.dry_run:
            self.log("*** DRY RUN MODE - No changes will be made ***")
        
        try:
            # Check for existing checkpoint
            checkpoint = self.checkpoint_manager.load_checkpoint()
            if checkpoint and not self.dry_run:
                self.log("Found existing checkpoint - resuming migration...")
                completed_players = set(checkpoint['completed_players'])
                self.stats.update(checkpoint['stats'])
            else:
                completed_players = set()
            
            # Step 1: Get 2025 leaderboard for draft order
            leaderboard = self.get_2025_leaderboard()
            
            # Step 2: Create 2026 draft order
            if not self.create_2026_draft_order(leaderboard):
                return False
            
            # Step 3: Migrate picks for each player
            players = self.get_all_players()
            remaining_players = [p for p in players if p['id'] not in completed_players]
            
            self.log(f"Migrating {len(remaining_players)} players...")
            
            # Use parallel processing for better performance
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_player = {
                    executor.submit(self.migrate_player_with_rate_limit, player): player 
                    for player in remaining_players
                }
                
                for future in as_completed(future_to_player):
                    player = future_to_player[future]
                    try:
                        success = future.result()
                        if success:
                            self.stats['players_processed'] += 1
                            self.stats['completed_players'].append(player['id'])
                        else:
                            self.stats['failed_players'].append(player['id'])
                        
                        # Save checkpoint every 3 players
                        if len(self.stats['completed_players']) % 3 == 0 and not self.dry_run:
                            self.checkpoint_manager.save_checkpoint(
                                self.stats['completed_players'],
                                self.stats['failed_players'],
                                self.stats
                            )
                            
                    except Exception as e:
                        self.log(f"Failed to migrate {player['name']}: {str(e)}", "ERROR")
                        self.stats['failed_players'].append(player['id'])
            
            # Step 4: Validate migration (only if not dry run)
            if not self.dry_run:
                if not self.validate_migration():
                    return False
            
            # Step 5: Create migration metadata record
            if not self.dry_run:
                self.create_migration_metadata()
            
            # Print final statistics
            self.print_migration_summary()
            
            # Clear checkpoint on successful completion
            if not self.dry_run and len(self.stats['errors']) == 0:
                self.checkpoint_manager.clear_checkpoint()
            
            return len(self.stats['errors']) == 0
            
        except Exception as e:
            self.log(f"Migration failed: {str(e)}", "ERROR")
            return False

    def create_migration_metadata(self):
        """Create migration metadata record for audit trail"""
        try:
            metadata_item = {
                'PK': 'MIGRATION#2025_TO_2026',
                'SK': 'METADATA',
                'Type': 'MigrationMetadata',
                'MigrationDate': self.migration_timestamp,
                'Strategy': 'ACTIVE_PICKS_ONLY',
                'PlayersProcessed': self.stats['players_processed'],
                'ActivePicksMigrated': self.stats['active_picks_migrated'],
                'DeceasedPicksSkipped': self.stats['deceased_picks_skipped'],
                'DraftOrdersCreated': self.stats['draft_orders_created'],
                'Status': 'COMPLETED' if len(self.stats['errors']) == 0 else 'COMPLETED_WITH_ERRORS',
                'ErrorCount': len(self.stats['errors']),
                'PerformanceMetrics': self.performance_monitor.get_performance_report()
            }
            
            def _put_metadata():
                self.table.put_item(Item=metadata_item)
            
            self.retry_with_backoff(_put_metadata)
            self.log("Migration metadata record created")
            
        except Exception as e:
            self.log(f"Error creating migration metadata: {str(e)}", "ERROR")

    def print_migration_summary(self):
        """Print migration statistics"""
        performance = self.performance_monitor.get_performance_report()
        
        self.log("=" * 60)
        self.log("ENHANCED MIGRATION SUMMARY")
        self.log("=" * 60)
        self.log(f"Strategy: Active Picks Only")
        self.log(f"Players processed: {self.stats['players_processed']}")
        self.log(f"Active picks migrated: {self.stats['active_picks_migrated']}")
        self.log(f"Deceased picks skipped: {self.stats['deceased_picks_skipped']}")
        self.log(f"Draft orders created: {self.stats['draft_orders_created']}")
        self.log(f"Errors: {len(self.stats['errors'])}")
        
        self.log("\nPERFORMANCE METRICS:")
        self.log(f"Total duration: {performance['total_duration']:.2f} seconds")
        self.log(f"Average time per player: {performance['avg_time_per_player']:.2f} seconds")
        self.log(f"Players per minute: {performance['players_per_minute']:.1f}")
        self.log(f"Throttle events: {performance['throttle_events']}")
        self.log(f"Error rate: {performance['error_rate']:.1%}")
        
        if self.stats['errors']:
            self.log("\nERRORS:")
            for error in self.stats['errors']:
                self.log(f"  - {error}")
        
        if self.dry_run:
            self.log("\n*** This was a DRY RUN - no changes were made ***")
        else:
            status = "successfully" if len(self.stats['errors']) == 0 else "with errors"
            self.log(f"\n✓ Migration completed {status}")


def main():
    parser = argparse.ArgumentParser(description='Enhanced Deadpool 2025 to 2026 Migration (Active Picks Only)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed progress information')
    parser.add_argument('--table-name', default='Deadpool',
                       help='DynamoDB table name (default: Deadpool)')
    
    args = parser.parse_args()
    
    # Create migration instance
    migration = EnhancedDeadpoolMigration(
        table_name=args.table_name,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    # Run migration
    success = migration.run_migration()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()