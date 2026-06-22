export interface IngredientRead {
  id: number;
  raw_text: string;
  qty: number | null;
  unit: string | null;
  ingredient_id: number | null;
  ingredient_name: string | null;
  parse_source: string;
  needs_review: boolean;
}

export interface RecipeRead {
  id: number;
  title: string;
  servings: number;
  source_url: string | null;
  ingredients: IngredientRead[];
}

export interface RecipeSummary {
  id: number;
  title: string;
  servings: number;
}

export interface SubQuantity {
  qty: number | null;
  unit: string | null;
}

export interface ListItem {
  ingredient_id: number;
  ingredient_name: string | null;
  category: string | null;
  quantities: SubQuantity[];
  source_recipe_ids: number[];
  pantry_status: string;
}

export interface ListRecipe {
  recipe_id: number;
  title: string;
  servings: number;
  default_servings: number;
}

export interface GroceryListData {
  id: number;
  status: string;
  recipes: ListRecipe[];
  items: ListItem[];
}

export interface KrogerStatus {
  connected: boolean;
  expired: boolean;
}

export interface KrogerLocation {
  location_id: string;
  name: string;
  address: string;
}

export interface ProductChoice {
  upc: string;
  description: string;
  size: string | null;
  price: number | null;
  stock_level: string | null;
}

export interface MatchItem {
  item_id: number;
  ingredient_id: number;
  ingredient_name: string | null;
  total_qty: number | null;
  total_unit: string | null;
  purchase_qty: number;
  purchase_qty_estimated: boolean;
  kroger_upc: string | null;
  current: ProductChoice | null;
}

export interface MatchData {
  connected: boolean;
  store_location_id: string | null;
  store_name?: string | null;
  items: MatchItem[];
}

export interface ConfirmProductBody {
  kroger_upc: string;
  kroger_description?: string | null;
  package_size?: string | null;
}

export interface SendItemResult {
  upc: string;
  ok: boolean;
  error: string | null;
}

export interface SendResult {
  status: string;
  results: SendItemResult[];
}

export interface PantryItem {
  item_id: number;
  ingredient_id: number;
  ingredient_name: string | null;
  pantry_status: string;
  last_qty: number | null;
  last_unit: string | null;
  purchased_at: string | null;
  days_ago: number | null;
}

export interface PantryView {
  items: PantryItem[];
}
