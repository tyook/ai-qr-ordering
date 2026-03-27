"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Upload, X, Loader2, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { ParsedMenu } from "@/types";
import { ParsedMenuEditor } from "./parsed-menu-editor";
import { useParseMenuImages, useSaveUploadedMenu } from "@/hooks/use-menu-upload";

interface MenuUploadModalProps {
  slug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hasExistingMenu: boolean;
}

type Step = "upload" | "parsing" | "review" | "success";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/heic", "image/heif"];
const MAX_FILES = 10;
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export function MenuUploadModal({ slug, open, onOpenChange, hasExistingMenu }: MenuUploadModalProps) {
  const [step, setStep] = useState<Step>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [parsedMenu, setParsedMenu] = useState<ParsedMenu | null>(null);
  const [mode, setMode] = useState<"overwrite" | "append">("overwrite");
  const [versionName, setVersionName] = useState("");

  const parseMutation = useParseMenuImages(slug);
  const saveMutation = useSaveUploadedMenu(slug);
  const { toast } = useToast();

  const reset = () => {
    setStep("upload");
    setFiles([]);
    setParsedMenu(null);
    setMode("overwrite");
    setVersionName("");
  };

  const handleClose = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
        ACCEPTED_TYPES.includes(f.type)
      );
      setFiles((prev) => [...prev, ...droppedFiles].slice(0, MAX_FILES));
    },
    []
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...selected].slice(0, MAX_FILES));
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const validateFiles = (): boolean => {
    for (const f of files) {
      if (!ACCEPTED_TYPES.includes(f.type)) {
        toast({ title: "Invalid file", description: `${f.name} is not a supported image type.`, variant: "destructive" });
        return false;
      }
      if (f.size > MAX_SIZE) {
        toast({ title: "File too large", description: `${f.name} exceeds 10MB limit.`, variant: "destructive" });
        return false;
      }
    }
    return true;
  };

  const handleParse = async () => {
    if (!validateFiles()) return;
    setStep("parsing");
    try {
      const result = await parseMutation.mutateAsync(files);
      setParsedMenu(result);
      setStep("review");
    } catch {
      toast({ title: "Parse failed", description: "Failed to parse menu photos. Please try again.", variant: "destructive" });
      setStep("upload");
    }
  };

  const handleSave = async () => {
    if (!parsedMenu) return;
    try {
      await saveMutation.mutateAsync({ menu: parsedMenu, mode, versionName: versionName || undefined });
      setStep("success");
      toast({ title: "Menu saved", description: "Your menu has been saved successfully." });
      setTimeout(() => handleClose(false), 1500);
    } catch {
      toast({ title: "Save failed", description: "Failed to save menu. Please try again.", variant: "destructive" });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === "upload" && "Upload Menu Photos"}
            {step === "parsing" && "Analyzing Menu..."}
            {step === "review" && "Review Parsed Menu"}
            {step === "success" && "Menu Saved!"}
          </DialogTitle>
        </DialogHeader>

        {step === "upload" && (
          <div className="space-y-4">
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => document.getElementById("menu-file-input")?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="font-medium">Drop menu photos here or click to browse</p>
              <p className="text-sm text-muted-foreground mt-1">
                Up to {MAX_FILES} photos. JPG, PNG, HEIC supported.
              </p>
              <input
                id="menu-file-input"
                type="file"
                multiple
                accept={ACCEPTED_TYPES.join(",")}
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            {files.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {files.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 bg-muted rounded-lg px-3 py-1.5 text-sm"
                  >
                    {f.name}
                    <button onClick={() => removeFile(i)}>
                      <X className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <Button
              onClick={handleParse}
              disabled={files.length === 0}
              className="w-full bg-purple-600 hover:bg-purple-700"
            >
              Parse Menu with AI
            </Button>
          </div>
        )}

        {step === "parsing" && (
          <div className="py-12 text-center">
            <Loader2 className="h-8 w-8 mx-auto mb-3 animate-spin text-purple-600" />
            <p className="font-medium">Analyzing your menu photos...</p>
            <p className="text-sm text-muted-foreground mt-1">
              This usually takes 10-15 seconds
            </p>
          </div>
        )}

        {step === "review" && parsedMenu && (
          <div className="space-y-4">
            <ParsedMenuEditor menu={parsedMenu} onChange={setParsedMenu} />

            {hasExistingMenu && (
              <div className="grid grid-cols-2 gap-3">
                <button
                  className={`border rounded-lg p-3 text-center transition-colors ${
                    mode === "overwrite"
                      ? "border-purple-600 bg-purple-50 dark:bg-purple-950"
                      : "border-border"
                  }`}
                  onClick={() => setMode("overwrite")}
                >
                  <p className="font-medium text-sm">Replace Entire Menu</p>
                  <p className="text-xs text-muted-foreground">
                    Discard current menu, use this one
                  </p>
                </button>
                <button
                  className={`border rounded-lg p-3 text-center transition-colors ${
                    mode === "append"
                      ? "border-purple-600 bg-purple-50 dark:bg-purple-950"
                      : "border-border"
                  }`}
                  onClick={() => setMode("append")}
                >
                  <p className="font-medium text-sm">Add to Existing Menu</p>
                  <p className="text-xs text-muted-foreground">
                    Keep current items, add these
                  </p>
                </button>
              </div>
            )}

            <Input
              value={versionName}
              onChange={(e) => setVersionName(e.target.value)}
              placeholder="Version name (e.g. Lunch Menu, Spring 2026)"
            />

            <Button
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="w-full"
            >
              {saveMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              )}
              Save Menu
            </Button>
          </div>
        )}

        {step === "success" && (
          <div className="py-12 text-center">
            <Check className="h-8 w-8 mx-auto mb-3 text-green-600" />
            <p className="font-medium">Menu saved successfully!</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
