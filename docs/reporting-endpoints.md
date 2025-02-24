# Reporting API Endpoints

## Overview Statistics
```
GET /api/v1/deadpool/reporting/overview
```
Query Parameters:
- `year` (optional, integer): Year to get statistics for. Defaults to current year.

Returns high-level statistics including total players, picks, success rates, and age distribution analysis.

## Time Analytics
```
GET /api/v1/deadpool/reporting/trends/time
```
Query Parameters:
- `year` (optional, integer): Year to analyze. Defaults to current year.
- `period` (optional, string): Analysis period. One of: "daily", "weekly", "monthly". Defaults to "monthly".

Returns time-based analytics about picks and deaths, analyzing patterns over different time periods.

## Demographics Analysis
```
GET /api/v1/deadpool/reporting/trends/demographics
```
Query Parameters:
- `year` (optional, integer): Year to analyze. Defaults to current year.

Returns demographic analysis of picks, including age distributions and success rates by age group.

## Player Analytics
```
GET /api/v1/deadpool/reporting/player-analytics
```
Query Parameters:
- `player_id` (optional, string): Player ID to analyze. If not provided, analyzes all players.
- `year` (optional, integer): Year to analyze. Defaults to current year.

Returns detailed analytics for player(s), including:
- Age preferences
- Pick timing patterns
- Success rates
- Score progression

## Response Formats

### Overview Response
```json
{
    "message": string,
    "data": {
        "total_players": integer,
        "total_picks": integer,
        "total_deceased": integer,
        "average_pick_age": float,
        "most_popular_age_range": string,
        "most_successful_age_range": string,
        "pick_success_rate": float,
        "age_distribution": {
            [age_range: string]: {
                "count": integer,
                "deceased": integer
            }
        },
        "updated_at": datetime,
        "year": integer
    }
}
```

### Time Analytics Response
```json
{
    "message": string,
    "data": [
        {
            "period": string,
            "pick_count": integer,
            "death_count": integer,
            "success_rate": float,
            "average_age": float,
            "timestamp": datetime
        }
    ],
    "metadata": {
        "total_periods": integer,
        "total_picks": integer,
        "total_deaths": integer,
        "overall_success_rate": float,
        "average_picks_per_period": float,
        "period_type": string,
        "year": integer
    }
}
```

### Demographics Response
```json
{
    "message": string,
    "data": [
        {
            "range": string,
            "pick_count": integer,
            "death_count": integer,
            "success_rate": float,
            "average_score": float
        }
    ],
    "metadata": {
        "total_picks": integer,
        "total_deaths": integer,
        "overall_success_rate": float,
        "most_popular_range": string,
        "most_successful_range": string,
        "year": integer,
        "updated_at": datetime
    }
}
```

### Player Analytics Response
```json
{
    "message": string,
    "data": [
        {
            "player_id": string,
            "player_name": string,
            "preferred_age_ranges": string[],
            "preferred_categories": string[],
            "pick_timing_pattern": string,
            "success_rate": float,
            "score_progression": float[]
        }
    ],
    "metadata": {
        "year": integer,
        "total_players": integer,
        "total_picks": integer,
        "total_deaths": integer,
        "overall_success_rate": float,
        "updated_at": datetime
    }
}