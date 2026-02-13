"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import type { MenuCategory } from "@/types";

interface MenuModalProps {
  categories: MenuCategory[];
  currency?: string;
}

export function MenuModal({ categories, currency = "$" }: MenuModalProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          View Menu
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Menu</DialogTitle>
        </DialogHeader>
        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">No menu items available.</p>
        ) : (
          <div className="space-y-6">
            {categories.map((category) => (
              <div key={category.id}>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
                  {category.name}
                </h3>
                <div className="space-y-3">
                  {category.items.map((item) => {
                    const defaultVariant = item.variants.find((v) => v.is_default) || item.variants[0];
                    return (
                      <div key={item.id} className="flex justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium leading-snug">{item.name}</p>
                          {item.description && (
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                          {item.variants.length > 1 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {item.variants.map((v) => (
                                <Badge key={v.id} variant="secondary" className="text-[10px] px-1.5 py-0">
                                  {v.label} {currency}{v.price}
                                </Badge>
                              ))}
                            </div>
                          )}
                          {item.modifiers.length > 0 && (
                            <p className="text-[10px] text-muted-foreground mt-1">
                              Add-ons: {item.modifiers.map((m) => m.name).join(", ")}
                            </p>
                          )}
                        </div>
                        {defaultVariant && item.variants.length === 1 && (
                          <span className="text-sm font-medium whitespace-nowrap">
                            {currency}{defaultVariant.price}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
                <Separator className="mt-4" />
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
