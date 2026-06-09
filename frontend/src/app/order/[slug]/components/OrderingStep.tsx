"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { MenuBrowseTab } from "./MenuBrowseTab";
import { VoiceChatTab } from "./VoiceChatTab";
import { CartBottomBar } from "./CartBottomBar";
import type { MenuCategory } from "@/types";

interface OrderingStepProps {
  slug: string;
  categories: MenuCategory[];
  taxRate: string;
}

type ActiveTab = "menu" | "voice";

export function OrderingStep({ slug, categories, taxRate }: OrderingStepProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("menu");

  return (
    <div
      className="flex flex-col bg-background"
      style={{ height: "100dvh" }}
    >
      {/* Tab bar */}
      <div className="shrink-0 border-b border-border bg-background/95 backdrop-blur-sm pt-14 px-4">
        <div className="max-w-lg mx-auto flex">
          <button
            onClick={() => setActiveTab("menu")}
            className={cn(
              "flex-1 py-3 text-sm font-medium text-center transition-colors border-b-2",
              activeTab === "menu"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            Menu
          </button>
          <button
            onClick={() => setActiveTab("voice")}
            className={cn(
              "flex-1 py-3 text-sm font-medium text-center transition-colors border-b-2",
              activeTab === "voice"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            Voice / Chat
          </button>
        </div>
      </div>

      {/* Tab content — both kept mounted to preserve state */}
      <div className="flex-1 overflow-hidden relative">
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto transition-opacity duration-200",
            activeTab === "menu" ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none",
          )}
        >
          <div className="max-w-lg mx-auto">
            <MenuBrowseTab categories={categories} />
          </div>
        </div>
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto transition-opacity duration-200",
            activeTab === "voice" ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none",
          )}
        >
          <div className="max-w-lg mx-auto">
            <VoiceChatTab slug={slug} />
          </div>
        </div>
      </div>

      {/* Persistent cart bottom bar */}
      <CartBottomBar taxRate={taxRate} />
    </div>
  );
}
