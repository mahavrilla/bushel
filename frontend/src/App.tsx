import { useState } from "react";

import { AddRecipe } from "./recipes/AddRecipe";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

type View =
  | { name: "list" }
  | { name: "add" }
  | { name: "detail"; id: number };

export function App() {
  const [view, setView] = useState<View>({ name: "list" });

  return (
    <main>
      <h1>Bushel</h1>
      <nav>
        <button onClick={() => setView({ name: "list" })}>Recipes</button>
        <button onClick={() => setView({ name: "add" })}>Add recipe</button>
      </nav>

      {view.name === "list" && (
        <RecipeList onOpen={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "add" && (
        <AddRecipe onCreated={(id) => setView({ name: "detail", id })} />
      )}
      {view.name === "detail" && <RecipeDetail recipeId={view.id} />}
    </main>
  );
}
