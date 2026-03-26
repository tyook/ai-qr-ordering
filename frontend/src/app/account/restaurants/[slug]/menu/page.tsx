"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import {
  useAdminMenu,
  useAddCategory,
  useAddMenuItem,
  useDeactivateMenuItem,
} from "@/hooks/use-admin-menu";

export default function MenuManagementPage() {
  const params = useParams<{ slug: string }>();
  const isAuthenticated = useRequireRestaurantAccess();
  const [newCategoryName, setNewCategoryName] = useState("");
  const [showAddItem, setShowAddItem] = useState<number | null>(null);
  const [newItem, setNewItem] = useState({
    name: "",
    description: "",
    variantLabel: "Regular",
    variantPrice: "",
  });

  const { data: menu, isLoading } = useAdminMenu(params.slug, isAuthenticated === true);
  const addCategory = useAddCategory(params.slug);
  const addMenuItem = useAddMenuItem(params.slug);
  const deactivateMenuItem = useDeactivateMenuItem(params.slug);

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    addCategory.mutate(
      {
        name: newCategoryName,
        sort_order: (menu?.categories.length || 0) + 1,
      },
      {
        onSuccess: () => setNewCategoryName(""),
      }
    );
  };

  const handleAddItem = (categoryId: number) => {
    addMenuItem.mutate(
      {
        category_id: categoryId,
        name: newItem.name,
        description: newItem.description,
        sort_order: 0,
        variants: [
          {
            label: newItem.variantLabel,
            price: newItem.variantPrice,
            is_default: true,
          },
        ],
        modifiers: [],
      },
      {
        onSuccess: () => {
          setShowAddItem(null);
          setNewItem({
            name: "",
            description: "",
            variantLabel: "Regular",
            variantPrice: "",
          });
        },
      }
    );
  };

  const handleDeactivateItem = (itemId: number) => {
    deactivateMenuItem.mutate(itemId);
  };

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link
              href="/account/restaurants"
              className="text-sm text-muted-foreground hover:underline"
            >
              Back to dashboard
            </Link>
            <h1 className="text-2xl font-bold">
              {menu?.restaurant_name} - Menu
            </h1>
          </div>
        </div>

        {/* Add Category */}
        <Card className="p-4 mb-6">
          <form onSubmit={handleAddCategory} className="flex gap-2">
            <Input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="New category name (e.g. Appetizers)"
              required
            />
            <Button type="submit" disabled={addCategory.isPending}>
              {addCategory.isPending ? "Adding..." : "Add Category"}
            </Button>
          </form>
        </Card>

        {/* Categories and Items */}
        {menu?.categories.map((cat) => (
          <div key={cat.id} className="mb-8">
            <h2 className="text-xl font-semibold mb-3">{cat.name}</h2>

            <div className="space-y-2 mb-4">
              {cat.items.map((item) => (
                <Card
                  key={item.id}
                  className={`p-4 ${!item.is_active ? "opacity-50" : ""}`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.name}</span>
                        {!item.is_active && (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.description}
                      </p>
                      <div className="text-sm mt-1">
                        {item.variants.map((v) => (
                          <span key={v.id} className="mr-3">
                            {v.label}: ${v.price}
                            {v.is_default && " (default)"}
                          </span>
                        ))}
                      </div>
                      {item.modifiers.length > 0 && (
                        <div className="text-sm text-muted-foreground mt-1">
                          Modifiers:{" "}
                          {item.modifiers
                            .map(
                              (m) =>
                                `${m.name} (+$${m.price_adjustment})`
                            )
                            .join(", ")}
                        </div>
                      )}
                    </div>
                    {item.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeactivateItem(item.id)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>

            {/* Add Item Form */}
            {showAddItem === cat.id ? (
              <Card className="p-4">
                <div className="space-y-3">
                  <div>
                    <Label>Item Name</Label>
                    <Input
                      value={newItem.name}
                      onChange={(e) =>
                        setNewItem({ ...newItem, name: e.target.value })
                      }
                      placeholder="e.g. Margherita Pizza"
                    />
                  </div>
                  <div>
                    <Label>Description</Label>
                    <Input
                      value={newItem.description}
                      onChange={(e) =>
                        setNewItem({ ...newItem, description: e.target.value })
                      }
                      placeholder="Classic pizza with tomato and mozzarella"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Size/Variant Label</Label>
                      <Input
                        value={newItem.variantLabel}
                        onChange={(e) =>
                          setNewItem({
                            ...newItem,
                            variantLabel: e.target.value,
                          })
                        }
                        placeholder="Regular"
                      />
                    </div>
                    <div>
                      <Label>Price</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={newItem.variantPrice}
                        onChange={(e) =>
                          setNewItem({
                            ...newItem,
                            variantPrice: e.target.value,
                          })
                        }
                        placeholder="12.99"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleAddItem(cat.id)}
                      disabled={addMenuItem.isPending}
                    >
                      {addMenuItem.isPending ? "Saving..." : "Save Item"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowAddItem(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </Card>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddItem(cat.id)}
              >
                + Add Item to {cat.name}
              </Button>
            )}

            <Separator className="mt-6" />
          </div>
        ))}
      </div>
    </div>
  );
}
