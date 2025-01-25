from pydantic import BaseModel
from typing import Optional, List

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
