import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AddRecipe } from "./recipes/AddRecipe";
import { GroceryList } from "./recipes/GroceryList";
import { KrogerSetup } from "./recipes/KrogerSetup";
import { RecipeDetail } from "./recipes/RecipeDetail";
import { RecipeList } from "./recipes/RecipeList";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<RecipeList />} />
        <Route path="recipes/new" element={<AddRecipe />} />
        <Route path="recipes/:id" element={<RecipeDetail />} />
        <Route path="list" element={<GroceryList />} />
        <Route path="kroger" element={<KrogerSetup />} />
      </Route>
    </Routes>
  );
}
