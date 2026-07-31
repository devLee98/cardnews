from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Item

router = APIRouter(
    prefix="/items",
    tags=["items"],
)


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


@router.get("", response_model=list[ItemResponse])
async def read_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).order_by(Item.id))
    return result.scalars().all()


@router.get("/{item_id}", response_model=ItemResponse)
async def read_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Item, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(
    data: ItemCreate,
    db: AsyncSession = Depends(get_db),
):
    item = Item(
        name=data.name,
        description=data.description,
    )

    db.add(item)
    await db.commit()
    await db.refresh(item)

    return item