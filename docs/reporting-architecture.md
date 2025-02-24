# Reporting Architecture Design

## Status
Proposed

## Context
The Deadpool application needs to support data visualization and reporting capabilities. While some endpoints like leaderboard and picks-counts already provide useful data, we need a more comprehensive reporting structure that:
1. Provides aggregated statistics and trends
2. Reuses existing endpoint logic where possible
3. Optimizes data delivery for visualization purposes
4. Maintains clear separation between transactional and analytical endpoints

## Decision
We will implement a dedicated reporting structure under the `/api/v1/deadpool/reporting` path while leveraging existing endpoints where appropriate.

### Endpoint Structure

```
/api/v1/deadpool/reporting/
├── overview
│   GET / - High-level statistics and current state
│   GET /historical - Historical statistics over time
│
├── trends
│   ├── time
│   │   GET / - Time-based analytics (daily, weekly, monthly patterns)
│   │   GET /picks - Pick frequency analysis
│   │   GET /deaths - Death rate patterns
│   │
│   ├── demographics
│   │   GET / - Age distribution analysis
│   │   GET /success-rates - Success rates by age group
│   │   GET /preferences - Player age group preferences
│   │
│   └── categories
│       GET / - Category distribution
│       GET /success-rates - Success rates by category
│       GET /trends - Category popularity trends
│
└── player-analytics
    GET / - Extended player performance metrics
    GET /historical - Historical performance analysis
    GET /strategies - Strategy analysis (age/category preferences)
```

### Data Models

#### Overview Statistics
```python
class OverviewStats(BaseModel):
    total_players: int
    total_picks: int
    total_deceased: int
    average_pick_age: float
    most_popular_age_range: str
    most_successful_age_range: str
    pick_success_rate: float
    updated_at: datetime

class HistoricalStats(BaseModel):
    timestamp: datetime
    stats: OverviewStats

class OverviewResponse(BaseModel):
    message: str
    data: OverviewStats
    historical_data: Optional[List[HistoricalStats]]
```

#### Time-based Analytics
```python
class TimeAnalytics(BaseModel):
    period: str  # daily, weekly, monthly
    pick_count: int
    death_count: int
    success_rate: float
    average_age: float
    timestamp: datetime

class TimeAnalyticsResponse(BaseModel):
    message: str
    data: List[TimeAnalytics]
    metadata: Dict[str, Any]  # For aggregated statistics
```

#### Demographic Analysis
```python
class AgeGroup(BaseModel):
    range: str  # e.g., "60-69"
    pick_count: int
    death_count: int
    success_rate: float
    average_score: float

class DemographicResponse(BaseModel):
    message: str
    data: List[AgeGroup]
    metadata: Dict[str, Any]
```

#### Category Analysis
```python
class CategoryStats(BaseModel):
    category: str
    pick_count: int
    death_count: int
    success_rate: float
    average_age: float
    average_score: float
    trend: str  # increasing, decreasing, stable

class CategoryResponse(BaseModel):
    message: str
    data: List[CategoryStats]
    metadata: Dict[str, Any]
```

#### Player Analytics
```python
class PlayerStrategy(BaseModel):
    player_id: str
    player_name: str
    preferred_age_ranges: List[str]
    preferred_categories: List[str]
    pick_timing_pattern: str
    success_rate: float
    score_progression: List[float]

class PlayerAnalyticsResponse(BaseModel):
    message: str
    data: List[PlayerStrategy]
    metadata: Dict[str, Any]
```

### Implementation Approach

1. **Data Access Layer**
   - Create a new ReportingService class that coordinates data aggregation
   - Reuse existing DynamoDBClient methods where possible
   - Implement new aggregation methods for reporting-specific queries

```python
class ReportingService:
    def __init__(self, db_client: DynamoDBClient):
        self.db = db_client
        
    async def get_overview_stats(self) -> OverviewStats:
        # Reuse existing endpoints/methods
        players = await self.db.get_players(datetime.now().year)
        picks = await self.db.get_picks()
        
        # Aggregate new statistics
        return OverviewStats(
            total_players=len(players),
            total_picks=len(picks),
            # ... additional aggregation logic
        )
```

2. **Caching Strategy**
   - Implement caching for reporting endpoints
   - Use different cache durations based on data volatility
   - Update cache on relevant data changes

```python
class ReportingCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_keys = {
            'overview': 'reporting:overview',
            'trends': 'reporting:trends',
            # ... additional cache keys
        }
        self.ttls = {
            'overview': 300,  # 5 minutes
            'trends': 3600,   # 1 hour
            # ... additional TTLs
        }
```

3. **Router Implementation**
   - Create a new reporting router
   - Implement endpoints using ReportingService
   - Add appropriate error handling and logging

```python
reporting_router = APIRouter(
    prefix="/api/v1/deadpool/reporting",
    tags=["deadpool-reporting"],
)

@reporting_router.get("/overview", response_model=OverviewResponse)
async def get_overview_stats():
    """
    Get high-level statistics about the current state of the game.
    """
    try:
        stats = await reporting_service.get_overview_stats()
        return {
            "message": "Successfully retrieved overview statistics",
            "data": stats
        }
    except Exception as e:
        # Error handling
        pass
```

### Optimization Strategies

1. **Query Optimization**
   - Use composite keys in DynamoDB for efficient data retrieval
   - Implement parallel queries where possible
   - Use projections to retrieve only needed attributes

2. **Caching**
   - Cache frequently accessed reporting data
   - Implement cache warming for heavy queries
   - Use cache versioning for data consistency

3. **Data Aggregation**
   - Pre-calculate common aggregations
   - Store aggregated data for historical analysis
   - Update aggregations incrementally when possible

### Error Handling

1. **Graceful Degradation**
   - Return partial data if some aggregations fail
   - Implement fallbacks for unavailable data
   - Clear error messages for different failure scenarios

2. **Monitoring**
   - Log performance metrics for reporting endpoints
   - Track cache hit/miss rates
   - Monitor query execution times

## Consequences

### Advantages
1. Clear separation of reporting capabilities
2. Reuse of existing business logic
3. Optimized for visualization needs
4. Scalable and maintainable structure
5. Efficient caching strategies

### Disadvantages
1. Additional complexity in caching layer
2. Need to maintain consistency between transactional and reporting data
3. Increased infrastructure requirements for caching

## Implementation Notes

1. **Phase 1: Core Reporting**
   - Implement overview endpoint
   - Basic trend analysis
   - Reuse existing endpoints

2. **Phase 2: Advanced Analytics**
   - Implement detailed trends
   - Add player analytics
   - Enhanced caching

3. **Phase 3: Optimization**
   - Performance tuning
   - Advanced caching strategies
   - Additional aggregations

## Migration Strategy

1. Implement new reporting endpoints alongside existing ones
2. Gradually move visualization consumers to new endpoints
3. Monitor performance and adjust as needed