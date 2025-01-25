from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..models.deadpool import PlayerResponse, PersonResponse, DeadpoolResponse
from ..utils.dynamodb import DynamoDBClient

router = APIRouter(
    prefix="/api/v1/deadpool",
    tags=["deadpool"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=DeadpoolResponse)
async def get_deadpool_data():
    """
    Get all Deadpool entries from DynamoDB.
    """
    db = DynamoDBClient()
    entries = await db.get_deadpool_entries()
    return {
        "message": "Successfully retrieved deadpool entries",
        "data": entries
    }

@router.get("/players", response_model=PlayerResponse)
async def get_players(year: Optional[int] = Query(None, description="Filter players by year")):
    """
    Get current players for a given year, sorted by draft order.
    Players are considered current if they have a draft order > 0.
    """
    db = DynamoDBClient()
    players = await db.get_players(year)
    return {
        "message": "Successfully retrieved players",
        "data": players
    }

@router.get("/people", response_model=PersonResponse)
async def get_people():
    """
    Get a list of all people in the deadpool.
    """
    db = DynamoDBClient()
    people = await db.get_people()
    return {
        "message": "Successfully retrieved people",
        "data": people
    }
