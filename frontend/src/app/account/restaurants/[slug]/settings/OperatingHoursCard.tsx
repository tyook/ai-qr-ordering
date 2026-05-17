"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Clock, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  useOperatingHours,
  useSaveOperatingHours,
  useHolidayOverrides,
  useCreateHolidayOverride,
  useDeleteHolidayOverride,
} from "@/hooks/use-operating-hours";
import type { OperatingHoursEntry, HolidayOverride } from "@/types";

const DAY_LABELS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

interface DaySlots {
  slots: { open_time: string; close_time: string }[];
}

function buildDayMap(entries: OperatingHoursEntry[]): DaySlots[] {
  const days: DaySlots[] = DAY_LABELS.map(() => ({ slots: [] }));
  for (const e of entries) {
    if (e.day_of_week >= 0 && e.day_of_week < 7) {
      days[e.day_of_week].slots.push({
        open_time: e.open_time,
        close_time: e.close_time,
      });
    }
  }
  for (const d of days) {
    d.slots.sort((a, b) => a.open_time.localeCompare(b.open_time));
  }
  return days;
}

function flattenToEntries(days: DaySlots[]): Omit<OperatingHoursEntry, "id">[] {
  const result: Omit<OperatingHoursEntry, "id">[] = [];
  days.forEach((day, i) => {
    for (const slot of day.slots) {
      result.push({
        day_of_week: i,
        open_time: slot.open_time,
        close_time: slot.close_time,
      });
    }
  });
  return result;
}

interface Props {
  slug: string;
}

export default function OperatingHoursCard({ slug }: Props) {
  const { toast } = useToast();
  const { data: savedHours } = useOperatingHours(slug);
  const saveHours = useSaveOperatingHours(slug);
  const { data: holidays = [] } = useHolidayOverrides(slug);
  const createHoliday = useCreateHolidayOverride(slug);
  const deleteHoliday = useDeleteHolidayOverride(slug);

  const [days, setDays] = useState<DaySlots[]>(() =>
    DAY_LABELS.map(() => ({ slots: [{ open_time: "09:00", close_time: "21:00" }] }))
  );
  const [initialized, setInitialized] = useState(false);

  const [newDate, setNewDate] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newHolidayClosed, setNewHolidayClosed] = useState(true);
  const [newHolidayOpen, setNewHolidayOpen] = useState("09:00");
  const [newHolidayClose, setNewHolidayClose] = useState("21:00");

  useEffect(() => {
    if (savedHours && !initialized) {
      if (savedHours.length > 0) {
        setDays(buildDayMap(savedHours));
      }
      setInitialized(true);
    }
  }, [savedHours, initialized]);

  const updateSlot = (
    dayIndex: number,
    slotIndex: number,
    field: "open_time" | "close_time",
    value: string
  ) => {
    setDays((prev) =>
      prev.map((day, di) =>
        di === dayIndex
          ? {
              slots: day.slots.map((s, si) =>
                si === slotIndex ? { ...s, [field]: value } : s
              ),
            }
          : day
      )
    );
  };

  const addSlot = (dayIndex: number) => {
    setDays((prev) =>
      prev.map((day, di) =>
        di === dayIndex
          ? { slots: [...day.slots, { open_time: "17:00", close_time: "22:00" }] }
          : day
      )
    );
  };

  const removeSlot = (dayIndex: number, slotIndex: number) => {
    setDays((prev) =>
      prev.map((day, di) =>
        di === dayIndex
          ? { slots: day.slots.filter((_, si) => si !== slotIndex) }
          : day
      )
    );
  };

  const toggleClosed = (dayIndex: number) => {
    setDays((prev) =>
      prev.map((day, di) => {
        if (di !== dayIndex) return day;
        if (day.slots.length > 0) return { slots: [] };
        return { slots: [{ open_time: "09:00", close_time: "21:00" }] };
      })
    );
  };

  const handleSaveHours = () => {
    const payload = flattenToEntries(days);
    saveHours.mutate(payload as OperatingHoursEntry[], {
      onSuccess: () => toast({ title: "Operating hours saved", variant: "success" }),
      onError: () =>
        toast({
          title: "Failed to save operating hours",
          variant: "destructive",
        }),
    });
  };

  const handleAddHoliday = () => {
    if (!newDate || !newLabel.trim()) return;
    const data: Omit<HolidayOverride, "id"> = {
      date: newDate,
      label: newLabel.trim(),
      is_closed: newHolidayClosed,
      open_time: newHolidayClosed ? null : newHolidayOpen,
      close_time: newHolidayClosed ? null : newHolidayClose,
    };
    createHoliday.mutate(data, {
      onSuccess: () => {
        setNewDate("");
        setNewLabel("");
        setNewHolidayClosed(true);
        setNewHolidayOpen("09:00");
        setNewHolidayClose("21:00");
        toast({ title: "Holiday added", variant: "success" });
      },
      onError: () =>
        toast({
          title: "Failed to add holiday",
          variant: "destructive",
        }),
    });
  };

  const handleDeleteHoliday = (holiday: HolidayOverride) => {
    if (
      !window.confirm(
        `Remove "${holiday.label}" (${holiday.date}) from holidays?`
      )
    )
      return;
    deleteHoliday.mutate(holiday.id);
  };

  return (
    <>
      {/* Weekly Operating Hours */}
      <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Operating Hours</h2>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Set your weekly schedule. Add multiple time slots per day for split
          shifts (e.g. lunch and dinner). These hours are shown to customers on
          your ordering page.
        </p>

        <div className="space-y-4">
          {days.map((day, dayIndex) => {
            const isClosed = day.slots.length === 0;
            return (
              <div key={dayIndex} className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="w-24 text-sm font-medium">
                    {DAY_LABELS[dayIndex]}
                  </span>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isClosed}
                      onChange={() => toggleClosed(dayIndex)}
                      className="rounded border-border"
                    />
                    <span className="text-sm text-muted-foreground">Closed</span>
                  </label>
                  {!isClosed && (
                    <button
                      onClick={() => addSlot(dayIndex)}
                      className="text-xs text-primary hover:underline flex items-center gap-0.5"
                    >
                      <Plus className="h-3 w-3" />
                      Add slot
                    </button>
                  )}
                </div>

                {day.slots.map((slot, slotIndex) => (
                  <div
                    key={slotIndex}
                    className="flex items-center gap-2 ml-28"
                  >
                    <Input
                      type="time"
                      value={slot.open_time}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIndex, "open_time", e.target.value)
                      }
                      className="w-32"
                    />
                    <span className="text-muted-foreground text-sm">to</span>
                    <Input
                      type="time"
                      value={slot.close_time}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIndex, "close_time", e.target.value)
                      }
                      className="w-32"
                    />
                    {day.slots.length > 1 && (
                      <button
                        onClick={() => removeSlot(dayIndex, slotIndex)}
                        className="p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                        title="Remove time slot"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        <Button
          variant="gradient"
          className="mt-4"
          onClick={handleSaveHours}
          disabled={saveHours.isPending}
        >
          {saveHours.isPending ? "Saving..." : "Save Hours"}
        </Button>
      </Card>

      {/* Holiday Overrides */}
      <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Holiday &amp; Closures</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Override specific dates for holidays, vacations, or special hours.
          These take priority over your weekly schedule.
        </p>

        {/* Add new holiday */}
        <div className="flex gap-2 mb-4 flex-wrap items-end">
          <div>
            <Label className="text-muted-foreground text-sm">Date</Label>
            <Input
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="w-40"
            />
          </div>
          <div className="flex-1 min-w-[140px]">
            <Label className="text-muted-foreground text-sm">Label</Label>
            <Input
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="e.g. Christmas"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer mt-5">
              <input
                type="checkbox"
                checked={newHolidayClosed}
                onChange={(e) => setNewHolidayClosed(e.target.checked)}
                className="rounded border-border"
              />
              <span className="text-sm text-muted-foreground">Closed</span>
            </label>
          </div>
          {!newHolidayClosed && (
            <>
              <div>
                <Label className="text-muted-foreground text-sm">Open</Label>
                <Input
                  type="time"
                  value={newHolidayOpen}
                  onChange={(e) => setNewHolidayOpen(e.target.value)}
                  className="w-32"
                />
              </div>
              <div>
                <Label className="text-muted-foreground text-sm">Close</Label>
                <Input
                  type="time"
                  value={newHolidayClose}
                  onChange={(e) => setNewHolidayClose(e.target.value)}
                  className="w-32"
                />
              </div>
            </>
          )}
          <Button
            variant="gradient"
            onClick={handleAddHoliday}
            disabled={
              createHoliday.isPending || !newDate || !newLabel.trim()
            }
          >
            <Plus className="h-4 w-4 mr-1" />
            {createHoliday.isPending ? "Adding..." : "Add"}
          </Button>
        </div>

        {createHoliday.isError && (
          <p className="text-sm text-destructive mb-4">
            Failed to add holiday. The date may already have an override.
          </p>
        )}

        {/* Holiday list */}
        {holidays.length > 0 ? (
          <div className="space-y-2">
            {holidays.map((h: HolidayOverride) => (
              <div
                key={h.id}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg group"
              >
                <div>
                  <span className="font-medium text-sm">{h.label}</span>
                  <span className="text-muted-foreground text-sm ml-2">
                    {h.date}
                  </span>
                  <span className="text-muted-foreground text-sm ml-2">
                    {h.is_closed
                      ? "— Closed"
                      : `— ${h.open_time} to ${h.close_time}`}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteHoliday(h)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                  title="Remove holiday"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            No holiday overrides set.
          </p>
        )}
      </Card>
    </>
  );
}
