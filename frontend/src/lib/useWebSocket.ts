import { useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "open" | "closed";

/**
 * Auto-reconnecting WebSocket hook. Calls `onMessage` for every parsed JSON
 * message and exposes the connection status.
 */
export function useWebSocket<T>(path: string, onMessage: (data: T) => void): WsStatus {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const url =
      (location.protocol === "https:" ? "wss://" : "ws://") + location.host + path;

    const connect = () => {
      setStatus("connecting");
      ws = new WebSocket(url);
      ws.onopen = () => setStatus("open");
      ws.onmessage = (ev) => {
        try {
          handlerRef.current(JSON.parse(ev.data) as T);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setStatus("closed");
        if (!closed) retry = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [path]);

  return status;
}
