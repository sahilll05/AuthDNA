import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import evaluateAPI from '@/api/evaluate';

export interface LiveLoginEvent {
  type: string;
  user_id: string;
  ip: string;
  country: string;
  city: string;
  score: number;
  decision: string;
  explanation: string;
  resource: string;
  risk_factors: Array<{
    factor: string;
    contribution: number;
    description?: string;
  }>;
  dna_match: number;


  is_new_user: boolean;
  processing_time_ms: number;
  request_id: string;
  timestamp: string;
}

interface RealtimeLogsContextType {
  events: LiveLoginEvent[];
  connected: boolean;
  error: string | null;
  stats: {
    total: number;
    blocked: number;
    allowed: number;
    challenged: number;
  };
  mutateEvent: (requestId: string, updates: Partial<LiveLoginEvent>) => void;
}


const RealtimeLogsContext = createContext<RealtimeLogsContextType | undefined>(undefined);

export function RealtimeLogsProvider({ children }: { children: React.ReactNode }) {
  const { apiKey } = useAuth();
  const [events, setEvents] = useState<LiveLoginEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 1. Initial Fetch of History
  const fetchHistory = useCallback(async () => {
    if (!apiKey) return;
    try {
       const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/v1/dashboard/logs?limit=50`, {
         headers: { 'X-API-Key': apiKey }
       });
       const data = await res.json();
       if (data.logs) {
         // Transform logs to match LiveLoginEvent interface
         const transformed: LiveLoginEvent[] = data.logs.map((l: any) => ({
           ...l,
           risk_factors: l.risk_factors || (l.risk_factors_json ? JSON.parse(l.risk_factors_json) : []),
           dna_match: Number(l.dna_match || 0)
         }));
         setEvents(transformed);
       }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  }, [apiKey]);


  // 2. SSE Connection Logic
  const connect = useCallback(() => {
    if (!apiKey || !mountedRef.current) return;

    const url = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/v1/stream/events?api_key=${apiKey}`;
    const controller = new AbortController();

    fetch(url, {
      headers: { 'X-API-Key': apiKey, 'Accept': 'text/event-stream' },
      signal: controller.signal,
    })

      .then(async (res) => {
        if (!res.ok) {
          setError(`Stream error: ${res.status}`);
          setConnected(false);
          scheduleReconnect();
          return;
        }
        setConnected(true);
        setError(null);

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (mountedRef.current) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6));
                if (payload.type === 'login_event') {
                  setEvents(prev => {
                    // Avoid duplicates if initial fetch and stream overlap
                    if (prev.some(e => e.request_id === payload.request_id)) return prev;
                    return [payload as LiveLoginEvent, ...prev].slice(0, 200);
                  });
                }
              } catch (_) {}
            }
          }
        }
        if (mountedRef.current) scheduleReconnect();
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        if (mountedRef.current) {
          setConnected(false);
          setError('Connection lost — reconnecting…');
          scheduleReconnect();
        }
      });

    return () => controller.abort();
  }, [apiKey]);

  const scheduleReconnect = () => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    reconnectTimer.current = setTimeout(() => {
      if (mountedRef.current) connect();
    }, 5000);
  };

  useEffect(() => {
    mountedRef.current = true;
    if (apiKey) {
      fetchHistory();
      const disconnect = connect();
      return () => {
        mountedRef.current = false;
        if (disconnect) disconnect();
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      };
    }
  }, [apiKey, connect, fetchHistory]);

  // Computed Stats
  const stats = React.useMemo(() => {
    return events.reduce((acc, e) => {
      acc.total++;
      if (e.decision === 'BLOCK') acc.blocked++;
      else if (e.decision === 'OTP' || e.decision === 'STEPUP') acc.challenged++;
      else if (e.decision === 'ALLOW') acc.allowed++;
      return acc;
    }, { total: 0, blocked: 0, challenged: 0, allowed: 0 });
  }, [events]);

  // 3. Mutators
  const mutateEvent = useCallback((requestId: string, updates: Partial<LiveLoginEvent>) => {
    setEvents(prev => prev.map(e => e.request_id === requestId ? { ...e, ...updates } : e));
  }, []);

  return (
    <RealtimeLogsContext.Provider value={{ events, connected, error, stats, mutateEvent }}>
      {children}
    </RealtimeLogsContext.Provider>
  );
}


export function useRealtimeLogsContext() {
  const context = useContext(RealtimeLogsContext);
  if (context === undefined) {
    throw new Error('useRealtimeLogsContext must be used within a RealtimeLogsProvider');
  }
  return context;
}
