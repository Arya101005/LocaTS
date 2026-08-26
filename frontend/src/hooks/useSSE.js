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
  const reconnectDelayRef = useRef(5000);
  const failCountRef = useRef(0);
  const mountedRef = useRef(true);
  const onUpdateRef = useRef(onUpdate);
  const pollIntervalRef = useRef(null);
  const urlRef = useRef(url);

  urlRef.current = url;

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  const pollStatus = useCallback(async () => {
    if (!urlRef.current || !mountedRef.current) return;
    try {
      const res = await fetch('/api/sse/status');
      if (res.ok) {
        const data = await res.json();
        setLastUpdate(new Date());
        onUpdateRef.current?.(data.data);
      }
    } catch (e) {}
  }, []);

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) return;
    pollStatus();
    pollIntervalRef.current = setInterval(pollStatus, 15000);
  }, [pollStatus]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current || !urlRef.current) return;

    stopPolling();

    if (failCountRef.current >= 2) {
      setConnected(false);
      setReconnecting(false);
      startPolling();
      return;
    }

    try {
      const es = new EventSource(urlRef.current);
      eventSourceRef.current = es;

      es.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setReconnecting(false);
        reconnectDelayRef.current = 5000;
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
        eventSourceRef.current = null;

        if (failCountRef.current < 2) {
          setReconnecting(true);
          const delay = Math.min(reconnectDelayRef.current, 15000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 15000);
            connect();
          }, delay);
        } else {
          startPolling();
        }
      };
    } catch (e) {
      setConnected(false);
      failCountRef.current++;
      startPolling();
    }
  }, [startPolling, stopPolling]);

  useEffect(() => {
    mountedRef.current = true;
    failCountRef.current = 0;
    stopPolling();
    connect();

    return () => {
      mountedRef.current = false;
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      stopPolling();
    };
  }, [connect, startPolling, stopPolling]);

  return { connected, lastUpdate, reconnecting };
}
