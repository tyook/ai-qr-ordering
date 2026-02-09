"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const params = useParams<{ slug: string }>();
  const [tableIds, setTableIds] = useState("");
  const [generatedTables, setGeneratedTables] = useState<string[]>([]);

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

  const handleGenerate = () => {
    const ids = tableIds
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    setGeneratedTables(ids);
  };

  const getOrderUrl = (tableId?: string) => {
    if (tableId) {
      return `${baseUrl}/order/${params.slug}/${tableId}`;
    }
    return `${baseUrl}/order/${params.slug}`;
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Settings & QR Codes</h1>

        {/* Counter QR (no table) */}
        <Card className="p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            Counter / Pickup QR Code
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            For counter service without table numbers.
          </p>
          <div className="flex items-center gap-6">
            <QRCodeSVG value={getOrderUrl()} size={150} />
            <div>
              <p className="text-sm font-mono break-all">{getOrderUrl()}</p>
            </div>
          </div>
        </Card>

        {/* Table QR Generator */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Table QR Codes</h2>
          <div className="flex gap-2 mb-4">
            <div className="flex-1">
              <Label>Table IDs (comma-separated)</Label>
              <Input
                value={tableIds}
                onChange={(e) => setTableIds(e.target.value)}
                placeholder="1, 2, 3, 4, 5"
              />
            </div>
            <Button className="mt-6" onClick={handleGenerate}>
              Generate
            </Button>
          </div>

          {generatedTables.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mt-6">
              {generatedTables.map((tableId) => (
                <div
                  key={tableId}
                  className="flex flex-col items-center p-4 border rounded-lg"
                >
                  <QRCodeSVG value={getOrderUrl(tableId)} size={120} />
                  <p className="font-semibold mt-2">Table {tableId}</p>
                  <p className="text-xs text-muted-foreground break-all text-center">
                    {getOrderUrl(tableId)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
