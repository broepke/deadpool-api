from pydantic import BaseModel
from typing import Dict, List, Any
from datetime import datetime

class AgeRangeStats(BaseModel):
    """Statistics for an age range."""
    count: int
    deceased: int

class OverviewStats(BaseModel):
    """Overview statistics model."""
    total_players: int
    total_picks: int
    total_deceased: int
    average_pick_age: float
    most_popular_age_range: str
    most_successful_age_range: str
    pick_success_rate: float
    age_distribution: Dict[str, AgeRangeStats]
    updated_at: datetime
    year: int

class OverviewResponse(BaseModel):
    """Response model for overview statistics."""
    message: str
    data: OverviewStats

class TimeAnalytics(BaseModel):
    """Time-based analytics model."""
    period: str  # daily, weekly, monthly
    pick_count: int
    death_count: int
    success_rate: float
    average_age: float
    timestamp: datetime

class TimeAnalyticsResponse(BaseModel):
    """Response model for time-based analytics."""
    message: str
    data: List[TimeAnalytics]
    metadata: Dict[str, Any]

class AgeGroup(BaseModel):
    """Age group analysis model."""
    range: str
    pick_count: int
    death_count: int
    success_rate: float
    average_score: float

class DemographicResponse(BaseModel):
    """Response model for demographic analysis."""
    message: str
    data: List[AgeGroup]
    metadata: Dict[str, Any]

class CategoryStats(BaseModel):
    """Category statistics model."""
    category: str
    pick_count: int
    death_count: int
    success_rate: float
    average_age: float
    average_score: float
    trend: str  # increasing, decreasing, stable

class CategoryResponse(BaseModel):
    """Response model for category analysis."""
    message: str
    data: List[CategoryStats]
    metadata: Dict[str, Any]

class PlayerStrategy(BaseModel):
    """Player strategy analysis model."""
    player_id: str
    player_name: str
    preferred_age_ranges: List[str]
    pick_timing_pattern: str
    success_rate: float
    score_progression: List[Dict[str, Any]]  # Contains score and date
    points: Dict[str, float] = {
        "current": 0.0,
        "total_potential": 0.0,
        "remaining": 0.0
    }

class PlayerAnalyticsResponse(BaseModel):
    """Response model for player analytics."""
    message: str
    data: List[PlayerStrategy]
    metadata: Dict[str, Any]