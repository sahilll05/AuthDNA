import { useRealtimeLogsContext } from '@/context/RealtimeLogsContext';

interface UseRealtimeLogsOptions {
  apiKey?: string | null;
  maxEvents?: number;
}

export function useRealtimeLogs(_options?: UseRealtimeLogsOptions) {
  const { events, connected, error, stats, mutateEvent } = useRealtimeLogsContext();
  return { events, connected, error, stats, mutateEvent };
}

