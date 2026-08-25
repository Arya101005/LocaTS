import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * SSE (Server-Sent Events) hook for live dashboard updates.
 * Auto-reconnects with exponential backoff.
 * Falls back to no-op if SSE is unavailable (e.g. serverless).
 */
export function useSSE(url = '/api/sse/stream', onUpdate) {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [reconnecting, setReconnecting] = useState(false);
  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(2000);
  const failCountRef = useRef(0);
  const mountedRef = useRef(true);
  const onUpdateRef = useRef(onUpdate);

  // Keep callback ref stable
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // If too many failures, stop trying (serverless environment)
    if (failCountRef.current >= 3) {
      setConnected(false);
      setReconnecting(false);
      return;
    }

    try {
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setReconnecting(false);
        reconnectDelayRef.current = 2000;
        failCountRef.current = 0;
      };

      es.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'update') {
            setLastUpdate(new Date());
            onUpdateRef.current?.(data.data);
          }
        } catch (e) {}
      };

      es.onerror = () => {
        if (!mountedRef.current) return;
        es.close();
        setConnected(false);
        failCountRef.current++;

        // Only reconnect if we haven't failed too many times
        if (failCountRef.current < 3) {
          setReconnecting(true);
          const delay = Math.min(reconnectDelayRef.current, 15000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 15000);
            connect();
          }, delay);
        }
      };
    } catch (e) {
      setConnected(false);
      failCountRef.current++;
    }
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    failCountRef.current = 0;
    connect();

    return () => {
      mountedRef.current = false;
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { connected, lastUpdate, reconnecting };
}
