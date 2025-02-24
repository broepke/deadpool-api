from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SearchResultAttributes(BaseModel):
    """
    Pydantic model for search result attributes.
    """
    name: str
    status: str
    metadata: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """
    Pydantic model for individual search result.
    """
    id: str
    type: str
    attributes: SearchResultAttributes
    score: float


class SearchResponse(BaseModel):
    """
    Pydantic model for search API response with pagination.
    """
    message: str
    data: List[SearchResult]
    metadata: Dict[str, Any]


# Rest of the existing models...
class PickDetail(BaseModel):
    """
    Pydantic model for detailed pick information including player and picked person details.
    """

    player_id: str
    player_name: str
    draft_order: int
    pick_person_id: Optional[str]
    pick_person_name: Optional[str]
    pick_person_age: Optional[int]
    pick_person_birth_date: Optional[str]
    pick_person_death_date: Optional[str]
    pick_timestamp: Optional[datetime]
    year: int


class PaginatedPickDetailResponse(BaseModel):
    """
    Pydantic model for paginated API responses containing detailed pick information.
    """
    message: str
    data: List[PickDetail]
    total: int
    page: int
    page_size: int
    total_pages: int


class PickDetailResponse(BaseModel):
    """
    Pydantic model for API responses containing detailed pick information.
    """
    message: str
    data: List[PickDetail]


class PlayerPick(BaseModel):
    """
    Pydantic model for Player Pick data.
    """

    person_id: str
    year: int
    timestamp: datetime


class PlayerPickResponse(BaseModel):
    """
    Pydantic model for API responses containing Player Pick data.
    """

    message: str
    data: List[PlayerPick]


class PlayerPickUpdate(BaseModel):
    """
    Pydantic model for updating Player Pick data.
    """

    person_id: str
    year: int


class DraftOrder(BaseModel):
    """
    Pydantic model for Draft Order data.
    """

    player_id: str
    draft_order: int
    year: int


class DraftOrderListResponse(BaseModel):
    """
    Pydantic model for API responses containing Draft Order data.
    """

    message: str
    data: List[DraftOrder]


class RouteInfo(BaseModel):
    """
    Pydantic model for API route information.
    """

    path: str
    name: str


class RoutesResponse(BaseModel):
    """
    Pydantic model for API routes response.
    """

    message: str
    routes: List[RouteInfo]


class PlayerUpdate(BaseModel):
    """
    Pydantic model for updating Player data.
    """
    draft_order: Optional[int] = None
    year: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class PlayerProfileUpdate(BaseModel):
    """
    Pydantic model for updating Player Profile data.
    """
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    phone_verified: Optional[bool] = None
    sms_notifications_enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class PersonUpdate(BaseModel):
    """
    Pydantic model for updating Person data.
    """

    name: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Player(BaseModel):
    """
    Pydantic model for Player data.
    """

    id: str
    name: str
    draft_order: int
    year: int
    phone_number: Optional[str] = None
    phone_verified: Optional[bool] = None
    sms_notifications_enabled: Optional[bool] = None


class Person(BaseModel):
    """
    Pydantic model for Person data.
    """

    id: str
    name: str
    status: str
    metadata: Optional[dict] = None


class SinglePlayerResponse(BaseModel):
    """
    Pydantic model for API responses containing a single Player.
    """

    message: str
    data: Player


class SinglePersonResponse(BaseModel):
    """
    Pydantic model for API responses containing a single Person.
    """

    message: str
    data: Person


class PlayerResponse(BaseModel):
    """
    Pydantic model for API responses containing Player data.
    """

    message: str
    data: List[Player]


class PaginatedPersonResponse(BaseModel):
    """
    Pydantic model for paginated API responses containing Person data.
    """
    message: str
    data: List[Person]
    total: int
    page: int
    page_size: int
    total_pages: int


class PersonResponse(BaseModel):
    """
    Pydantic model for API responses containing Person data.
    """
    message: str
    data: List[Person]


class NextDrafterResponse(BaseModel):
    """
    Pydantic model for API response containing next drafter information.
    """

    message: str
    data: Dict[str, Any]


class LeaderboardEntry(BaseModel):
    """
    Pydantic model for a player's leaderboard entry.
    """
    
    player_id: str
    player_name: str
    score: int


class DraftRequest(BaseModel):
    """
    Pydantic model for draft request data.
    """
    name: str
    player_id: str


class DraftResponse(BaseModel):
    """
    Pydantic model for draft response data.
    """
    message: str
    data: Dict[str, Any]


class PicksCountEntry(BaseModel):
    """
    Pydantic model for a player's picks count entry.
    """
    
    player_id: str
    player_name: str
    draft_order: int
    pick_count: int
    year: int


class PicksCountResponse(BaseModel):
    """
    Pydantic model for API response containing picks count data.
    """
    
    message: str
    data: List[PicksCountEntry]


class PhoneVerificationRequest(BaseModel):
    """
    Pydantic model for requesting phone verification.
    """
    phone_number: str


class PhoneVerificationResponse(BaseModel):
    """
    Pydantic model for phone verification response.
    """
    message: str
    data: Dict[str, Any]


class CodeVerificationRequest(BaseModel):
    """
    Pydantic model for verifying a phone code.
    """
    code: str


class CodeVerificationResponse(BaseModel):
    """
    Pydantic model for code verification response.
    """
    message: str
    data: Dict[str, Any]


class ProfileUpdateResponse(BaseModel):
    """
    Pydantic model for profile update response.
    """
    message: str


class LeaderboardResponse(BaseModel):
    """
    Pydantic model for API response containing leaderboard data.
    """
    
    message: str
    data: List[LeaderboardEntry]
