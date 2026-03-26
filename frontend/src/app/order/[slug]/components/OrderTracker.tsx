"use client";

import { useOrderQueue } from "@/hooks/use-order-queue";

interface OrderTrackerProps {
  slug: string;
  orderId: string;
}

const STEPS = [
  { key: "confirmed", label: "Confirmed" },
  { key: "preparing", label: "Preparing" },
  { key: "ready", label: "Ready" },
  { key: "completed", label: "Completed" },
] as const;

const STATUS_ORDER = ["confirmed", "preparing", "ready", "completed"];

function getStepIndex(status: string | null): number {
  if (!status) return -1;
  return STATUS_ORDER.indexOf(status);
}

export function OrderTracker({ slug, orderId }: OrderTrackerProps) {
  const { queuePosition, estimatedWait, status, isConnected } = useOrderQueue({
    slug,
    orderId,
    enabled: true,
  });

  const currentIndex = getStepIndex(status);
  const isReady = status === "ready";
  const isCompleted = status === "completed";

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Progress bar */}
      <div className="flex items-center justify-between mb-6 px-2">
        {STEPS.map((step, i) => {
          const isActive = i === currentIndex;
          const isDone = i < currentIndex;
          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                    isDone
                      ? "bg-green-500 text-white"
                      : isActive
                        ? "bg-blue-500 text-white"
                        : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {isDone ? "\u2713" : i + 1}
                </div>
                <span
                  className={`text-xs mt-1 ${
                    isDone
                      ? "text-green-600 font-semibold"
                      : isActive
                        ? "text-blue-600 font-semibold"
                        : "text-gray-400"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 mb-5 ${
                    i < currentIndex ? "bg-green-500" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Queue info */}
      {isReady ? (
        <div className="bg-green-50 rounded-xl p-5 text-center mb-4">
          <div className="text-lg font-bold text-green-800">Your order is ready for pickup!</div>
        </div>
      ) : isCompleted ? (
        <div className="bg-gray-50 rounded-xl p-5 text-center mb-4">
          <div className="text-lg font-bold text-gray-800">Order complete. Thank you!</div>
        </div>
      ) : queuePosition !== null ? (
        <div className="bg-gray-50 rounded-xl p-5 text-center mb-4">
          <div className="text-3xl font-extrabold text-gray-900">#{queuePosition}</div>
          <div className="text-sm text-gray-500 mb-3">in line</div>
          {estimatedWait !== null && (
            <>
              <div className="w-12 h-px bg-gray-300 mx-auto mb-3" />
              <div className="text-xl font-bold text-yellow-700">~{estimatedWait} min</div>
              <div className="text-sm text-gray-500">estimated wait</div>
            </>
          )}
        </div>
      ) : null}

      {/* Connection indicator */}
      <div className="flex items-center justify-center gap-1.5 text-xs">
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-gray-400"}`}
        />
        <span className={isConnected ? "text-green-600" : "text-gray-500"}>
          {isConnected ? "Live updates active" : "Updating..."}
        </span>
      </div>
    </div>
  );
}
