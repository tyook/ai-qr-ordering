"use client";

import { useEffect } from "react";
import { Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";
import { useTab } from "@/hooks/use-tab";
import type { OperatingHoursEntry, HolidayOverride } from "@/types";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatTime(time: string | null): string {
  if (!time) return "";
  const [h, m] = time.split(":");
  const hour = parseInt(h, 10);
  const ampm = hour >= 12 ? "PM" : "AM";
  const h12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  return `${h12}:${m} ${ampm}`;
}

function timeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

function getOpenStatus(
  hours: OperatingHoursEntry[],
  holidays: HolidayOverride[]
): { isOpen: boolean; label: string } {
  const now = new Date();
  const todayStr = now.toISOString().split("T")[0];
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  const holiday = holidays.find((h) => h.date === todayStr);
  if (holiday) {
    if (holiday.is_closed)
      return { isOpen: false, label: `Closed today (${holiday.label})` };
    const open = timeToMinutes(holiday.open_time ?? "0:0");
    const close = timeToMinutes(holiday.close_time ?? "0:0");
    const withinHours = currentMinutes >= open && currentMinutes < close;
    return withinHours
      ? { isOpen: true, label: `Open (${holiday.label} hours)` }
      : {
          isOpen: false,
          label: `Closed (${holiday.label}: ${formatTime(holiday.open_time)} – ${formatTime(holiday.close_time)})`,
        };
  }

  if (hours.length === 0) return { isOpen: true, label: "" };

  const jsDay = now.getDay();
  const dayIndex = jsDay === 0 ? 6 : jsDay - 1;
  const todaySlots = hours
    .filter((h) => h.day_of_week === dayIndex)
    .sort((a, b) => a.open_time.localeCompare(b.open_time));

  if (todaySlots.length === 0) return { isOpen: false, label: "Closed today" };

  for (const slot of todaySlots) {
    const open = timeToMinutes(slot.open_time);
    const close = timeToMinutes(slot.close_time);
    if (currentMinutes >= open && currentMinutes < close) {
      return { isOpen: true, label: `Open until ${formatTime(slot.close_time)}` };
    }
  }

  const nextSlot = todaySlots.find(
    (s) => timeToMinutes(s.open_time) > currentMinutes
  );
  if (nextSlot) {
    return {
      isOpen: false,
      label: `Closed (reopens ${formatTime(nextSlot.open_time)})`,
    };
  }

  return { isOpen: false, label: "Closed for the day" };
}

interface DaySchedule {
  day: number;
  slots: { open_time: string; close_time: string }[];
}

function groupByDay(hours: OperatingHoursEntry[]): DaySchedule[] {
  const map = new Map<number, { open_time: string; close_time: string }[]>();
  for (let i = 0; i < 7; i++) map.set(i, []);
  for (const h of hours) {
    map.get(h.day_of_week)?.push({ open_time: h.open_time, close_time: h.close_time });
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a - b)
    .map(([day, slots]) => ({
      day,
      slots: slots.sort((a, b) => a.open_time.localeCompare(b.open_time)),
    }));
}

interface WelcomeStepProps {
  restaurantName: string;
  slug: string;
  operatingHours: OperatingHoursEntry[];
  holidayOverrides: HolidayOverride[];
  acceptingOrders: boolean;
}

export function WelcomeStep({
  restaurantName,
  slug,
  operatingHours,
  holidayOverrides,
  acceptingOrders,
}: WelcomeStepProps) {
  const { setStep, paymentModel, tableIdentifier, setTabData } = useOrderStore();
  const { data: existingTab } = useTab(slug, tableIdentifier, paymentModel === "tab");

  useEffect(() => {
    if (existingTab) {
      setTabData(existingTab);
    }
  }, [existingTab, setTabData]);

  const status = getOpenStatus(operatingHours, holidayOverrides);
  const hasHours = operatingHours.length > 0;
  const grouped = hasHours ? groupByDay(operatingHours) : [];
  const isClosed = (hasHours && !status.isOpen) || !acceptingOrders;

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center">
      {/* Ambient glow orbs */}
      <div
        aria-hidden
        className="absolute top-1/4 left-1/4 -z-10 h-[350px] w-[350px] rounded-full animate-glow-pulse pointer-events-none bg-[radial-gradient(circle,rgba(217,119,6,0.12),transparent_70%)]"
      />
      <div
        aria-hidden
        className="absolute bottom-1/4 right-1/4 -z-10 h-[250px] w-[250px] rounded-full animate-glow-pulse pointer-events-none bg-[radial-gradient(circle,rgba(217,119,6,0.12),transparent_70%)]"
        style={{ animationDelay: "2s" }}
      />

      <div className="flex flex-col items-center gap-4 w-full max-w-sm">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground">
          Welcome to
        </p>
        <h1 className="gradient-text text-3xl font-bold tracking-tight">
          {restaurantName}
        </h1>

        {/* Open/Closed status */}
        {!acceptingOrders ? (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
            <span className="text-sm font-medium text-red-400">
              Not accepting orders right now
            </span>
          </div>
        ) : hasHours && status.label ? (
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                status.isOpen ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span
              className={`text-sm font-medium ${
                status.isOpen ? "text-green-500" : "text-red-400"
              }`}
            >
              {status.label}
            </span>
          </div>
        ) : null}

        <p className="text-muted-foreground text-sm">
          Type or speak your order in any language
        </p>

        {/* Operating hours schedule */}
        {hasHours && (
          <details className="w-full text-left">
            <summary className="flex items-center gap-1.5 cursor-pointer text-sm text-muted-foreground hover:text-foreground transition-colors">
              <Clock className="h-3.5 w-3.5" />
              View hours
            </summary>
            <div className="mt-2 rounded-lg bg-muted/50 p-3 space-y-1">
              {grouped.map((daySchedule) => {
                const jsDay = new Date().getDay();
                const todayIndex = jsDay === 0 ? 6 : jsDay - 1;
                const isToday = daySchedule.day === todayIndex;
                return (
                  <div
                    key={daySchedule.day}
                    className={`flex justify-between text-sm ${
                      isToday
                        ? "font-semibold text-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    <span>{DAY_LABELS[daySchedule.day]}</span>
                    <span>
                      {daySchedule.slots.length === 0
                        ? "Closed"
                        : daySchedule.slots
                            .map(
                              (s) =>
                                `${formatTime(s.open_time)} – ${formatTime(s.close_time)}`
                            )
                            .join(", ")}
                    </span>
                  </div>
                );
              })}
            </div>
          </details>
        )}

        {existingTab && (
          <div className="rounded-lg bg-zinc-800 p-4 text-center w-full">
            <p className="mb-2 text-muted-foreground">
              You have an open tab (${existingTab.total})
            </p>
            <Button
              variant="gradient"
              className="w-full"
              onClick={() => setStep("ordering")}
              disabled={isClosed}
            >
              Continue Ordering
            </Button>
            <button
              onClick={() => setStep("tab_review")}
              className="mt-2 w-full py-2 text-sm text-muted-foreground"
            >
              View Tab &amp; Pay
            </button>
          </div>
        )}
        <Button
          variant="gradient"
          size="lg"
          className="w-full max-w-sm glow-primary-lg"
          onClick={() => setStep("ordering")}
          disabled={isClosed}
        >
          {!acceptingOrders
            ? "Not Accepting Orders"
            : isClosed
              ? "Currently Closed"
              : "Start Ordering"}
        </Button>
      </div>
    </div>
  );
}
