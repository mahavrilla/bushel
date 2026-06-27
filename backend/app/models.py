from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
    staples_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GroceryListItem(Base):
    __tablename__ = "grocery_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    total_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchase_qty: Mapped[int] = mapped_column(Integer, default=1)
    purchase_qty_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kroger_upc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_recipe_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    quantities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    pantry_status: Mapped[str] = mapped_column(String(20), default="needed")
    pantry_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


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


class GroceryListRecipe(Base):
    __tablename__ = "grocery_list_recipes"
    __table_args__ = (UniqueConstraint("list_id", "recipe_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    servings: Mapped[int] = mapped_column(Integer)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_store_location_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    home_store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Staple(Base):
    __tablename__ = "staples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), unique=True
    )
    auto_add: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GroceryListStaple(Base):
    __tablename__ = "grocery_list_staples"
    __table_args__ = (UniqueConstraint("list_id", "staple_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("grocery_lists.id", ondelete="CASCADE"))
    staple_id: Mapped[int] = mapped_column(ForeignKey("staples.id", ondelete="CASCADE"))


class PriceCache(Base):
    __tablename__ = "price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kroger_upc: Mapped[str] = mapped_column(String(50))
    location_id: Mapped[str] = mapped_column(String(50))
    regular_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    promo_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stock_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("kroger_upc", "location_id", name="uq_price_cache_upc_loc"),
    )
