from pydantic import BaseModel
from typing import Optional, List

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
