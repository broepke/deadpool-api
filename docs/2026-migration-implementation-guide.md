# Deadpool 2026 Migration Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing the 2026 deadpool migration using the **Active Picks Only** strategy. This approach migrates only living celebrities from 2025 to 2026, allowing players to draft new celebrities to replace those who died in 2025.

## Migration Strategy Confirmed

✅ **Active Picks Only Migration**
- Migrate only celebrities who are still alive (didn't die in 2025)
- Players start 2026 with their living picks + available draft slots
- Each player currently has 20 picks, so this will work perfectly
- Players can draft new celebrities to replace deceased ones

## Enhanced Scripts Created

### 1. Migration Script: [`utilities/migrate_2025_to_2026_enhanced.py`](utilities/migrate_2025_to_2026_enhanced.py)

**Key Features:**
- ✅ Active picks only migration strategy
- ✅ Enhanced error handling with retry logic
- ✅ Circuit breaker pattern for DynamoDB throttling
- ✅ Checkpoint-based migration with resume capability
- ✅ Parallel processing with rate limiting
- ✅ Comprehensive performance monitoring
- ✅ Draft slots tracking for each player
- ✅ Migration audit trail

**Usage:**
```bash
# Dry run to preview changes
python utilities/migrate_2025_to_2026_enhanced.py --dry-run --verbose

# Execute actual migration
python utilities/migrate_2025_to_2026_enhanced.py --verbose
```

### 2. Validation Script: [`utilities/validate_2026_migration_enhanced.py`](utilities/validate_2026_migration_enhanced.py)

**Key Features:**
- ✅ Comprehensive validation framework
- ✅ Pick count validation (active vs deceased)
- ✅ Draft slots calculation verification
- ✅ Data integrity checks
- ✅ Business rule enforcement
- ✅ Detailed reporting with JSON export

**Usage:**
```bash
# Run validation
python utilities/validate_2026_migration_enhanced.py --verbose

# Export detailed report
python utilities/validate_2026_migration_enhanced.py --verbose --export-report
```

## Implementation Steps

### Phase 1: Preparation (This Week)

#### Step 1: Test Environment Setup
```bash
# 1. Create backup of production data
aws dynamodb create-backup --table-name Deadpool --backup-name deadpool-pre-2026-migration

# 2. Set up development environment with copy of production data
# (Use your existing backup/restore procedures)
```

#### Step 2: Dry Run Testing
```bash
# Test migration script in development
python utilities/migrate_2025_to_2026_enhanced.py --dry-run --verbose --table-name Deadpool-Dev

# Review output for any issues
```

#### Step 3: Validation Testing
```bash
# Test validation script
python utilities/validate_2026_migration_enhanced.py --verbose --table-name Deadpool-Dev
```

### Phase 2: Production Migration (Next Week)

#### Step 1: Pre-Migration Backup
```bash
# Create comprehensive backup
aws dynamodb create-backup --table-name Deadpool --backup-name deadpool-2026-migration-backup
```

#### Step 2: Execute Migration
```bash
# Run production migration
python utilities/migrate_2025_to_2026_enhanced.py --verbose

# Monitor output for any errors
```

#### Step 3: Validate Migration
```bash
# Run comprehensive validation
python utilities/validate_2026_migration_enhanced.py --verbose --export-report

# Review validation report
```

#### Step 4: Update Application Configuration
```python
# Update default year in application
CURRENT_GAME_YEAR = 2026

# Clear any year-specific caches
# Update API endpoints to default to 2026
```

## Database Changes

### New Record Types Added

#### 1. Draft Slots Tracking
```python
{
    'PK': 'PLAYER#{player_id}',
    'SK': 'DRAFT_SLOTS#2026',
    'Type': 'DraftSlots',
    'Year': 2026,
    'MaxPicks': 20,
    'CurrentPicks': 17,  # Number of active picks migrated
    'AvailableSlots': 3,  # 20 - CurrentPicks
    'LastUpdated': '2026-01-01T00:00:00.000Z'
}
```

#### 2. Migration Audit Trail
```python
{
    'PK': 'MIGRATION#2025_TO_2026',
    'SK': 'METADATA',
    'Type': 'MigrationMetadata',
    'MigrationDate': '2026-01-01T00:00:00.000Z',
    'Strategy': 'ACTIVE_PICKS_ONLY',
    'PlayersProcessed': 11,
    'ActivePicksMigrated': 187,
    'DeceasedPicksSkipped': 13,
    'Status': 'COMPLETED'
}
```

## API Updates Needed

### 1. Enhanced Draft Endpoint
```python
@app.post("/draft")
async def draft_celebrity(draft_request: DraftRequest):
    # Check available draft slots before allowing draft
    draft_slots = get_draft_slots(player_id, 2026)
    if draft_slots['available_slots'] <= 0:
        raise HTTPException(400, "No available draft slots")
    
    # Execute draft and update slots
    result = execute_draft(draft_request)
    update_draft_slots(player_id, 2026, -1)
    return result
```

### 2. Draft Slots Endpoint
```python
@app.get("/players/{player_id}/draft-slots")
async def get_draft_slots(player_id: str, year: int = 2026):
    return get_draft_slots_from_db(player_id, year)
```

### 3. Enhanced Picks Endpoint
```python
@app.get("/players/{player_id}/picks")
async def get_picks(player_id: str, year: int = 2026, include_draft_slots: bool = True):
    picks = get_player_picks(player_id, year)
    response = {'picks': picks}
    
    if include_draft_slots:
        response['draft_slots'] = get_draft_slots_from_db(player_id, year)
    
    return response
```

## Expected Results

### Migration Outcome
- **Players**: All 11 players migrated successfully
- **Active Picks**: ~15-19 picks per player (celebrities still alive)
- **Draft Slots**: 1-5 available slots per player (20 - active_picks)
- **Deceased Picks**: Skipped (players can draft replacements)

### Player Experience
- Players see their living celebrities carried forward to 2026
- Players have draft slots available to replace deceased celebrities
- 2026 leaderboard starts at zero for all players
- Draft functionality works with individual slot limits

## Rollback Plan

If migration fails or has issues:

```bash
# 1. Stop application
# 2. Restore from backup
aws dynamodb restore-table-from-backup \
  --target-table-name Deadpool \
  --backup-arn arn:aws:dynamodb:region:account:table/Deadpool/backup/backup-id

# 3. Restart application
# 4. Investigate issues and retry
```

## Monitoring & Validation

### Key Metrics to Monitor
- ✅ All players have correct number of active picks
- ✅ No deceased celebrities migrated to 2026
- ✅ Draft slots calculated correctly (20 - active_picks)
- ✅ 2026 leaderboard shows zero points
- ✅ Draft functionality works with slot limits

### Success Criteria
- [ ] All active picks migrated successfully
- [ ] No data loss or corruption
- [ ] Draft slots tracking working
- [ ] Players can draft new celebrities
- [ ] API endpoints function correctly for 2026

## Communication Plan

### Pre-Migration
- Notify players about 2026 transition
- Explain that living picks carry forward
- Mention draft opportunities for deceased picks

### Post-Migration
- Confirm successful transition
- Show players their 2026 status
- Explain available draft slots

## Next Steps

1. **Immediate (This Week)**:
   - [ ] Test migration script in development environment
   - [ ] Validate script output and results
   - [ ] Schedule production migration window

2. **Migration Week**:
   - [ ] Execute production migration
   - [ ] Validate migration success
   - [ ] Update application configuration
   - [ ] Monitor system performance

3. **Post-Migration**:
   - [ ] Update API endpoints for draft slots
   - [ ] Enhance UI to show available slots
   - [ ] Monitor player engagement
   - [ ] Document lessons learned

## Support

For issues during migration:
- Check migration logs for detailed error information
- Use validation script to identify specific problems
- Refer to checkpoint files for resume capability
- Contact development team for assistance

---

**Migration Strategy**: Active Picks Only  
**Expected Duration**: 2-4 hours  
**Risk Level**: Low (with comprehensive backup and validation)  
**Player Impact**: Minimal (seamless transition with enhanced features)