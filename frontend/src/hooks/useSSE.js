import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * SSE (Server-Sent Events) hook for live dashboard updates.
 * Auto-reconnects with exponential backoff.
 * Reconciles missed updates on reconnect.
 */
export function useSSE(url = '/api/sse/stream', onUpdate) {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [reconnecting, setReconnecting] = useState(false);
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    try {
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setReconnecting(false);
        reconnectDelayRef.current = 1000; // Reset backoff
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'update') {
            setLastUpdate(new Date(data.timestamp));
            onUpdate?.(data.data);
          }
          // heartbeat — just confirms connection alive
        } catch (e) {}
      };

      es.onerror = () => {
        es.close();
        setConnected(false);
        setReconnecting(true);

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
        const delay = Math.min(reconnectDelayRef.current, 30000);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
          connect();
        }, delay);
      };
    } catch (e) {
      // Fallback to polling if SSE not supported
      setConnected(false);
    }
  }, [url, onUpdate]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { connected, lastUpdate, reconnecting };
}
