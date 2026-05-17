"use client";

import { useState } from "react";
import { Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useAcceptingOrders,
  useToggleAcceptingOrders,
} from "@/hooks/use-accepting-orders";

interface PauseOrdersButtonProps {
  slug: string;
}

export function PauseOrdersButton({ slug }: PauseOrdersButtonProps) {
  const { data } = useAcceptingOrders(slug);
  const toggle = useToggleAcceptingOrders(slug);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [autoResume, setAutoResume] = useState(true);

  const accepting = data?.accepting_orders ?? true;

  const handleConfirm = () => {
    if (accepting) {
      toggle.mutate(
        { accepting_orders: false, auto_resume_orders: autoResume },
        { onSuccess: () => setDialogOpen(false) }
      );
    } else {
      toggle.mutate(
        { accepting_orders: true },
        { onSuccess: () => setDialogOpen(false) }
      );
    }
  };

  const handleOpen = () => {
    setAutoResume(data?.auto_resume_orders ?? true);
    setDialogOpen(true);
  };

  return (
    <>
      <Button
        variant={accepting ? "outline" : "default"}
        size="sm"
        onClick={handleOpen}
        className={
          accepting
            ? ""
            : "bg-green-600 hover:bg-green-700 text-white"
        }
      >
        {accepting ? (
          <>
            <Pause className="w-4 h-4 mr-1.5" />
            Pause Orders
          </>
        ) : (
          <>
            <Play className="w-4 h-4 mr-1.5" />
            Resume Orders
          </>
        )}
      </Button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {accepting ? "Pause New Orders?" : "Resume Orders?"}
            </DialogTitle>
            <DialogDescription>
              {accepting
                ? "Customers will see that you're not accepting orders and won't be able to place new ones."
                : "Customers will be able to place orders again."}
            </DialogDescription>
          </DialogHeader>

          {accepting && (
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={autoResume}
                onCheckedChange={(v) => setAutoResume(v === true)}
              />
              <span className="text-sm text-muted-foreground">
                Automatically resume on next business day
              </span>
            </label>
          )}

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant={accepting ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={toggle.isPending}
              className={
                accepting
                  ? ""
                  : "bg-green-600 hover:bg-green-700 text-white"
              }
            >
              {toggle.isPending
                ? "Saving..."
                : accepting
                  ? "Pause Orders"
                  : "Resume Orders"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
