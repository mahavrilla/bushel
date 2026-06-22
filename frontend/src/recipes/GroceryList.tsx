import { useEffect, useState } from "react";

import { getList } from "../api";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { Spinner } from "../components/ui/Spinner";
import { CartTab } from "./CartTab";
import { ItemsTab } from "./ItemsTab";
import { StaplesSection } from "./StaplesSection";
import type { GroceryListData } from "./types";

type Tab = "items" | "staples" | "cart";

export function GroceryList() {
  const [list, setList] = useState<GroceryListData | null>(null);
  const [tab, setTab] = useState<Tab>("items");

  function reload() {
    getList().then(setList).catch(() => setList(null));
  }
  useEffect(reload, []);

  if (list === null)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );

  if (list.recipes.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title="Grocery list" />
        <EmptyState icon="🧺" message="No recipes on your list yet. Add some from the Recipes tab." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Grocery list" />
      <SegmentedControl
        options={[
          { value: "items", label: "Items" },
          { value: "staples", label: "Staples" },
          { value: "cart", label: "Cart" },
        ]}
        value={tab}
        onChange={(t) => {
          if (t === "items") reload();
          setTab(t);
        }}
      />
      {tab === "items" && <ItemsTab list={list} reload={reload} />}
      {tab === "staples" && <StaplesSection onChange={reload} />}
      {tab === "cart" && <CartTab />}
    </div>
  );
}
