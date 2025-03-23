from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
import uuid
from datetime import datetime, timedelta
from ..models.deadpool import (
    PhoneVerificationRequest,
    PhoneVerificationResponse,
    CodeVerificationRequest,
    CodeVerificationResponse,
    PlayerResponse,
    PersonResponse,
    PaginatedPersonResponse,
    PlayerUpdate,
    PersonUpdate,
    SinglePlayerResponse,
    SinglePersonResponse,
    RoutesResponse,
    DraftOrderListResponse,
    PlayerPickResponse,
    PlayerPickUpdate,
    PaginatedPickDetailResponse,
    NextDrafterResponse,
    LeaderboardResponse,
    DraftRequest,
    DraftResponse,
    PicksCountResponse,
    PlayerProfileUpdate,
    ProfileUpdateResponse,
    SearchResponse,
)
from ..services.search import SearchService
from ..services.picks import PicksService
from ..utils.dynamodb import DynamoDBClient
from ..utils.logging import cwlogger, Timer
from ..utils.name_matching import names_match, get_player_name
from ..utils.sns import (
    generate_verification_code,
    send_verification_code,
    manage_sns_subscription,
    validate_phone_number
)

# SNS Topic ARN for notifications
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:deadpool-notifications"

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
    with Timer() as timer:
        try:
            cwlogger.info("GET_ROUTES_START", "Retrieving available API routes")

            routes = []
            for route in router.routes:
                # Skip the root endpoint itself to avoid recursion
                if route.path != "/api/v1/deadpool/":
                    routes.append(
                        {"path": f"/api/v1/deadpool{route.path}", "name": route.name}
                    )

            cwlogger.info(
                "GET_ROUTES_COMPLETE",
                f"Retrieved {len(routes)} routes",
                data={"route_count": len(routes), "elapsed_ms": timer.elapsed_ms},
            )

            return {
                "message": "Successfully retrieved available routes",
                "routes": routes,
            }

        except Exception as e:
            cwlogger.error(
                "GET_ROUTES_ERROR",
                "Error retrieving routes",
                error=e,
                data={"elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving routes"
            )


@router.get("/players", response_model=PlayerResponse)
async def get_players(
    year: Optional[int] = Query(None, description="Filter players by year"),
):
    """
    Get current players for a given year, sorted by draft order.
    Players are considered current if they have a draft order > 0.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYERS_START",
                f"Retrieving players for year {target_year}",
                data={"year": target_year},
            )

            db = DynamoDBClient()
            players = await db.get_players(target_year)

            cwlogger.info(
                "GET_PLAYERS_COMPLETE",
                f"Retrieved {len(players)} players",
                data={
                    "year": target_year,
                    "player_count": len(players),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved players", "data": players}

        except Exception as e:
            cwlogger.error(
                "GET_PLAYERS_ERROR",
                "Error retrieving players",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving players"
            )


@router.get("/players/{player_id}", response_model=SinglePlayerResponse)
async def get_player(
    player_id: str = Path(..., description="The ID of the player to get"),
    year: Optional[int] = Query(
        None, description="The year to get the player's draft order for"
    ),
):
    """
    Get a specific player's information.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYER_START",
                f"Retrieving player {player_id}",
                data={"player_id": player_id, "year": target_year},
            )

            db = DynamoDBClient()
            player = await db.get_player(player_id, target_year)

            if not player:
                cwlogger.warning(
                    "GET_PLAYER_ERROR",
                    "Player not found",
                    data={"player_id": player_id, "year": target_year},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            cwlogger.info(
                "GET_PLAYER_COMPLETE",
                f"Retrieved player {player_id}",
                data={
                    "player_id": player_id,
                    "player_name": get_player_name(player),
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved player", "data": player}

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PLAYER_ERROR",
                "Error retrieving player",
                error=e,
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving player"
            )


@router.put("/players/{player_id}/profile", response_model=ProfileUpdateResponse)
async def update_player_profile(
    player_id: str = Path(..., description="The ID of the player to update"),
    updates: PlayerProfileUpdate = None,
):
    """
    Update a player's profile information.

    Fields that can be updated:
    - first_name: Player's first name
    - last_name: Player's last name
    - phone_number: Player's phone number
    - phone_verified: Whether the phone number is verified
    - sms_notifications_enabled: Whether SMS notifications are enabled
    """
    with Timer() as timer:
        try:
            if not updates:
                cwlogger.warning(
                    "UPDATE_PLAYER_PROFILE_ERROR",
                    "No update data provided",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Update data is required")

            cwlogger.info(
                "UPDATE_PLAYER_PROFILE_START",
                f"Updating player profile {player_id}",
                data={
                    "player_id": player_id,
                    "updates": updates.dict(exclude_unset=True),
                },
            )

            db = DynamoDBClient()
            
            # Verify player exists
            existing_player = await db.get_player(player_id)
            if not existing_player:
                cwlogger.warning(
                    "UPDATE_PLAYER_PROFILE_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            await db.update_player(
                player_id, updates.dict(exclude_unset=True)
            )

            cwlogger.info(
                "UPDATE_PLAYER_PROFILE_COMPLETE",
                "Successfully updated player profile",
                data={
                    "player_id": player_id,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated player profile"
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_PLAYER_PROFILE_ERROR",
                "Error updating player profile",
                error=e,
                data={"player_id": player_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while updating player profile"
            )

@router.post("/players/{player_id}/phone/request-verification", response_model=PhoneVerificationResponse)
async def request_phone_verification(
    player_id: str = Path(..., description="The ID of the player to verify phone for"),
    request: PhoneVerificationRequest = None,
):
    """
    Request phone number verification for a player.
    Sends a verification code via SMS and stores it in the player's profile.
    The code expires after 10 minutes.
    Rate limited to 3 attempts per 10 minutes.
    """
    with Timer() as timer:
        try:
            if not request:
                cwlogger.warning(
                    "PHONE_VERIFICATION_REQUEST_ERROR",
                    "No request data provided",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Request data is required")

            # Validate phone number format
            if not validate_phone_number(request.phone_number):
                cwlogger.warning(
                    "PHONE_VERIFICATION_REQUEST_ERROR",
                    "Invalid phone number format",
                    data={
                        "player_id": player_id,
                        "phone_number": request.phone_number
                    },
                )
                raise HTTPException(
                    status_code=400,
                    detail="Invalid phone number format. Must be in E.164 format (e.g., +12345678900)"
                )

            db = DynamoDBClient()
            
            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.warning(
                    "PHONE_VERIFICATION_REQUEST_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            # Check rate limiting (max 3 attempts per 10 minutes)
            verification_timestamp = player.get("verification_timestamp")
            if verification_timestamp:
                last_attempt = datetime.fromisoformat(verification_timestamp)
                if last_attempt > datetime.utcnow() - timedelta(minutes=10):
                    cwlogger.warning(
                        "PHONE_VERIFICATION_REQUEST_ERROR",
                        "Rate limit exceeded",
                        data={
                            "player_id": player_id,
                            "last_attempt": verification_timestamp
                        },
                    )
                    raise HTTPException(
                        status_code=429,
                        detail="Please wait before requesting another verification code"
                    )

            # Generate and store verification code
            code = generate_verification_code()
            verification_timestamp = datetime.utcnow().isoformat()

            # Update player profile with verification data
            await db.update_player(
                player_id,
                {
                    "phone_number": request.phone_number,
                    "verification_code": code,
                    "verification_timestamp": verification_timestamp
                }
            )

            # Send verification code via SNS
            message_id = send_verification_code(request.phone_number, code)

            cwlogger.info(
                "PHONE_VERIFICATION_REQUEST_COMPLETE",
                "Successfully sent verification code",
                data={
                    "player_id": player_id,
                    "message_id": message_id,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Verification code sent successfully",
                "data": {
                    "message_id": message_id,
                    "expires_at": (datetime.fromisoformat(verification_timestamp) + timedelta(minutes=10)).isoformat()
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "PHONE_VERIFICATION_REQUEST_ERROR",
                "Error processing verification request",
                error=e,
                data={
                    "player_id": player_id,
                    "elapsed_ms": timer.elapsed_ms
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while processing the verification request"
            )

@router.post("/players/{player_id}/phone/verify", response_model=CodeVerificationResponse)
async def verify_phone_code(
    player_id: str = Path(..., description="The ID of the player to verify code for"),
    request: CodeVerificationRequest = None,
):
    """
    Verify a phone number using the provided verification code.
    The code must be verified within 10 minutes of being sent.
    Upon successful verification, the phone number is marked as verified
    and subscribed to SMS notifications.
    """
    with Timer() as timer:
        try:
            if not request:
                cwlogger.warning(
                    "PHONE_CODE_VERIFICATION_ERROR",
                    "No verification code provided",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Verification code is required")

            db = DynamoDBClient()
            
            # Get player profile
            player = await db.get_player(player_id)
            if not player:
                cwlogger.warning(
                    "PHONE_CODE_VERIFICATION_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            # Verify code exists and hasn't expired
            stored_code = player.get("verification_code")
            verification_timestamp = player.get("verification_timestamp")

            if not stored_code or not verification_timestamp:
                cwlogger.warning(
                    "PHONE_CODE_VERIFICATION_ERROR",
                    "No verification code found",
                    data={"player_id": player_id},
                )
                raise HTTPException(
                    status_code=400,
                    detail="No verification code found. Please request a new code."
                )

            # Check code expiration (10 minutes)
            if datetime.fromisoformat(verification_timestamp) < datetime.utcnow() - timedelta(minutes=10):
                cwlogger.warning(
                    "PHONE_CODE_VERIFICATION_ERROR",
                    "Verification code expired",
                    data={
                        "player_id": player_id,
                        "verification_timestamp": verification_timestamp
                    },
                )
                raise HTTPException(
                    status_code=400,
                    detail="Verification code has expired. Please request a new code."
                )

            # Verify code matches
            if request.code != stored_code:
                cwlogger.warning(
                    "PHONE_CODE_VERIFICATION_ERROR",
                    "Invalid verification code",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Invalid verification code")

            # Subscribe to notifications
            subscription_arn = None
            try:
                subscription_arn = manage_sns_subscription(
                    player["phone_number"],
                    SNS_TOPIC_ARN,
                    subscribe=True
                )
            except Exception as e:
                cwlogger.error(
                    "SNS_SUBSCRIPTION_ERROR",
                    "Error subscribing to notifications",
                    error=e,
                    data={"player_id": player_id},
                )
                # Continue with verification even if subscription fails
                pass

            # Update player profile
            await db.update_player(
                player_id,
                {
                    "phone_verified": True,
                    "sms_notifications_enabled": True  # Enable notifications by default after verification
                }
            )

            cwlogger.info(
                "PHONE_CODE_VERIFICATION_COMPLETE",
                "Successfully verified phone number",
                data={
                    "player_id": player_id,
                    "subscription_arn": subscription_arn,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Phone number successfully verified",
                "data": {
                    "verified": True
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "PHONE_CODE_VERIFICATION_ERROR",
                "Error verifying phone code",
                error=e,
                data={
                    "player_id": player_id,
                    "elapsed_ms": timer.elapsed_ms
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while verifying the phone code"
            )

@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: str = Path(..., description="The ID of the player to update or create"),
    updates: PlayerUpdate = None,
):
    """
    Update or create a player's information.

    When creating a new player, the following fields are required:
    - name: Player's full name
    - draft_order: Player's draft position
    - year: Draft year
    """
    with Timer() as timer:
        try:
            if not updates:
                cwlogger.warning(
                    "UPDATE_PLAYER_ERROR",
                    "No update data provided",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=400, detail="Update data is required")

            cwlogger.info(
                "UPDATE_PLAYER_START",
                f"{'Creating' if player_id == 'new' else 'Updating'} player {player_id}",
                data={
                    "player_id": player_id,
                    "updates": updates.dict(exclude_unset=True),
                },
            )

            # Validate required fields for new players
            existing_player = await DynamoDBClient().get_player(player_id)
            if not existing_player:
                if (
                    not updates.name
                    or updates.draft_order is None
                    or updates.year is None
                ):
                    cwlogger.warning(
                        "UPDATE_PLAYER_ERROR",
                        "Missing required fields for new player",
                        data={
                            "player_id": player_id,
                            "provided_fields": updates.dict(exclude_unset=True),
                        },
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="New players require name, draft_order, and year",
                    )

            db = DynamoDBClient()
            updated_player = await db.update_player(
                player_id, updates.dict(exclude_unset=True)
            )

            cwlogger.info(
                "UPDATE_PLAYER_COMPLETE",
                f"Successfully {'created' if not existing_player else 'updated'} player",
                data={
                    "player_id": player_id,
                    "player_name": updated_player["name"],
                    "is_new": not existing_player,
                    "year": updates.year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated player",
                "data": [updated_player],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_PLAYER_ERROR",
                "Error updating player",
                error=e,
                data={"player_id": player_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating player"
            )


@router.get("/people", response_model=PaginatedPersonResponse)
async def get_people(
    status: Optional[str] = Query(None, description="Filter by status ('deceased' or 'alive')"),
    limit: Optional[int] = Query(None, description="Limit the number of results returned. If not specified, pagination will be used."),
    page: Optional[int] = Query(1, description="Page number for paginated results", ge=1),
    page_size: Optional[int] = Query(10, description="Number of items per page", ge=1, le=100),
):
    """
    Get a list of all people in the deadpool.
    Supports pagination, limit, and status filtering.
    If limit is specified, returns that many results.
    If limit is not specified, returns paginated results with default page size of 10.
    Status can be 'deceased' or 'alive'.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "GET_PEOPLE_START",
                "Retrieving people",
                data={
                    "status": status,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size
                }
            )

            # Validate status parameter
            if status and status not in ["deceased", "alive"]:
                raise HTTPException(
                    status_code=400,
                    detail="Status must be either 'deceased' or 'alive'"
                )

            db = DynamoDBClient()
            # Get all people with optional status filter
            people = await db.get_people(status=status)

            # Sort deceased people by death date in descending order
            if status == "deceased":
                people.sort(
                    key=lambda x: x.get("metadata", {}).get("DeathDate", ""),
                    reverse=True
                )

            total_items = len(people)

            # Handle limit case
            if limit is not None:
                limited_people = people[:limit]
                cwlogger.info(
                    "GET_PEOPLE_COMPLETE",
                    f"Retrieved {len(limited_people)} people (limited from {total_items})",
                    data={
                        "status": status,
                        "limit": limit,
                        "total_items": total_items,
                        "returned_items": len(limited_people),
                        "elapsed_ms": timer.elapsed_ms,
                    },
                )
                return {
                    "message": "Successfully retrieved people",
                    "data": limited_people,
                    "total": total_items,
                    "page": 1,
                    "page_size": limit,
                    "total_pages": 1
                }

            # Handle pagination case
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_people = people[start_idx:end_idx]
            total_pages = (total_items + page_size - 1) // page_size

            cwlogger.info(
                "GET_PEOPLE_COMPLETE",
                f"Retrieved {len(paginated_people)} people (page {page} of {total_pages})",
                data={
                    "status": status,
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "returned_items": len(paginated_people),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved people",
                "data": paginated_people,
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PEOPLE_ERROR",
                "Error retrieving people",
                error=e,
                data={
                    "status": status,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size,
                    "elapsed_ms": timer.elapsed_ms
                },
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving people"
            )


@router.get("/people/{person_id}", response_model=SinglePersonResponse)
async def get_person(
    person_id: str = Path(..., description="The ID of the person to get"),
):
    """
    Get a specific person's information.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "GET_PERSON_START",
                f"Retrieving person {person_id}",
                data={"person_id": person_id},
            )

            db = DynamoDBClient()
            person = await db.get_person(person_id)

            if not person:
                cwlogger.warning(
                    "GET_PERSON_ERROR",
                    "Person not found",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            cwlogger.info(
                "GET_PERSON_COMPLETE",
                f"Retrieved person {person_id}",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "status": person["status"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {"message": "Successfully retrieved person", "data": person}

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PERSON_ERROR",
                "Error retrieving person",
                error=e,
                data={"person_id": person_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving person"
            )


@router.put("/people/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: str = Path(..., description="The ID of the person to update or create"),
    updates: PersonUpdate = None,
):
    """
    Update or create a person's information.

    When creating a new person, the following field is required:
    - name: Person's full name

    Use 'new' as the person_id to automatically generate a UUID for a new person.
    """
    with Timer() as timer:
        try:
            if not updates or not updates.name:
                cwlogger.warning(
                    "UPDATE_PERSON_ERROR",
                    "Name is required",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=400, detail="Name is required")

            # Generate UUID for new people
            is_new = person_id == "new"
            if is_new:
                person_id = str(uuid.uuid4())
                cwlogger.info(
                    "UPDATE_PERSON_START",
                    "Creating new person",
                    data={"person_id": person_id, "name": updates.name},
                )
            else:
                cwlogger.info(
                    "UPDATE_PERSON_START",
                    f"Updating person {person_id}",
                    data={
                        "person_id": person_id,
                        "updates": updates.dict(exclude_unset=True),
                    },
                )

            db = DynamoDBClient()
            updated_person = await db.update_person(
                person_id, updates.dict(exclude_unset=True)
            )

            cwlogger.info(
                "UPDATE_PERSON_COMPLETE",
                f"Successfully {'created' if is_new else 'updated'} person",
                data={
                    "person_id": person_id,
                    "person_name": updated_person["name"],
                    "is_new": is_new,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated person",
                "data": [updated_person],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_PERSON_ERROR",
                "Error updating person",
                error=e,
                data={"person_id": person_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating person"
            )


@router.get("/search", response_model=SearchResponse)
async def search_entities(
    q: str = Query(..., description="Search query string"),
    type: Optional[str] = Query("people", description="Entity type to search (people or players)"),
    mode: Optional[str] = Query("fuzzy", description="Search mode (exact or fuzzy)"),
    limit: Optional[int] = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: Optional[int] = Query(0, description="Pagination offset", ge=0),
):
    """
    Search for entities by name.
    Supports fuzzy matching and pagination.
    Currently supports searching for people and players.
    """
    with Timer() as timer:
        try:
            # Validate entity type
            if type and type not in ["people", "players"]:
                raise HTTPException(
                    status_code=400,
                    detail="Entity type must be either 'people' or 'players'"
                )

            # Validate search mode
            if mode and mode not in ["exact", "fuzzy"]:
                raise HTTPException(
                    status_code=400,
                    detail="Search mode must be either 'exact' or 'fuzzy'"
                )

            cwlogger.info(
                "SEARCH_START",
                "Starting entity search",
                data={
                    "query": q,
                    "type": type,
                    "mode": mode,
                    "limit": limit,
                    "offset": offset
                }
            )

            search_service = SearchService(DynamoDBClient())
            results = await search_service.search_entities(
                query=q,
                entity_type=type,
                mode=mode,
                limit=limit,
                offset=offset
            )

            cwlogger.info(
                "SEARCH_COMPLETE",
                "Search completed successfully",
                data={
                    "query": q,
                    "type": type,
                    "results_count": len(results["data"]),
                    "total_matches": results["metadata"]["total"],
                    "elapsed_ms": timer.elapsed_ms
                }
            )

            return {
                "message": "Successfully retrieved search results",
                **results
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "SEARCH_ERROR",
                "Error performing search",
                error=e,
                data={
                    "query": q,
                    "type": type,
                    "mode": mode,
                    "elapsed_ms": timer.elapsed_ms
                }
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while performing the search"
            )


@router.get("/draft-order", response_model=DraftOrderListResponse)
async def get_draft_order(
    year: Optional[int] = Query(None, description="Filter draft orders by year"),
    player_id: Optional[str] = Query(
        None, description="Filter draft orders by player ID"
    ),
):
    """
    Get draft order records, optionally filtered by year and/or player.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_DRAFT_ORDER_START",
                "Retrieving draft orders",
                data={"year": target_year, "player_id": player_id},
            )

            db = DynamoDBClient()
            draft_orders = await db.get_draft_order(target_year, player_id)

            cwlogger.info(
                "GET_DRAFT_ORDER_COMPLETE",
                f"Retrieved {len(draft_orders)} draft orders",
                data={
                    "year": target_year,
                    "player_id": player_id,
                    "order_count": len(draft_orders),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved draft orders",
                "data": draft_orders,
            }

        except Exception as e:
            cwlogger.error(
                "GET_DRAFT_ORDER_ERROR",
                "Error retrieving draft orders",
                error=e,
                data={
                    "year": target_year,
                    "player_id": player_id,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving draft orders",
            )


@router.put("/draft-order/{player_id}", response_model=DraftOrderListResponse)
async def update_draft_order(
    player_id: str = Path(..., description="The ID of the player to update"),
    year: int = Query(..., description="The year for the draft order"),
    draft_order: int = Query(..., description="The new draft order position"),
):
    """
    Update a player's draft order for a specific year.
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "UPDATE_DRAFT_ORDER_START",
                f"Updating draft order for player {player_id}",
                data={"player_id": player_id, "year": year, "draft_order": draft_order},
            )

            db = DynamoDBClient()

            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.warning(
                    "UPDATE_DRAFT_ORDER_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            updated_order = await db.update_draft_order(player_id, year, draft_order)

            cwlogger.info(
                "UPDATE_DRAFT_ORDER_COMPLETE",
                "Successfully updated draft order",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "year": year,
                    "draft_order": draft_order,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated draft order",
                "data": [updated_order],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "UPDATE_DRAFT_ORDER_ERROR",
                "Error updating draft order",
                error=e,
                data={
                    "player_id": player_id,
                    "year": year,
                    "draft_order": draft_order,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while updating draft order"
            )


@router.put("/picks/{player_id}", response_model=PlayerPickResponse)
async def update_player_pick(
    player_id: str = Path(..., description="The ID of the player to update picks for"),
    updates: PlayerPickUpdate = None,
):
    """
    Update or create a pick for a specific player.
    """
    with Timer() as timer:
        try:
            if not updates:
                raise HTTPException(status_code=400, detail="Update data is required")

            cwlogger.info(
                "PLAYER_PICK_START",
                f"Updating pick for player {player_id}",
                data={
                    "player_id": player_id,
                    "person_id": updates.person_id,
                    "year": updates.year,
                },
            )

            db = DynamoDBClient()

            # Verify player exists
            player = await db.get_player(player_id)
            if not player:
                cwlogger.error(
                    "PLAYER_PICK_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            # Verify person exists
            person = await db.get_person(updates.person_id)
            if not person:
                cwlogger.error(
                    "PLAYER_PICK_ERROR",
                    "Person not found",
                    data={"person_id": updates.person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            # Update the pick
            updated_pick = await db.update_player_pick(player_id, updates.dict())

            # Invalidate picks cache for the affected year
            picks_service = PicksService(db)
            await picks_service.invalidate_picks_cache(updates.year)

            cwlogger.info(
                "PLAYER_PICK_COMPLETE",
                f"Successfully updated pick for player {player_id}",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "person_id": updates.person_id,
                    "person_name": person["name"],
                    "year": updates.year,
                    "timestamp": updated_pick["timestamp"],
                    "cache_invalidated": True,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully updated player pick",
                "data": [updated_pick],  # Wrap in list to match response model
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "PLAYER_PICK_ERROR",
                "Unexpected error updating player pick",
                error=e,
                data={"player_id": player_id, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while updating the player pick",
            )

@router.get("/picks/{player_id}", response_model=PaginatedPickDetailResponse)
async def get_player_picks(
    player_id: str = Path(..., description="The ID of the player to get picks for"),
    year: Optional[int] = Query(None, description="Filter picks by year (defaults to current year)"),
    limit: Optional[int] = Query(None, description="Limit the number of results returned. If not specified, pagination will be used."),
    page: Optional[int] = Query(1, description="Page number for paginated results", ge=1),
    page_size: Optional[int] = Query(10, description="Number of items per page", ge=1, le=100),
):
    """
    Get picks for a specific player, optionally filtered by year.
    If limit is specified, returns that many results.
    If limit is not specified, returns paginated results with default page size of 10.
    Returns detailed pick information including player and picked person details.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PLAYER_PICKS_START",
                f"Retrieving picks for player {player_id}",
                data={"player_id": player_id, "year": target_year},
            )

            db = DynamoDBClient()

            # Verify player exists and get their draft order for the target year
            player = await db.get_player(player_id, target_year)
            if not player:
                cwlogger.warning(
                    "GET_PLAYER_PICKS_ERROR",
                    "Player not found",
                    data={"player_id": player_id},
                )
                raise HTTPException(status_code=404, detail="Player not found")

            picks = await db.get_player_picks(player_id, target_year)
            
            # Build the detailed pick information
            detailed_picks = []
            for pick in picks:
                # Get person details
                picked_person = await db.get_person(pick["person_id"])
                
                # Extract additional person details from metadata
                person_metadata = picked_person.get("metadata", {}) if picked_person else {}
                
                pick_detail = {
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "draft_order": player["draft_order"],
                    "pick_person_id": pick["person_id"],
                    "pick_person_name": picked_person["name"] if picked_person else None,
                    "pick_person_age": person_metadata.get("Age"),
                    "pick_person_birth_date": person_metadata.get("BirthDate"),
                    "pick_person_death_date": person_metadata.get("DeathDate"),
                    "pick_timestamp": pick["timestamp"],
                    "year": target_year,
                }
                detailed_picks.append(pick_detail)

            # Sort by timestamp descending
            detailed_picks.sort(key=lambda x: x["pick_timestamp"] or "", reverse=True)

            total_items = len(detailed_picks)

            # Handle limit case
            if limit is not None:
                limited_picks = detailed_picks[:limit]
                cwlogger.info(
                    "GET_PLAYER_PICKS_COMPLETE",
                    f"Retrieved {len(limited_picks)} picks (limited from {total_items})",
                    data={
                        "player_id": player_id,
                        "player_name": player["name"],
                        "year": target_year,
                        "limit": limit,
                        "total_items": total_items,
                        "returned_items": len(limited_picks),
                        "elapsed_ms": timer.elapsed_ms,
                    },
                )
                return {
                    "message": "Successfully retrieved player picks",
                    "data": limited_picks,
                    "total": total_items,
                    "page": 1,
                    "page_size": limit,
                    "total_pages": 1
                }

            # Handle pagination case
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_picks = detailed_picks[start_idx:end_idx]
            total_pages = (total_items + page_size - 1) // page_size

            cwlogger.info(
                "GET_PLAYER_PICKS_COMPLETE",
                f"Retrieved {len(paginated_picks)} picks (page {page} of {total_pages})",
                data={
                    "player_id": player_id,
                    "player_name": player["name"],
                    "year": target_year,
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "returned_items": len(paginated_picks),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully retrieved player picks",
                "data": paginated_picks,
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PLAYER_PICKS_ERROR",
                "Error retrieving player picks",
                error=e,
                data={
                    "player_id": player_id,
                    "year": target_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving player picks",
            )


@router.get("/picks", response_model=PaginatedPickDetailResponse)
async def get_picks(
    year: Optional[int] = Query(None, description="Filter picks by year (defaults to current year)"),
    limit: Optional[int] = Query(None, description="Limit the number of results returned. If not specified, pagination will be used."),
    page: Optional[int] = Query(1, description="Page number for paginated results", ge=1),
    page_size: Optional[int] = Query(10, description="Number of items per page", ge=1, le=100),
):
    """
    Get all picks for a given year with player and picked person details.
    If limit is specified, returns that many results.
    If limit is not specified, returns paginated results with default page size of 10.
    Returns data sorted by timestamp in descending order (most recent first).
    Players with no picks appear at the end, sorted by their draft order.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PICKS_START",
                f"Retrieving picks for year {target_year}",
                data={
                    "year": target_year,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size
                },
            )

            # Use the optimized picks service
            picks_service = PicksService(DynamoDBClient())
            result = await picks_service.get_picks(
                year=target_year,
                limit=limit,
                page=page,
                page_size=page_size
            )

            cwlogger.info(
                "GET_PICKS_COMPLETE",
                f"Retrieved {len(result['data'])} picks",
                data={
                    "year": target_year,
                    "total_items": result["total"],
                    "returned_items": len(result["data"]),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except Exception as e:
            cwlogger.error(
                "GET_PICKS_ERROR",
                "Error retrieving picks",
                error=e,
                data={"year": year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500, detail="An error occurred while retrieving picks"
            )


@router.post("/draft", response_model=DraftResponse)
async def draft_person(draft_request: DraftRequest):
    """
    Draft a person for the current year.
    Rules:
    1. Cannot draft someone already picked in current year
    2. Can draft someone from previous years
    3. Creates new person entry if not found in database
    4. Creates player pick entry for the drafting player
    """
    with Timer() as timer:
        try:
            db = DynamoDBClient()
            current_year = datetime.now().year

            cwlogger.info(
                "DRAFT_START",
                f"Starting draft process for {draft_request.name}",
                data={
                    "player_id": draft_request.player_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                },
            )

            # Verify player exists
            player = await db.get_player(draft_request.player_id)
            if not player:
                cwlogger.error(
                    "DRAFT_ERROR",
                    "Player not found",
                    data={
                        "player_id": draft_request.player_id,
                        "person_name": draft_request.name,
                        "year": current_year,
                    },
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Player with ID {draft_request.player_id} not found",
                )

            # Get all people to check if person already exists
            people = await db.get_people()
            
            # Use fuzzy name matching to find existing person
            existing_person = None
            best_match_score = 0
            for person in people:
                match_result = names_match(person["name"], draft_request.name)
                if match_result["match"] and match_result["similarity"] > best_match_score:
                    existing_person = person
                    best_match_score = match_result["similarity"]
                    
                    cwlogger.info(
                        "DRAFT_NAME_MATCH",
                        "Found matching person",
                        data={
                            "input_name": draft_request.name,
                            "matched_name": person["name"],
                            "normalized_input": match_result["normalized1"],
                            "normalized_match": match_result["normalized2"],
                            "similarity": match_result["similarity"],
                            "exact_match": match_result["exact_match"]
                        }
                    )

            # Get all picks for current year to check for duplicates
            players = await db.get_players(current_year)
            for player in players:
                picks = await db.get_player_picks(player["id"], current_year)
                for pick in picks:
                    picked_person = await db.get_person(pick["person_id"])
                    if picked_person:
                        match_result = names_match(picked_person["name"], draft_request.name)
                        if match_result["match"]:
                            cwlogger.warning(
                                "DRAFT_DUPLICATE",
                                "Attempted to draft already picked person",
                                data={
                                    "person_name": draft_request.name,
                                    "matched_name": picked_person["name"],
                                    "year": current_year,
                                    "similarity": match_result["similarity"],
                                    "existing_pick": {
                                        "player_id": player["id"],
                                        "player_name": player["name"],
                                        "pick_timestamp": pick.get("timestamp"),
                                    },
                                },
                            )
                            raise HTTPException(
                                status_code=400,
                                detail=f"{draft_request.name} (or similar name) has already been drafted for {current_year}",
                            )

            # If person exists in database but wasn't picked this year, use their ID
            if existing_person:
                person_id = existing_person["id"]
                cwlogger.info(
                    "DRAFT_PERSON",
                    "Using existing person record",
                    data={
                        "person_id": person_id,
                        "person_name": draft_request.name,
                        "matched_name": existing_person["name"],
                        "similarity": best_match_score,
                        "is_new": False,
                    },
                )
            else:
                # Create new person with UUID
                person_id = str(uuid.uuid4())
                await db.update_person(person_id, {"name": draft_request.name})
                cwlogger.info(
                    "DRAFT_PERSON",
                    "Created new person record",
                    data={
                        "person_id": person_id,
                        "person_name": draft_request.name,
                        "is_new": True,
                    },
                )

            # Create player pick entry
            pick_update = {"person_id": person_id, "year": current_year}
            player_pick = await db.update_player_pick(
                draft_request.player_id, pick_update
            )

            cwlogger.info(
                "DRAFT_COMPLETE",
                "Successfully completed draft",
                data={
                    "player_id": draft_request.player_id,
                    "person_id": person_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                    "is_new_person": not existing_person,
                    "pick_timestamp": player_pick["timestamp"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return {
                "message": "Successfully processed draft request",
                "data": {
                    "person_id": person_id,
                    "name": draft_request.name,
                    "is_new": not existing_person,
                    "pick_timestamp": player_pick["timestamp"],
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "DRAFT_ERROR",
                "Unexpected error during draft process",
                error=e,
                data={
                    "player_id": draft_request.player_id,
                    "person_name": draft_request.name,
                    "year": current_year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing the draft",
            )


@router.get("/draft-next", response_model=NextDrafterResponse)
async def get_next_drafter():
    """
    Get the next player who should draft based on:
    1. Least number of picks for current year
    2. Lowest draft order number for current year
    3. Total picks not exceeding 20 for active people
    """
    with Timer() as timer:
        try:
            cwlogger.info(
                "GET_NEXT_DRAFTER_START",
                "Determining next drafter",
                data={"year": datetime.now().year}
            )

            # Use the optimized picks service
            picks_service = PicksService(DynamoDBClient())
            result = await picks_service.get_next_drafter()

            cwlogger.info(
                "GET_NEXT_DRAFTER_COMPLETE",
                f"Selected next drafter: {result['data']['player_name']}",
                data={
                    **result["data"],
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except Exception as e:
            cwlogger.error(
                "GET_NEXT_DRAFTER_ERROR",
                "Unexpected error determining next drafter",
                error=e,
                data={"elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while determining the next drafter",
            )


@router.get("/picks-counts", response_model=PicksCountResponse)
async def get_picks_counts(
    year: Optional[int] = Query(
        None,
        description="The year to get pick counts for (defaults to current year)",
    ),
):
    """
    Get pick counts for all players in a specific year.
    Returns a list of players with their pick counts (only counting picks for living people),
    sorted by draft order.
    """
    with Timer() as timer:
        try:
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "GET_PICKS_COUNTS_START",
                f"Retrieving pick counts for year {target_year}",
                data={"year": target_year},
            )

            # Use the optimized picks service
            picks_service = PicksService(DynamoDBClient())
            result = await picks_service.get_picks_counts(target_year)

            cwlogger.info(
                "GET_PICKS_COUNTS_COMPLETE",
                f"Retrieved pick counts for {len(result['data'])} players",
                data={
                    "year": target_year,
                    "player_count": len(result['data']),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except Exception as e:
            cwlogger.error(
                "GET_PICKS_COUNTS_ERROR",
                "Error retrieving pick counts",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving pick counts",
            )


@router.get("/picks/by-person/{person_id}", response_model=PaginatedPickDetailResponse)
async def get_picks_by_person(
    person_id: str = Path(..., description="The ID of the person to get picks for"),
    year: Optional[int] = Query(None, description="Filter picks by year (defaults to current year)"),
    limit: Optional[int] = Query(None, description="Limit the number of results returned. If not specified, pagination will be used."),
    page: Optional[int] = Query(1, description="Page number for paginated results", ge=1),
    page_size: Optional[int] = Query(10, description="Number of items per page", ge=1, le=100),
):
    """
    Get all picks for a specific person across all players.
    If year is specified, only returns picks for that year.
    If limit is specified, returns that many results.
    If limit is not specified, returns paginated results with default page size of 10.
    Returns detailed pick information including player and picked person details.
    """
    with Timer() as timer:
        try:
            # Verify person exists first to return a proper 404 if needed
            db = DynamoDBClient()
            person = await db.get_person(person_id)
            if not person:
                cwlogger.warning(
                    "GET_PICKS_BY_PERSON_ERROR",
                    "Person not found",
                    data={"person_id": person_id},
                )
                raise HTTPException(status_code=404, detail="Person not found")

            cwlogger.info(
                "GET_PICKS_BY_PERSON_START",
                f"Retrieving picks for person {person_id}",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "year": year,
                    "limit": limit,
                    "page": page,
                    "page_size": page_size
                },
            )

            # Use the optimized picks service with caching and batch operations
            picks_service = PicksService(db)
            result = await picks_service.get_picks_by_person(
                person_id=person_id,
                year=year,
                limit=limit,
                page=page,
                page_size=page_size
            )

            cwlogger.info(
                "GET_PICKS_BY_PERSON_COMPLETE",
                f"Retrieved {len(result['data'])} picks",
                data={
                    "person_id": person_id,
                    "person_name": person["name"],
                    "year": year,
                    "total_items": result["total"],
                    "returned_items": len(result["data"]),
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except HTTPException:
            raise
        except Exception as e:
            cwlogger.error(
                "GET_PICKS_BY_PERSON_ERROR",
                "Error retrieving picks",
                error=e,
                data={
                    "person_id": person_id,
                    "year": year,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving picks",
            )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    year: Optional[int] = Query(
        None,
        description="The year to get the leaderboard for (defaults to current year)",
    ),
):
    """
    Get the leaderboard for a specific year.
    Players are scored based on their dead celebrity picks:
    Score = sum of (50 + (100 - Age)) for each dead celebrity
    """
    with Timer() as timer:
        try:
            # Use current year if none specified
            target_year = year if year else datetime.now().year

            cwlogger.info(
                "LEADERBOARD_START",
                f"Calculating leaderboard for year {target_year}",
                data={"year": target_year},
            )

            # Use the optimized picks service with caching and batch operations
            picks_service = PicksService(DynamoDBClient())
            result = await picks_service.get_leaderboard(target_year)

            cwlogger.info(
                "LEADERBOARD_COMPLETE",
                f"Generated leaderboard for year {target_year}",
                data={
                    "year": target_year,
                    "player_count": len(result["data"]),
                    "top_score": result["data"][0].score if result["data"] else 0,
                    "elapsed_ms": timer.elapsed_ms,
                },
            )

            return result

        except Exception as e:
            cwlogger.error(
                "LEADERBOARD_ERROR",
                "Error generating leaderboard",
                error=e,
                data={"year": target_year, "elapsed_ms": timer.elapsed_ms},
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while generating the leaderboard",
            )


@router.get("/debug/person/{person_id}")
async def debug_person(
    person_id: str = Path(..., description="The ID of the person to debug"),
):
    """
    Debug endpoint to investigate person ID issues.
    This endpoint is for debugging purposes only.
    """
    try:
        db = DynamoDBClient()
        
        # First check if the person exists
        person = await db.get_person(person_id)
        
        # Scan for similar person IDs
        similar_persons = await db.scan_for_person(person_id)
        
        # Get all picks for this person
        picks_service = PicksService(db)
        picks_result = await picks_service.get_picks_by_person(
            person_id=person_id,
            limit=100  # Get a large number to ensure we see all picks
        )
        
        return {
            "person_exists": person is not None,
            "person_data": person,
            "similar_persons": similar_persons,
            "picks_result": picks_result
        }
        
    except Exception as e:
        print(f"DEBUG: Error in debug endpoint: {str(e)}")
        return {
            "error": str(e)
        }

@router.get("/debug/direct-picks/{person_id}")
async def debug_direct_picks(
    person_id: str = Path(..., description="The ID of the person to get picks for"),
):
    """
    Debug endpoint to directly get picks for a person without using the service layer.
    This endpoint is for debugging purposes only.
    """
    try:
        db = DynamoDBClient()
        
        # First check if the person exists
        person = await db.get_person(person_id)
        if not person:
            return {"error": "Person not found"}
        
        # Get all players
        players = await db.get_players()
        
        # Get picks for each player
        all_picks = []
        for player in players:
            player_picks = await db.get_player_picks(player["id"])
            for pick in player_picks:
                if pick["person_id"] == person_id or person_id in pick["person_id"]:
                    all_picks.append({
                        "player_id": player["id"],
                        "player_name": player["name"],
                        "pick_person_id": pick["person_id"],
                        "pick_person_name": person["name"],
                        "pick_timestamp": pick["timestamp"],
                        "year": pick["year"]
                    })
        
        return {
            "person_exists": True,
            "person_data": person,
            "picks_count": len(all_picks),
            "picks": all_picks
        }
        
    except Exception as e:
        print(f"DEBUG: Error in direct picks endpoint: {str(e)}")
        return {
            "error": str(e)
        }
