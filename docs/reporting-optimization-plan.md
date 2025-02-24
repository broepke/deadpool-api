# Reporting API Performance Optimization Plan

## Current Issues

### 1. N+1 Query Problem
The current implementation makes multiple sequential database queries:
- Fetches all players for a year
- For each player, fetches their picks
- For each pick, fetches person details
This results in hundreds or thousands of individual database queries for a single API request.

### 2. Redundant Data Fetching
- Same data (players, picks, people) is fetched multiple times across different analytics endpoints
- No data sharing between concurrent requests
- Full person details are fetched when only specific fields are needed

### 3. Lack of Caching
- Every request recalculates statistics from scratch
- No caching of intermediate results
- No reuse of calculations between requests

### 4. Inefficient Data Processing
- Many calculations are done in memory that could be optimized at the database level
- Multiple iterations over the same data
- Unnecessary data transformations

## Optimization Strategies

### 1. Implement Batch Loading
```python
# Instead of:
for player in players:
    picks = await self.db.get_player_picks(player["id"], target_year)
    for pick in picks:
        person = await self.db.get_person(pick["person_id"])

# Use batch loading:
player_ids = [p["id"] for p in players]
picks = await self.db.get_picks_for_players(player_ids, target_year)
person_ids = [p["person_id"] for p in picks]
people = await self.db.get_people_by_ids(person_ids)
```

### 2. Add Caching Layer

#### 2.1 In-Memory Cache
- Cache frequently accessed data with short TTL
- Cache intermediate calculations
- Use Redis or similar for distributed caching

```python
class ReportingCache:
    def __init__(self, ttl=300):  # 5 minute TTL
        self.cache = {}
        self.ttl = ttl

    async def get_or_compute(self, key, compute_func):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
        
        value = await compute_func()
        self.cache[key] = (value, time.time())
        return value
```

#### 2.2 Database Materialized Views
- Create materialized views for common aggregations
- Update views periodically or on data change
- Example:

```sql
CREATE MATERIALIZED VIEW yearly_pick_stats AS
SELECT 
    year,
    COUNT(DISTINCT player_id) as total_players,
    COUNT(*) as total_picks,
    AVG(age) as avg_age
FROM picks
JOIN people ON picks.person_id = people.id
GROUP BY year;
```

### 3. Optimize Database Queries

#### 3.1 Composite Queries
Replace multiple queries with single optimized queries that return all needed data:

```python
async def get_player_stats(self, year: int):
    query = """
    SELECT 
        p.id as player_id,
        p.name as player_name,
        COUNT(pk.id) as pick_count,
        SUM(CASE WHEN pe.death_date IS NOT NULL THEN 1 ELSE 0 END) as deceased_count,
        AVG(pe.age) as avg_pick_age
    FROM players p
    LEFT JOIN picks pk ON p.id = pk.player_id
    LEFT JOIN people pe ON pk.person_id = pe.id
    WHERE pk.year = :year
    GROUP BY p.id, p.name
    """
    return await self.db.execute(query, {"year": year})
```

#### 3.2 Denormalization
Add computed fields to reduce join complexity:
- Add age_range to people table
- Add pick_count to players table
- Add success_rate to players table

### 4. API Optimizations

#### 4.1 GraphQL Implementation
Consider implementing GraphQL to allow clients to request only needed fields:
```graphql
query {
  playerAnalytics(year: 2025) {
    player_id
    player_name
    success_rate
    # Only fetch fields needed
  }
}
```

#### 4.2 Pagination
Add pagination to all endpoints:
```python
@router.get("/player-analytics")
async def get_player_analytics(
    offset: int = 0,
    limit: int = 20,
    year: Optional[int] = None
):
    # Implement pagination logic
```

#### 4.3 Partial Response Support
Allow clients to request partial data:
```python
@router.get("/overview")
async def get_overview_stats(
    fields: List[str] = Query(None),
    year: Optional[int] = None
):
    # Return only requested fields
```

## Implementation Phases

### Phase 1: Quick Wins
1. Implement batch loading for immediate query reduction
2. Add basic in-memory caching for frequently accessed data
3. Optimize existing database queries

### Phase 2: Infrastructure Updates
1. Set up Redis for distributed caching
2. Create database materialized views
3. Implement database denormalization

### Phase 3: API Modernization
1. Add GraphQL support
2. Implement pagination
3. Add partial response support

### Phase 4: Monitoring & Optimization
1. Add performance monitoring
2. Implement cache warming
3. Fine-tune cache TTLs and batch sizes

## Success Metrics
- Response time reduction (target: 80% improvement)
- Database query reduction (target: 90% reduction)
- Cache hit rate (target: >80%)
- API error rate (target: <0.1%)

## Risks and Mitigations
1. Cache invalidation complexity
   - Implement careful cache key design
   - Use cache versioning
   - Monitor cache hit/miss rates

2. Data consistency
   - Implement proper cache invalidation
   - Use write-through caching
   - Add consistency checks

3. Memory usage
   - Monitor cache size
   - Implement cache eviction policies
   - Set appropriate TTLs

4. Migration complexity
   - Phase implementations
   - Maintain backward compatibility
   - Comprehensive testing plan