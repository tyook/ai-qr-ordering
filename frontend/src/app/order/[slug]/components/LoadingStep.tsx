"use client";

export function LoadingStep() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4" />
      <p className="text-lg text-muted-foreground">Understanding your order...</p>
    </div>
  );
}
