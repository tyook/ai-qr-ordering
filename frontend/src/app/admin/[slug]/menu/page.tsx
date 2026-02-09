"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";

interface Variant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

interface Modifier {
  id: number;
  name: string;
  price_adjustment: string;
}

interface MenuItemFull {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  sort_order: number;
  variants: Variant[];
  modifiers: Modifier[];
}

interface Category {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
  items: MenuItemFull[];
}

interface FullMenu {
  restaurant_name: string;
  categories: Category[];
}

export default function MenuManagementPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [menu, setMenu] = useState<FullMenu | null>(null);
  const [loading, setLoading] = useState(true);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [showAddItem, setShowAddItem] = useState<number | null>(null);
  const [newItem, setNewItem] = useState({
    name: "",
    description: "",
    variantLabel: "Regular",
    variantPrice: "",
  });

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/admin/login");
      return;
    }
    loadMenu();
  }, [isAuthenticated, router]);

  const loadMenu = async () => {
    try {
      const data = await apiFetch<FullMenu>(
        `/api/restaurants/${params.slug}/menu/`
      );
      setMenu(data);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch(`/api/restaurants/${params.slug}/categories/`, {
      method: "POST",
      body: JSON.stringify({
        name: newCategoryName,
        sort_order: (menu?.categories.length || 0) + 1,
      }),
    });
    setNewCategoryName("");
    loadMenu();
  };

  const handleAddItem = async (categoryId: number) => {
    await apiFetch(`/api/restaurants/${params.slug}/items/`, {
      method: "POST",
      body: JSON.stringify({
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
      }),
    });
    setShowAddItem(null);
    setNewItem({ name: "", description: "", variantLabel: "Regular", variantPrice: "" });
    loadMenu();
  };

  const handleDeactivateItem = async (itemId: number) => {
    await apiFetch(`/api/restaurants/${params.slug}/items/${itemId}/`, {
      method: "DELETE",
    });
    loadMenu();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link
              href="/admin"
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
            <Button type="submit">Add Category</Button>
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
                    <Button onClick={() => handleAddItem(cat.id)}>
                      Save Item
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
