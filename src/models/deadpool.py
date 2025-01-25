from pydantic import BaseModel
from typing import Optional, List, Dict, Any

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

class DeadpoolEntry(BaseModel):
    """
    Pydantic model for Deadpool data entries.
    This can be expanded based on the actual data structure needed.
    """
    id: str
    name: str
    description: Optional[str] = None
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

class SingleDeadpoolEntryResponse(BaseModel):
    """
    Pydantic model for API responses containing a single Deadpool entry.
    """
    message: str
    data: DeadpoolEntry

class DeadpoolResponse(BaseModel):
    """
    Pydantic model for API responses containing Deadpool data.
    """
    message: str
    data: List[DeadpoolEntry]

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
