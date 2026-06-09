"use client";

import { useState } from "react";
import { useParams, useSearchParams, useRouter, usePathname } from "next/navigation";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Trash2, Plus, CheckCircle2, AlertTriangle, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useRestaurant } from "@/hooks/use-restaurant";
import { useUpdateTaxRate } from "@/hooks/use-update-tax-rate";
import { useTables, useCreateTable, useDeleteTable } from "@/hooks/use-tables";
import { useConnectOnboardingLink, useConnectOnboardingStatus } from "@/hooks/use-connect-onboarding";
import { useToast } from "@/hooks/use-toast";
import { apiFetch } from "@/lib/api";
import type { Table } from "@/types";
import OperatingHoursCard from "./OperatingHoursCard";

export default function SettingsPage() {
  const params = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { toast } = useToast();
  const isAuthenticated = useRequireRestaurantAccess();
  const [taxRate, setTaxRate] = useState<string | null>(null);
  const [taxMessage, setTaxMessage] = useState("");
  const [paymentModel, setPaymentModel] = useState<string | null>(null);
  const [pmMessage, setPmMessage] = useState("");
  const [newTableName, setNewTableName] = useState("");
  const [newTableNumber, setNewTableNumber] = useState("");

  const { data: restaurant } = useRestaurant(params.slug);
  const updateTaxRate = useUpdateTaxRate(params.slug);
  const { data: tables = [], isLoading: tablesLoading, error: tablesError } = useTables(params.slug);
  const createTable = useCreateTable(params.slug);
  const deleteTable = useDeleteTable(params.slug);

  // Payment setup (Stripe Connect)
  const isStripeReturn = searchParams.get("stripe_return") === "true";
  const isStripeRefresh = searchParams.get("stripe_refresh") === "true";
  const { data: connectStatus, isLoading: connectLoading } = useConnectOnboardingStatus(params.slug, true);
  const connectLink = useConnectOnboardingLink(params.slug);
  const paymentReady = connectStatus?.onboarding_complete ?? false;

  // Clean Stripe query params after return
  const [stripeCleaned, setStripeCleaned] = useState(false);
  if ((isStripeReturn || isStripeRefresh) && connectStatus && !stripeCleaned) {
    setStripeCleaned(true);
    router.replace(pathname);
  }

  const handlePaymentSetup = () => {
    const baseUrl = window.location.origin;
    const returnUrl = `${baseUrl}${pathname}?stripe_return=true`;
    const refreshUrl = `${baseUrl}${pathname}?stripe_refresh=true`;

    connectLink.mutate(
      { returnUrl, refreshUrl },
      {
        onSuccess: (data) => {
          window.location.href = data.url;
        },
        onError: (err) => {
          toast({
            title: "Failed to start payment setup",
            description: err instanceof Error ? err.message : "Unknown error",
            variant: "destructive",
          });
        },
      }
    );
  };

  const displayTaxRate = taxRate ?? restaurant?.tax_rate ?? "";
  const displayPaymentModel = paymentModel ?? restaurant?.payment_model ?? "upfront";

  const handleSavePaymentModel = async () => {
    setPmMessage("");
    try {
      await apiFetch(`/api/restaurants/${params.slug}/`, {
        method: "PATCH",
        body: JSON.stringify({ payment_model: displayPaymentModel }),
      });
      setPmMessage("Saved");
    } catch {
      setPmMessage("Failed to save");
    }
  };

  const handleSaveTax = () => {
    setTaxMessage("");
    updateTaxRate.mutate(displayTaxRate, {
      onSuccess: () => setTaxMessage("Saved"),
      onError: () => setTaxMessage("Failed to save"),
    });
  };

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

  const getOrderUrl = (tableNumber?: string) => {
    if (tableNumber) {
      return `${baseUrl}/order/${params.slug}/${tableNumber}`;
    }
    return `${baseUrl}/order/${params.slug}`;
  };

  const handlePrintAllQR = () => {
    if (activeTables.length === 0) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    const tableEntries = activeTables.map((table: Table) => ({
      url: getOrderUrl(table.number),
      label: `${table.name} (#${table.number})`,
    }));

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>All Table QR Codes</title>
          <style>
            body { margin: 0; font-family: sans-serif; }
            .page {
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              min-height: 100vh;
              page-break-after: always;
            }
            .page:last-child { page-break-after: auto; }
            h1 { font-size: 24px; margin-bottom: 24px; }
            p { font-size: 14px; color: #666; margin-top: 16px; word-break: break-all; }
          </style>
        </head>
        <body>
          ${tableEntries.map((_, i) => `
            <div class="page">
              <h1 id="label-${i}"></h1>
              <div id="qr-${i}"></div>
              <p id="url-${i}"></p>
            </div>
          `).join("")}
        </body>
      </html>
    `);
    printWindow.document.close();

    tableEntries.forEach((entry, i) => {
      const labelEl = printWindow.document.getElementById(`label-${i}`);
      const urlEl = printWindow.document.getElementById(`url-${i}`);
      if (labelEl) labelEl.textContent = entry.label;
      if (urlEl) urlEl.textContent = entry.url;

      const container = printWindow.document.getElementById(`qr-${i}`);
      if (container) {
        const tempDiv = document.createElement("div");
        document.body.appendChild(tempDiv);
        const root = createRoot(tempDiv);
        flushSync(() => {
          root.render(<QRCodeSVG value={entry.url} size={300} />);
        });
        container.innerHTML = tempDiv.innerHTML;
        root.unmount();
        document.body.removeChild(tempDiv);
      }
    });

    printWindow.focus();
    printWindow.print();
  };

  const handlePrintQR = (url: string, label: string) => {
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>QR Code - ${label}</title>
          <style>
            body {
              margin: 0;
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              min-height: 100vh;
              font-family: sans-serif;
            }
            h1 { font-size: 24px; margin-bottom: 24px; }
            p { font-size: 14px; color: #666; margin-top: 16px; word-break: break-all; }
          </style>
        </head>
        <body>
          <h1>${label}</h1>
          <div id="qr"></div>
          <p>${url}</p>
        </body>
      </html>
    `);
    printWindow.document.close();
    // Render QR into the print window
    const container = printWindow.document.getElementById("qr");
    if (container) {
      const tempDiv = document.createElement("div");
      document.body.appendChild(tempDiv);
      const root = createRoot(tempDiv);
      flushSync(() => {
        root.render(
          <QRCodeSVG value={url} size={300} />
        );
      });
      container.innerHTML = tempDiv.innerHTML;
      root.unmount();
      document.body.removeChild(tempDiv);
    }
    printWindow.focus();
    printWindow.print();
  };

  const handleAddTable = () => {
    const name = newTableName.trim();
    const number = newTableNumber.trim();
    if (!name || !number) return;
    createTable.mutate(
      { name, number },
      {
        onSuccess: () => {
          setNewTableName("");
          setNewTableNumber("");
        },
      }
    );
  };

  const handleDeleteTable = (table: Table) => {
    if (!window.confirm(`Delete table "${table.name}" (#${table.number})? Existing QR codes for this table will stop working.`)) {
      return;
    }
    deleteTable.mutate(table.id);
  };

  if (isAuthenticated === null) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  const activeTables = tables.filter((t: Table) => t.is_active);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Settings & QR Codes</h1>

        {/* Payment Setup */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Payment Setup</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Connect your bank account via Stripe to receive payouts from customer orders.
            Payment must be set up before QR codes can be generated.
          </p>
          {connectLoading ? (
            <div className="flex items-center gap-2 py-4">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary" />
              <span className="text-sm text-muted-foreground">Checking payment status...</span>
            </div>
          ) : paymentReady ? (
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <span className="text-green-600 font-medium">Payments connected</span>
              {connectStatus?.charges_enabled && (
                <span className="text-xs text-muted-foreground ml-2">Charges enabled</span>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {isStripeReturn && !paymentReady && (
                <div className="flex items-center gap-2 text-yellow-600 mb-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-sm">Payment setup was not completed. Please try again.</span>
                </div>
              )}
              <Button
                variant="gradient"
                onClick={handlePaymentSetup}
                disabled={connectLink.isPending}
              >
                {connectLink.isPending ? "Redirecting to Stripe..." : "Set Up Payments"}
              </Button>
            </div>
          )}
        </Card>

        {/* Tax Rate */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Tax Rate</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Set the sales tax percentage for this restaurant. This will be
            applied to all orders.
          </p>
          <div className="flex items-end gap-2">
            <div className="w-40">
              <Label className="text-muted-foreground text-sm" htmlFor="tax-rate">Rate (%)</Label>
              <Input
                id="tax-rate"
                type="number"
                step="0.001"
                min="0"
                max="99"
                value={displayTaxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                placeholder="0.000"
              />
            </div>
            <Button variant="gradient" onClick={handleSaveTax} disabled={updateTaxRate.isPending}>
              {updateTaxRate.isPending ? "Saving..." : "Save"}
            </Button>
            {taxMessage && (
              <span className="text-sm text-muted-foreground ml-2">
                {taxMessage}
              </span>
            )}
          </div>
        </Card>

        {/* Payment Model */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Payment Model</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Choose when customers pay for their orders.
          </p>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="text-muted-foreground text-sm">Model</Label>
              <select
                value={displayPaymentModel}
                onChange={(e) => setPaymentModel(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="upfront">Pay Upfront (pay before order goes to kitchen)</option>
                <option value="tab">Open Tab (order first, pay later)</option>
              </select>
            </div>
            <Button variant="gradient" onClick={handleSavePaymentModel}>
              Save
            </Button>
            {pmMessage && (
              <span className="text-sm text-muted-foreground ml-2">
                {pmMessage}
              </span>
            )}
          </div>
        </Card>

        {/* POS Integration */}
        <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">POS Integration</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Connect your point-of-sale system (Toast, Clover, Square) to sync orders automatically.
          </p>
          <Link href={`/account/restaurants/${params.slug}/settings/integrations`}>
            <Button variant="outline">Manage POS Integration</Button>
          </Link>
        </Card>

        {/* Operating Hours */}
        <OperatingHoursCard slug={params.slug} />

        {/* QR Codes — gated behind payment setup */}
        {!connectLoading && !paymentReady && (
          <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
            <div className="flex items-center gap-3 text-muted-foreground">
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
              <p className="text-sm">
                Set up payments above to enable QR code generation and start taking orders.
              </p>
            </div>
          </Card>
        )}

        {paymentReady && (
          <>
            {/* Counter QR (no table) */}
            <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">
                  Counter / Pickup QR Code
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePrintQR(getOrderUrl(), "Counter / Pickup QR Code")}
                >
                  <Printer className="h-4 w-4 mr-2" />
                  Print
                </Button>
              </div>
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

            {/* Table Management */}
            <Card className="bg-card border border-border rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Table Management</h2>
                {activeTables.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrintAllQR}
                  >
                    <Printer className="h-4 w-4 mr-2" />
                    Print All
                  </Button>
                )}
              </div>
              <p className="text-sm text-muted-foreground mb-4">
                Add tables and generate per-table QR codes for dine-in ordering.
              </p>

              {/* Add new table */}
              <div className="flex gap-2 mb-6">
                <div className="flex-1">
                  <Label>Table Name</Label>
                  <Input
                    value={newTableName}
                    onChange={(e) => setNewTableName(e.target.value)}
                    placeholder="e.g. Patio 3"
                  />
                </div>
                <div className="w-32">
                  <Label>Number</Label>
                  <Input
                    value={newTableNumber}
                    onChange={(e) => setNewTableNumber(e.target.value)}
                    placeholder="e.g. A1"
                  />
                </div>
                <Button
                  variant="gradient"
                  className="mt-6"
                  onClick={handleAddTable}
                  disabled={createTable.isPending || !newTableName.trim() || !newTableNumber.trim()}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  {createTable.isPending ? "Adding..." : "Add"}
                </Button>
              </div>

              {createTable.isError && (
                <p className="text-sm text-destructive mb-4">
                  {createTable.error?.message || "Failed to add table. The number may already exist."}
                </p>
              )}

              {/* Table list with QR codes */}
              {tablesLoading && (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
                </div>
              )}

              {tablesError && (
                <p className="text-sm text-destructive text-center py-4">
                  Failed to load tables.
                </p>
              )}

              {!tablesLoading && !tablesError && activeTables.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {activeTables.map((table: Table) => (
                    <div
                      key={table.id}
                      className="flex flex-col items-center p-4 bg-card border border-border rounded-2xl relative group"
                    >
                      <button
                        onClick={() => handleDeleteTable(table)}
                        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                        title="Delete table"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                      <QRCodeSVG value={getOrderUrl(table.number)} size={120} />
                      <p className="font-semibold mt-2">{table.name}</p>
                      <p className="text-xs text-muted-foreground">#{table.number}</p>
                      <p className="text-xs text-muted-foreground break-all text-center mt-1">
                        {getOrderUrl(table.number)}
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => handlePrintQR(getOrderUrl(table.number), `${table.name} (#${table.number})`)}
                      >
                        <Printer className="h-3 w-3 mr-1" />
                        Print
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {!tablesLoading && !tablesError && activeTables.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No tables yet. Add your first table above.
                </p>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
