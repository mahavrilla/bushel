import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

/**
 * Render a screen inside a MemoryRouter. Pass `path`/`initialEntries` when the screen
 * reads route params (e.g. path="/recipes/:id", initialEntries=["/recipes/1"]).
 */
export function renderWithRouter(
  ui: ReactElement,
  { path = "/", initialEntries = ["/"] }: { path?: string; initialEntries?: string[] } = {},
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path={path} element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}
