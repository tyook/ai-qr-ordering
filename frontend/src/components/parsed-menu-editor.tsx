"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, ChevronDown, ChevronRight } from "lucide-react";
import type { ParsedMenu, ParsedMenuCategory, ParsedMenuItem, ParsedMenuVariant } from "@/types";

interface ParsedMenuEditorProps {
  menu: ParsedMenu;
  onChange: (menu: ParsedMenu) => void;
}

export function ParsedMenuEditor({ menu, onChange }: ParsedMenuEditorProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<number>>(new Set());

  const toggleCategory = (index: number) => {
    const next = new Set(collapsedCategories);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setCollapsedCategories(next);
  };

  const updateCategory = (catIndex: number, updates: Partial<ParsedMenuCategory>) => {
    const categories = [...menu.categories];
    categories[catIndex] = { ...categories[catIndex], ...updates };
    onChange({ categories });
  };

  const removeCategory = (catIndex: number) => {
    onChange({ categories: menu.categories.filter((_, i) => i !== catIndex) });
  };

  const updateItem = (catIndex: number, itemIndex: number, updates: Partial<ParsedMenuItem>) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    items[itemIndex] = { ...items[itemIndex], ...updates };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const removeItem = (catIndex: number, itemIndex: number) => {
    const categories = [...menu.categories];
    categories[catIndex] = {
      ...categories[catIndex],
      items: categories[catIndex].items.filter((_, i) => i !== itemIndex),
    };
    onChange({ categories });
  };

  const updateVariant = (
    catIndex: number,
    itemIndex: number,
    varIndex: number,
    updates: Partial<ParsedMenuVariant>
  ) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    const variants = [...items[itemIndex].variants];
    variants[varIndex] = { ...variants[varIndex], ...updates };
    items[itemIndex] = { ...items[itemIndex], variants };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const totalItems = menu.categories.reduce((sum, cat) => sum + cat.items.length, 0);

  return (
    <div>
      <p className="text-sm text-muted-foreground mb-4">
        AI found <strong>{menu.categories.length}</strong> categories and{" "}
        <strong>{totalItems}</strong> items. Edit anything that looks off.
      </p>

      <div className="space-y-3">
        {menu.categories.map((cat, catIndex) => (
          <div key={catIndex} className="border rounded-lg">
            <div className="flex items-center justify-between bg-muted/50 px-4 py-2">
              <button
                className="flex items-center gap-2 font-semibold text-sm"
                onClick={() => toggleCategory(catIndex)}
              >
                {collapsedCategories.has(catIndex) ? (
                  <ChevronRight className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
                <Input
                  value={cat.name}
                  onChange={(e) => updateCategory(catIndex, { name: e.target.value })}
                  className="h-7 w-48 font-semibold"
                  onClick={(e) => e.stopPropagation()}
                />
                <span className="text-muted-foreground font-normal">
                  ({cat.items.length} items)
                </span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => removeCategory(catIndex)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            {!collapsedCategories.has(catIndex) && (
              <div className="divide-y">
                {cat.items.map((item, itemIndex) => (
                  <div key={itemIndex} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 space-y-1">
                        <Input
                          value={item.name}
                          onChange={(e) =>
                            updateItem(catIndex, itemIndex, { name: e.target.value })
                          }
                          className="h-7 font-medium"
                        />
                        <Input
                          value={item.description || ""}
                          onChange={(e) =>
                            updateItem(catIndex, itemIndex, {
                              description: e.target.value || null,
                            })
                          }
                          placeholder="Description (optional)"
                          className="h-7 text-sm text-muted-foreground"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        {item.variants.map((variant, varIndex) => (
                          <div key={varIndex} className="flex items-center gap-1">
                            {item.variants.length > 1 && (
                              <Input
                                value={variant.label}
                                onChange={(e) =>
                                  updateVariant(catIndex, itemIndex, varIndex, {
                                    label: e.target.value,
                                  })
                                }
                                className="h-7 w-20 text-xs"
                              />
                            )}
                            <div className="flex items-center">
                              <span className="text-sm">$</span>
                              <Input
                                value={variant.price}
                                onChange={(e) =>
                                  updateVariant(catIndex, itemIndex, varIndex, {
                                    price: e.target.value,
                                  })
                                }
                                className="h-7 w-20 text-right"
                              />
                            </div>
                          </div>
                        ))}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => removeItem(catIndex, itemIndex)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
