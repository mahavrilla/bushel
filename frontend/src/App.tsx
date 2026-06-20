import { useState } from "react";

import { AddRecipe } from "./recipes/AddRecipe";
import { GroceryList } from "./recipes/GroceryList";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

type View =
  | { name: "list" }
  | { name: "add" }
  | { name: "grocery" }
  | { name: "detail"; id: number };

export function App() {
  const [view, setView] = useState<View>({ name: "list" });

  return (
    <main>
      <h1>Bushel</h1>
      <nav>
        <button onClick={() => setView({ name: "list" })}>Recipes</button>
        <button onClick={() => setView({ name: "add" })}>Add recipe</button>
        <button onClick={() => setView({ name: "grocery" })}>Grocery List</button>
      </nav>

      {view.name === "list" && (
        <RecipeList onOpen={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "add" && (
        <AddRecipe onCreated={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "grocery" && <GroceryList />}
      {view.name === "detail" && <RecipeDetail recipeId={view.id} />}
    </main>
  );
}
