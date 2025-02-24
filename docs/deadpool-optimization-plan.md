# Deadpool API Performance Optimization Plan

## High-Traffic Endpoints to Optimize

### 1. GET /picks
Current Issues:
- Makes individual queries for each player's picks
- Nested loop querying person details for each pick
- No caching of results

Optimization Strategy:
```python
# Instead of:
for player in players:
    picks = await db.get_player_picks(player["id"], year)
    for pick in picks:
        person = await db.get_person(pick["person_id"])

# Use batch operations:
player_ids = [p["id"] for p in players]
all_picks = await db.batch_get_player_picks(player_ids, year)
person_ids = set()
for picks in all_picks.values():
    person_ids.update(pick["person_id"] for pick in picks)
people = await db.batch_get_people(list(person_ids))
```

### 2. GET /leaderboard
Current Issues:
- Individual queries for each player's picks
- Repeated person queries
- Score calculations performed on every request

Optimization Strategy:
1. Implement caching:
```python
@router.get("/leaderboard")
async def get_leaderboard(year: Optional[int] = None):
    cache_key = f"leaderboard_{year or datetime.now().year}"
    return await reporting_cache.get_or_compute(
        cache_key,
        lambda: calculate_leaderboard(year)
    )
```

2. Use batch operations in calculation:
```python
async def calculate_leaderboard(year):
    players = await db.get_players(year)
    all_picks = await db.batch_get_player_picks([p["id"] for p in players], year)
    all_people = await db.batch_get_people(get_unique_person_ids(all_picks))
    # Calculate scores using cached data
```

### 3. GET /picks-counts
Current Issues:
- Individual queries for each player's picks
- Repeated person status checks

Optimization Strategy:
1. Add caching with short TTL (1 minute):
```python
@router.get("/picks-counts")
async def get_picks_counts(year: Optional[int] = None):
    cache_key = f"picks_counts_{year or datetime.now().year}"
    return await reporting_cache.get_or_compute(
        cache_key,
        lambda: calculate_picks_counts(year),
        ttl=60  # 1 minute TTL
    )
```

2. Use batch operations:
```python
async def calculate_picks_counts(year):
    players = await db.get_players(year)
    all_picks = await db.batch_get_player_picks([p["id"] for p in players], year)
    all_people = await db.batch_get_people(get_unique_person_ids(all_picks))
    # Calculate counts using cached data
```

### 4. GET /picks/by-person/{person_id}
Current Issues:
- Multiple queries across years
- Individual player and pick queries
- No result caching

Optimization Strategy:
1. Implement caching with person-specific invalidation:
```python
@router.get("/picks/by-person/{person_id}")
async def get_picks_by_person(person_id: str, year: Optional[int] = None):
    cache_key = f"person_picks_{person_id}_{year or 'all'}"
    return await reporting_cache.get_or_compute(
        cache_key,
        lambda: get_person_picks_data(person_id, year)
    )
```

2. Use batch operations:
```python
async def get_person_picks_data(person_id, year):
    # Get all relevant years in one query
    draft_orders = await db.get_draft_order(year)
    years = {order["year"] for order in draft_orders}
    
    # Batch get all players for these years
    players_by_year = {
        y: await db.get_players(y) for y in years
    }
    
    # Batch get all picks
    all_picks = await db.batch_get_player_picks(
        [p["id"] for players in players_by_year.values() for p in players],
        year
    )
```

## Implementation Phases

### Phase 1: Add Caching Infrastructure
1. Implement caching utility with TTL support
2. Add cache invalidation hooks for data updates
3. Configure cache TTLs based on data volatility

### Phase 2: Optimize Database Operations
1. Implement batch operations in DynamoDB client
2. Add fallback to individual queries for error handling
3. Update IAM permissions for batch operations

### Phase 3: Endpoint Optimization
1. Update /picks endpoint with batch operations
2. Optimize /leaderboard with caching and batch operations
3. Improve /picks-counts performance
4. Enhance /picks/by-person/{person_id} efficiency

### Phase 4: Monitoring & Tuning
1. Add performance monitoring
2. Track cache hit rates
3. Monitor database operation counts
4. Fine-tune cache TTLs based on usage patterns

## Success Metrics
- Response time reduction (target: 70% improvement)
- Database query reduction (target: 80% reduction)
- Cache hit rate (target: >90% for high-traffic endpoints)
- Error rate (target: <0.1%)

## Risks and Mitigations

### 1. Cache Consistency
Risk: Stale data in cache
Mitigation:
- Use appropriate TTLs based on data update frequency
- Implement cache invalidation on data updates
- Add cache versioning for breaking changes

### 2. Database Load
Risk: Batch operations may increase memory usage
Mitigation:
- Implement chunking for large batch operations
- Add circuit breakers for batch size limits
- Monitor database metrics

### 3. Error Handling
Risk: Batch operation failures
Mitigation:
- Implement graceful fallbacks to individual queries
- Add detailed error logging
- Monitor failure rates and patterns

## Next Steps
1. Review and approve optimization plan
2. Implement caching infrastructure
3. Add batch operations to DynamoDB client
4. Update endpoints incrementally
5. Monitor and tune performance