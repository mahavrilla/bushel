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
