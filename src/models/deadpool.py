from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union, Tuple
from datetime import datetime

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
    name: Optional[str] = None
    draft_order: Optional[int] = None
    year: Optional[int] = None
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
    metadata: Optional[dict] = None

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
