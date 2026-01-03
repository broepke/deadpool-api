# Deadpool 2026 Migration - Active Picks Analysis

## Critical Clarification: Active vs. All Picks

Based on your feedback, I need to clarify an important distinction in the migration strategy:

### Current Migration Plan (All Picks)
The current migration scripts copy **ALL** 2025 picks to 2026, including:
- Active picks (celebrities still alive)
- Deceased picks (celebrities who died in 2025)

### Recommended Migration Plan (Active Picks Only)
Based on your clarification, we should only migrate **ACTIVE** picks to 2026:
- ✅ Active picks (celebrities still alive) → Carry forward to 2026
- ❌ Deceased picks (celebrities who died in 2025) → Do NOT carry forward

## Rationale for Active-Only Migration

### Game Logic Benefits
1. **Fresh Opportunities**: Players can draft new celebrities to replace those who died in 2025
2. **Strategic Depth**: Players must make new choices for deceased slots
3. **Competitive Balance**: No "dead weight" picks carried forward
4. **Draft Activity**: Ensures continued drafting activity in 2026

### Player Fairness
- Players with fewer active picks get more draft opportunities in 2026
- Example: Player with 19 active picks gets 1 additional draft slot
- Players with 20 active picks maintain full roster

## Updated Migration Strategy

### Modified Process
1. **Identify Active Picks**: Query 2025 picks where celebrity has no death date OR death date is not in 2025
2. **Migrate Active Only**: Copy only active picks to 2026
3. **Track Available Slots**: Calculate how many draft slots each player has available
4. **Update Draft Logic**: Ensure draft system respects the 20-pick limit per player

### Database Query Logic
```sql
-- Get active picks for a player (celebrities still alive)
SELECT * FROM Deadpool 
WHERE PK = 'PLAYER#{player_id}' 
AND begins_with(SK, 'PICK#2025#')
AND PersonID IN (
    SELECT PersonID FROM Deadpool 
    WHERE begins_with(PK, 'PERSON#') 
    AND SK = 'DETAILS'
    AND (attribute_not_exists(DeathDate) OR DeathDate NOT LIKE '2025%')
)
```

## Impact Analysis

### Current Player Status (Estimated)
Based on the data I reviewed:
- **Total 2025 Picks**: ~200+ picks across all players
- **2025 Deaths**: Multiple celebrities died in 2025 (Jimmy Carter, Bob Newhart, etc.)
- **Active Picks**: Likely 15-20 active picks per player
- **Available Slots**: 0-5 additional draft opportunities per player

### Migration Adjustments Needed

#### Script Modifications
1. **Enhanced Person Lookup**: Check death status for each pick
2. **Active Pick Filtering**: Only migrate picks for living celebrities
3. **Slot Calculation**: Track available draft slots per player
4. **Validation Updates**: Ensure pick counts reflect active-only migration

#### Application Updates
1. **Draft Logic**: Respect individual player pick limits
2. **UI Updates**: Show available draft slots per player
3. **Reporting**: Distinguish between active and total historical picks

## Recommended Implementation

### Phase 1: Analysis
- [ ] Query all 2025 picks and their celebrity death status
- [ ] Calculate active pick counts per player
- [ ] Identify players with available draft slots

### Phase 2: Modified Migration
- [ ] Update migration script to filter for active picks only
- [ ] Migrate only living celebrity picks to 2026
- [ ] Validate active pick counts per player

### Phase 3: Draft Preparation
- [ ] Update draft logic to handle variable pick counts
- [ ] Ensure players can draft up to their individual limits
- [ ] Test draft functionality with mixed pick counts

## Questions for Clarification

1. **Pick Limit Confirmation**: Is the limit 20 picks per player total?
2. **Death Date Cutoff**: Should we use calendar year 2025 or game year 2025?
3. **Partial Picks**: How should we handle players with fewer than 20 active picks?
4. **Draft Order**: Should draft order account for available slots (more slots = earlier pick)?

## Updated Migration Script Logic

```python
def get_active_picks_2025(self, player_id: str) -> List[Dict[str, Any]]:
    """Get only active (living) picks for a player from 2025"""
    picks_2025 = self.get_player_picks(player_id, 2025)
    active_picks = []
    
    for pick in picks_2025:
        person = self.get_person(pick['person_id'])
        if person:
            death_date = person.get('death_date')
            # Check if person is still alive or didn't die in 2025
            if not death_date or not death_date.startswith('2025'):
                active_picks.append(pick)
    
    return active_picks

def migrate_active_picks_only(self, player_id: str, player_name: str) -> bool:
    """Migrate only active 2025 picks for a player to 2026"""
    active_picks_2025 = self.get_active_picks_2025(player_id)
    
    self.log(f"Migrating {len(active_picks_2025)} active picks for {player_name}")
    self.log(f"  Available draft slots: {20 - len(active_picks_2025)}")
    
    # Create 2026 picks for active celebrities only
    for pick in active_picks_2025:
        # Migration logic here...
```

## Conclusion

The active-picks-only migration strategy is more aligned with typical fantasy game mechanics and provides better gameplay dynamics. This approach:

- Maintains strategic value of living picks
- Creates drafting opportunities for 2026
- Ensures competitive balance
- Provides fresh gameplay elements

I recommend updating the migration plan to use this active-picks-only approach. Would you like me to revise the migration scripts and documentation accordingly?