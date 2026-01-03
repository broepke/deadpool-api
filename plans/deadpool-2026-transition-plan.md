# Deadpool Game 2026 Transition Plan

## Executive Summary

This document outlines the comprehensive plan to transition the Deadpool game from 2025 to 2026, preserving all current player picks while resetting point totals for the new year. The transition will maintain game continuity while establishing a fresh scoring period for 2026.

## Current Game State Analysis

### Game Mechanics
- **Scoring Formula**: `50 + (100 - Age)` points for each celebrity that dies in the target year
- **Player Structure**: 11 active players with established profiles and draft orders
- **Pick System**: Players draft celebrities they believe will die in the target year
- **Year-Based Scoring**: Points only count when celebrities die in the same year as the game

### Current 2025 Data
- **Players**: 11 active players with complete profiles
- **Draft Order**: Established for 2025 (players 1-11)
- **Picks**: Extensive pick data showing players have made their 2025 selections
- **Celebrity Database**: 323+ celebrities with birth dates, death dates, and metadata
- **Deaths in 2025**: Several celebrities have already died in 2025, generating points

### Database Structure
- **DynamoDB Single Table Design** with composite keys (PK/SK)
- **Player Records**: `PLAYER#{player_id}` / `DETAILS`
- **Draft Orders**: `YEAR#{year}` / `ORDER#{draft_order}#PLAYER#{player_id}`
- **Player Picks**: `PLAYER#{player_id}` / `PICK#{year}#{person_id}`
- **People Records**: `PERSON#{person_id}` / `DETAILS`

## 2026 Transition Strategy

### Core Principle
**"Continuation with Reset"** - All 2025 picks become 2026 picks, but scoring resets to zero for the new year.

### Key Requirements
1. **Preserve Player Picks**: All 2025 celebrity selections carry forward to 2026
2. **Reset Scoring**: Point totals reset to zero for 2026 calculations
3. **Maintain Player Profiles**: All player information and preferences preserved
4. **Establish 2026 Draft Order**: Create new draft order for 2026
5. **Update System Logic**: Ensure scoring calculations work for 2026

## Detailed Migration Plan

### Phase 1: Data Preparation and Validation

#### 1.1 Current State Audit
- [ ] Query all 2025 player picks to get complete inventory
- [ ] Validate all player profiles are complete and active
- [ ] Confirm celebrity database is up-to-date with 2025 deaths
- [ ] Document current 2025 leaderboard for historical records

#### 1.2 Data Integrity Checks
- [ ] Verify all pick relationships (player → celebrity) are valid
- [ ] Ensure no orphaned records exist
- [ ] Validate celebrity metadata (ages, death dates) is accurate
- [ ] Check for any duplicate picks within 2025

### Phase 2: 2026 Draft Order Setup

#### 2.1 Draft Order Strategy
**Recommended Approach**: Reverse order of 2025 final standings
- Lowest scoring player gets #1 pick in 2026
- Highest scoring player gets #11 pick in 2026
- Provides competitive balance for the new year

#### 2.2 Implementation
- [ ] Calculate final 2025 leaderboard standings
- [ ] Create reverse-order draft sequence for 2026
- [ ] Insert new draft order records: `YEAR#2026` / `ORDER#{position}#PLAYER#{player_id}`

### Phase 3: Pick Migration

#### 3.1 Pick Duplication Strategy
For each 2025 pick, create corresponding 2026 pick:
- **Source**: `PLAYER#{player_id}` / `PICK#2025#{person_id}`
- **Target**: `PLAYER#{player_id}` / `PICK#2026#{person_id}`
- **Timestamp**: Set to 2026-01-01 00:00:00 (or migration date)

#### 3.2 Migration Process
- [ ] Extract all 2025 picks from DynamoDB
- [ ] Transform data structure for 2026 (update year and timestamp)
- [ ] Batch insert 2026 pick records
- [ ] Validate migration completeness

### Phase 4: System Updates

#### 4.1 Application Logic Updates
- [ ] Update default year logic to use 2026
- [ ] Ensure leaderboard calculations work for 2026
- [ ] Verify pick counting and validation for 2026
- [ ] Test draft functionality for 2026

#### 4.2 Cache Invalidation
- [ ] Clear all cached leaderboard data
- [ ] Reset pick count caches
- [ ] Invalidate next drafter calculations
- [ ] Clear any year-specific cached data

### Phase 5: Testing and Validation

#### 5.1 Data Validation
- [ ] Verify all players have identical pick counts between 2025 and 2026
- [ ] Confirm 2026 leaderboard starts at zero for all players
- [ ] Test pick retrieval and display for 2026
- [ ] Validate draft order functionality

#### 5.2 API Testing
- [ ] Test `/leaderboard?year=2026` endpoint
- [ ] Test `/picks?year=2026` endpoint
- [ ] Test `/draft-next` for 2026 functionality
- [ ] Verify search and reporting work for 2026

## Implementation Scripts

### Script 1: Data Migration Script
```python
# utilities/migrate_2025_to_2026.py
import boto3
from datetime import datetime
import json

def migrate_picks_to_2026():
    """
    Migrate all 2025 picks to 2026 with reset timestamps
    """
    # Implementation details in separate script file
    pass

def create_2026_draft_order():
    """
    Create 2026 draft order based on reverse 2025 standings
    """
    # Implementation details in separate script file
    pass
```

### Script 2: Validation Script
```python
# utilities/validate_2026_migration.py
def validate_migration():
    """
    Comprehensive validation of 2026 migration
    """
    # Implementation details in separate script file
    pass
```

## Migration Timeline

### Pre-Migration (Planning Phase)
- **Week 1**: Finalize migration plan and scripts
- **Week 2**: Develop and test migration scripts in development
- **Week 3**: Prepare production migration procedures

### Migration Execution
- **Day 1**: Backup current production data
- **Day 1**: Execute migration scripts
- **Day 1**: Validate migration success
- **Day 2**: Monitor system performance and user feedback

### Post-Migration
- **Week 1**: Monitor system stability and performance
- **Week 2**: Address any issues or edge cases discovered
- **Ongoing**: Regular monitoring of 2026 game progression

## Risk Assessment and Mitigation

### High Risk Items
1. **Data Loss During Migration**
   - *Mitigation*: Complete database backup before migration
   - *Rollback Plan*: Restore from backup if migration fails

2. **Pick Count Mismatches**
   - *Mitigation*: Comprehensive validation scripts
   - *Detection*: Automated pick count comparisons

3. **Application Logic Errors**
   - *Mitigation*: Thorough testing in development environment
   - *Monitoring*: Real-time error tracking post-migration

### Medium Risk Items
1. **Performance Impact**
   - *Mitigation*: Batch operations and optimized queries
   - *Monitoring*: Performance metrics during migration

2. **Cache Inconsistencies**
   - *Mitigation*: Complete cache invalidation post-migration
   - *Verification*: Manual cache verification procedures

## Success Criteria

### Technical Success
- [ ] All 2025 picks successfully migrated to 2026
- [ ] 2026 leaderboard shows zero points for all players
- [ ] All API endpoints function correctly for 2026
- [ ] No data loss or corruption detected

### Functional Success
- [ ] Players can view their 2026 picks (same as 2025)
- [ ] Draft functionality works for 2026
- [ ] Scoring calculations work correctly for 2026 deaths
- [ ] Reporting and analytics function for 2026

### User Experience Success
- [ ] Seamless transition for players
- [ ] Clear communication about the transition
- [ ] No disruption to ongoing game experience

## Communication Plan

### Pre-Migration Communication
- Notify players about upcoming 2026 transition
- Explain that picks will carry forward but scores reset
- Provide timeline for transition

### During Migration
- Status updates on migration progress
- Estimated completion times
- Any temporary service interruptions

### Post-Migration
- Confirmation of successful transition
- Instructions for viewing 2026 game state
- Support contact information for issues

## Monitoring and Support

### Key Metrics to Monitor
- Pick count accuracy (2025 vs 2026)
- API response times and error rates
- Database performance metrics
- User engagement and activity levels

### Support Procedures
- Dedicated support channel for migration issues
- Escalation procedures for critical problems
- Documentation for common post-migration questions

## Future Considerations

### Annual Transition Process
This migration establishes a template for future year transitions:
- Standardized migration scripts
- Automated validation procedures
- Documented rollback procedures
- Performance optimization lessons learned

### System Improvements
- Consider automated year rollover functionality
- Implement better caching strategies for multi-year data
- Enhance monitoring and alerting for migrations

## Conclusion

This comprehensive plan ensures a smooth transition from 2025 to 2026 while preserving game continuity and player investment. The migration maintains all player picks while establishing a fresh competitive environment for 2026.

The success of this transition will depend on careful execution of the migration scripts, thorough testing, and proactive monitoring of the system post-migration.