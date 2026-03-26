"use client";

import { useRestaurantBusyness } from "@/hooks/use-restaurant-busyness";

interface BusynessBannerProps {
  slug: string;
}

const BUSYNESS_CONFIG = {
  green: {
    emoji: "\u{1F7E2}",
    label: "Short wait",
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-800",
  },
  yellow: {
    emoji: "\u{1F7E1}",
    label: "Moderate wait",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-800",
  },
  red: {
    emoji: "\u{1F534}",
    label: "Busy",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-800",
  },
} as const;

export function BusynessBanner({ slug }: BusynessBannerProps) {
  const { busyness, estimatedWait, isLoading, error } = useRestaurantBusyness(slug);

  if (isLoading || error || !busyness) return null;

  const config = BUSYNESS_CONFIG[busyness];

  return (
    <div className={`${config.bg} ${config.border} border rounded-lg p-3 mb-4 flex items-center gap-3`}>
      <span className="text-xl">{config.emoji}</span>
      <div>
        <div className={`font-semibold text-sm ${config.text}`}>{config.label}</div>
        <div className="text-xs text-gray-600">
          {estimatedWait
            ? `~${estimatedWait} min estimated wait right now`
            : "No wait right now"}
        </div>
      </div>
    </div>
  );
}
