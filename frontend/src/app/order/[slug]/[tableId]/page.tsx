"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useOrderStore } from "@/stores/order-store";
import OrderPage from "../page";

export default function TableOrderPage() {
  const params = useParams<{ slug: string; tableId: string }>();
  const setTableIdentifier = useOrderStore((s) => s.setTableIdentifier);

  useEffect(() => {
    setTableIdentifier(params.tableId);
  }, [params.tableId, setTableIdentifier]);

  return <OrderPage />;
}
