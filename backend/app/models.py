from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_servings: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_purchase_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(Text)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    parse_source: Mapped[str] = mapped_column(String(30), default="library")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class IngredientProductMap(Base):
    __tablename__ = "ingredient_product_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    kroger_upc: Mapped[str] = mapped_column(String(50))
    kroger_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GroceryList(Base):
    __tablename__ = "grocery_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    store_location_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    total_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchase_qty: Mapped[int] = mapped_column(Integer, default=1)
    kroger_upc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_recipe_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    pantry_status: Mapped[str] = mapped_column(String(20), default="needed")


class PurchaseLog(Base):
    __tablename__ = "purchase_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    kroger_upc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("grocery_lists.id", ondelete="SET NULL"), nullable=True
    )


class KrogerAuth(Base):
    __tablename__ = "kroger_auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
