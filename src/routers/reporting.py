from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from ..models.reporting import (
    OverviewResponse,
    TimeAnalyticsResponse,
    DemographicResponse,
    CategoryResponse,
    PlayerAnalyticsResponse
)
from ..services.reporting import ReportingService
from ..utils.dynamodb import DynamoDBClient
from ..utils.logging import cwlogger, Timer

router = APIRouter(
    prefix="/api/v1/deadpool/reporting",
    tags=["deadpool-reporting"],
    responses={404: {"description": "Not found"}},
)

@router.get("/overview", response_model=OverviewResponse)
async def get_overview_stats(
    year: Optional[int] = Query(None, description="Year to get statistics for (defaults to current year)")
):
    """
    Get high-level statistics about the current state of the game.
    Includes total players, picks, success rates, and age distribution analysis.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_OVERVIEW_STATS_START",
                "Retrieving overview statistics",
                data={"year": target_year},
            )

            reporting_service = ReportingService(DynamoDBClient())
            stats = await reporting_service.get_overview_stats(target_year)

            cwlogger.info(
                "GET_OVERVIEW_STATS_COMPLETE",
                "Successfully retrieved overview statistics",
                data={
                    "year": target_year,
                    "total_players": stats["total_players"],
                    "total_picks": stats["total_picks"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved overview statistics",
                "data": stats
            }

        except Exception as e:
            cwlogger.error(
                "GET_OVERVIEW_STATS_ERROR",
                "Error retrieving overview statistics",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving overview statistics"
            )

@router.get("/trends/time", response_model=TimeAnalyticsResponse)
async def get_time_analytics(
    year: Optional[int] = Query(None, description="Year to analyze (defaults to current year)"),
    period: Optional[str] = Query("monthly", description="Analysis period (daily, weekly, or monthly)")
):
    """
    Get time-based analytics about picks and deaths.
    Analyzes patterns over different time periods.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            # Validate period parameter
            if period not in ["daily", "weekly", "monthly"]:
                raise HTTPException(
                    status_code=400,
                    detail="Period must be one of: daily, weekly, monthly"
                )

            cwlogger.info(
                "GET_TIME_ANALYTICS_START",
                "Retrieving time-based analytics",
                data={"year": target_year, "period": period},
            )

            reporting_service = ReportingService(DynamoDBClient())
            analytics = await reporting_service.get_time_analytics(target_year, period)

            cwlogger.info(
                "GET_TIME_ANALYTICS_COMPLETE",
                "Successfully retrieved time-based analytics",
                data={
                    "year": target_year,
                    "period": period,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved time-based analytics",
                "data": analytics["data"],
                "metadata": analytics["metadata"]
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_TIME_ANALYTICS_ERROR",
                "Error retrieving time-based analytics",
                error=e,
                data={
                    "year": target_year,
                    "period": period,
                    "elapsed_ms": timer.elapsed_ms
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving time-based analytics"
            )

@router.get("/trends/demographics", response_model=DemographicResponse)
async def get_demographic_analysis(
    year: Optional[int] = Query(None, description="Year to analyze (defaults to current year)")
):
    """
    Get demographic analysis of picks.
    Analyzes age distributions and success rates by age group.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_DEMOGRAPHIC_ANALYSIS_START",
                "Retrieving demographic analysis",
                data={"year": target_year},
            )

            reporting_service = ReportingService(DynamoDBClient())
            analysis = await reporting_service.get_demographic_analysis(target_year)

            cwlogger.info(
                "GET_DEMOGRAPHIC_ANALYSIS_COMPLETE",
                "Successfully retrieved demographic analysis",
                data={
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved demographic analysis",
                "data": analysis["data"],
                "metadata": analysis["metadata"]
            }

        except Exception as e:
            cwlogger.error(
                "GET_DEMOGRAPHIC_ANALYSIS_ERROR",
                "Error retrieving demographic analysis",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving demographic analysis"
            )

@router.get("/trends/categories", response_model=CategoryResponse)
async def get_category_analysis(
    year: Optional[int] = Query(None, description="Year to analyze (defaults to current year)")
):
    """
    Get analysis of picks by category.
    Analyzes success rates and trends across different celebrity categories.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_CATEGORY_ANALYSIS_START",
                "Retrieving category analysis",
                data={"year": target_year},
            )

            reporting_service = ReportingService(DynamoDBClient())
            analysis = await reporting_service.get_category_analysis(target_year)

            cwlogger.info(
                "GET_CATEGORY_ANALYSIS_COMPLETE",
                "Successfully retrieved category analysis",
                data={
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved category analysis",
                "data": analysis["data"],
                "metadata": analysis["metadata"]
            }

        except Exception as e:
            cwlogger.error(
                "GET_CATEGORY_ANALYSIS_ERROR",
                "Error retrieving category analysis",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving category analysis"
            )

@router.get("/player-analytics", response_model=PlayerAnalyticsResponse)
async def get_player_analytics(
    player_id: Optional[str] = Query(None, description="Player ID to analyze (optional)"),
    year: Optional[int] = Query(None, description="Year to analyze (defaults to current year)")
):
    """
    Get detailed analytics for player(s).
    Analyzes player strategies, preferences, and performance trends.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYER_ANALYTICS_START",
                "Retrieving player analytics",
                data={
                    "player_id": player_id,
                    "year": target_year
                },
            )

            reporting_service = ReportingService(DynamoDBClient())
            analytics = await reporting_service.get_player_analytics(player_id, target_year)

            cwlogger.info(
                "GET_PLAYER_ANALYTICS_COMPLETE",
                "Successfully retrieved player analytics",
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved player analytics",
                "data": analytics["data"],
                "metadata": analytics["metadata"]
            }

        except Exception as e:
            cwlogger.error(
                "GET_PLAYER_ANALYTICS_ERROR",
                "Error retrieving player analytics",
                error=e,
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving player analytics"
            )