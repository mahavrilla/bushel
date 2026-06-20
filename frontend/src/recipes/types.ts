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
