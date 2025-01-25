from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
from ..models.deadpool import (
    PlayerResponse, PersonResponse, DeadpoolResponse,
    PlayerUpdate, PersonUpdate, SinglePlayerResponse,
    SinglePersonResponse, SingleDeadpoolEntryResponse,
    RouteInfo, RoutesResponse
)
from ..utils.dynamodb import DynamoDBClient

router = APIRouter(
    prefix="/api/v1/deadpool",
    tags=["deadpool"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=RoutesResponse)
async def get_routes():
    """
    Get all available API routes.
    """
    routes = []
    for route in router.routes:
        # Skip the root endpoint itself to avoid recursion
        if route.path != "/api/v1/deadpool/":
            routes.append({
                "path": f"/api/v1/deadpool{route.path}",
                "name": route.name
            })
    return {
        "message": "Successfully retrieved available routes",
        "routes": routes
    }

@router.get("/entries", response_model=DeadpoolResponse)
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

@router.get("/entries/{entry_id}", response_model=SingleDeadpoolEntryResponse)
async def get_deadpool_entry(
    entry_id: str = Path(..., description="The ID of the entry to get")
):
    """
    Get a specific deadpool entry.
    """
    db = DynamoDBClient()
    entry = await db.get_deadpool_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {
        "message": "Successfully retrieved entry",
        "data": entry
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

@router.get("/players/{player_id}", response_model=SinglePlayerResponse)
async def get_player(
    player_id: str = Path(..., description="The ID of the player to get"),
    year: Optional[int] = Query(None, description="The year to get the player's draft order for")
):
    """
    Get a specific player's information.
    """
    db = DynamoDBClient()
    player = await db.get_player(player_id, year)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {
        "message": "Successfully retrieved player",
        "data": player
    }

@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: str = Path(..., description="The ID of the player to update"),
    updates: PlayerUpdate = None
):
    """
    Update a player's information.
    """
    db = DynamoDBClient()
    updated_player = await db.update_player(player_id, updates.dict(exclude_unset=True))
    return {
        "message": "Successfully updated player",
        "data": [updated_player]  # Wrap in list to match response model
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

@router.get("/people/{person_id}", response_model=SinglePersonResponse)
async def get_person(
    person_id: str = Path(..., description="The ID of the person to get")
):
    """
    Get a specific person's information.
    """
    db = DynamoDBClient()
    person = await db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return {
        "message": "Successfully retrieved person",
        "data": person
    }

@router.put("/people/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: str = Path(..., description="The ID of the person to update"),
    updates: PersonUpdate = None
):
    """
    Update a person's information.
    """
    db = DynamoDBClient()
    updated_person = await db.update_person(person_id, updates.dict(exclude_unset=True))
    return {
        "message": "Successfully updated person",
        "data": [updated_person]  # Wrap in list to match response model
    }
