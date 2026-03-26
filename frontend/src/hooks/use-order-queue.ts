import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOrderQueue, type OrderQueueInfo } from "@/lib/api";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";
const RECONNECT_INTERVAL = 3000;
const POLL_INTERVAL = 15000;

interface UseOrderQueueOptions {
  slug: string;
  orderId: string | null;
  enabled?: boolean;
}

export function useOrderQueue({ slug, orderId, enabled = true }: UseOrderQueueOptions) {
  const [queueInfo, setQueueInfo] = useState<OrderQueueInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout>();
  const pollRef = useRef<NodeJS.Timeout>();
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (!orderId || !enabledRef.current) return;
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const data = await fetchOrderQueue(slug, orderId);
        setQueueInfo(data);
      } catch {
        // Silently fail — will retry on next interval
      }
    }, POLL_INTERVAL);
  }, [slug, orderId, stopPolling]);

  const connect = useCallback(() => {
    if (!orderId || !enabledRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_URL}/ws/order/${slug}/${orderId}/`);

    ws.onopen = () => {
      setIsConnected(true);
      stopPolling();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setQueueInfo(data);
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (enabledRef.current) {
        startPolling();
        reconnectRef.current = setTimeout(connect, RECONNECT_INTERVAL);
      }
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [slug, orderId, stopPolling, startPolling]);

  useEffect(() => {
    if (!enabled || !orderId) return;
    connect();

    return () => {
      enabledRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      stopPolling();
      wsRef.current?.close();
    };
  }, [connect, enabled, orderId, stopPolling]);

  return {
    queuePosition: queueInfo?.queue_position ?? null,
    estimatedWait: queueInfo?.estimated_wait_minutes ?? null,
    status: queueInfo?.status ?? null,
    busyness: queueInfo?.busyness ?? null,
    isConnected,
  };
}
