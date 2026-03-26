import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useRealtimeLogs } from '@/hooks/use-realtime-logs';
import { useAuth } from '@/context/AuthContext';
import { Activity, ShieldAlert, ShieldCheck, Key } from 'lucide-react';

const DECISION_BADGE: Record<string, string> = {
  ALLOW: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  OTP: 'bg-amber-100 text-amber-800 border-amber-300',
  STEPUP: 'bg-orange-100 text-orange-800 border-orange-300',
  BLOCK: 'bg-red-100 text-red-800 border-red-300',
};

export default function UsersPage() {
  const { events, connected, error, stats } = useRealtimeLogs();
  const [filterUser, setFilterUser] = useState('');

  const filteredEvents = useMemo(() => {
    if (!filterUser.trim()) return events;
    return events.filter(e => e.user_id.toLowerCase().includes(filterUser.toLowerCase()));
  }, [events, filterUser]);


  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-theme(spacing.16))] relative">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            Live Stream
            <span className="relative flex h-3 w-3 ml-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${connected ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${connected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
            </span>
          </h1>
          <p className="text-muted-foreground mt-1">
            {connected ? 'Waiting for events...' : error || 'Connecting...'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 flex-shrink-0">
        <Card>
          <CardContent className="pt-6 flex items-center gap-4">
            <div className="p-3 bg-blue-100 text-blue-600 rounded-lg dark:bg-blue-900/30 dark:text-blue-400"><Activity size={24} /></div>
            <div><p className="text-sm text-muted-foreground">Total Seen</p><p className="text-2xl font-bold">{stats.total}</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 flex items-center gap-4">
            <div className="p-3 bg-red-100 text-red-600 rounded-lg dark:bg-red-900/30 dark:text-red-400"><ShieldAlert size={24} /></div>
            <div><p className="text-sm text-muted-foreground">Blocked</p><p className="text-2xl font-bold">{stats.blocked}</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 flex items-center gap-4">
            <div className="p-3 bg-emerald-100 text-emerald-600 rounded-lg dark:bg-emerald-900/30 dark:text-emerald-400"><ShieldCheck size={24} /></div>
            <div><p className="text-sm text-muted-foreground">Allowed</p><p className="text-2xl font-bold">{stats.allowed}</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 flex items-center gap-4">
            <div className="p-3 bg-amber-100 text-amber-600 rounded-lg dark:bg-amber-900/30 dark:text-amber-400"><Key size={24} /></div>
            <div><p className="text-sm text-muted-foreground">Challenged</p><p className="text-2xl font-bold">{stats.challenged}</p></div>
          </CardContent>
        </Card>
      </div>

      <Card className="flex-grow flex flex-col min-h-0 bg-zinc-50/50 dark:bg-zinc-900/20">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between pb-4">
          <CardTitle className="text-lg font-medium">Event Feed</CardTitle>
          <Input 
            placeholder="Filter by user..." 
            value={filterUser}
            onChange={(e) => setFilterUser(e.target.value)}
            className="w-48 h-8 text-sm placeholder:text-muted-foreground/50 border-white/10 bg-white/5" 
          />
        </CardHeader>
        <CardContent className="flex-grow overflow-auto min-h-0 p-0">
          {filteredEvents.length === 0 ? (
             <div className="h-full flex items-center justify-center flex-col text-muted-foreground opacity-50 space-y-4">
               <Activity size={48} className="animate-pulse" />
               <p>Listening for real-time login events...</p>
             </div>
          ) : (
            <div className="divide-y divide-border/50">
              {filteredEvents.map((ev, i) => (
                <div key={i} className="group flex flex-col sm:flex-row items-start sm:items-center gap-4 p-4 hover:bg-white/5 transition-colors">
                  <div className="w-16 flex-shrink-0 text-xs text-muted-foreground">
                    {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </div>
                  
                  <div className="flex-shrink-0 w-24">
                    <Badge variant="outline" className={`${DECISION_BADGE[ev.decision] || ''} w-full justify-center`}>
                      {ev.decision}
                    </Badge>
                  </div>
                  
                  <div className="flex-grow min-w-0 flex items-center gap-3">
                    <span className="font-semibold truncate">{ev.user_id}</span>
                    <span className="text-muted-foreground text-sm truncate max-w-[150px]">
                      {ev.resource}
                    </span>
                  </div>

                  <div className="flex-shrink-0 flex flex-col items-end gap-1 w-32">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{ev.city || 'Unknown'}, {ev.country}</span>
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">{ev.ip}</span>
                  </div>

                  <div className="flex-shrink-0 w-20 flex justify-end">
                    <div className="text-center">
                      <div className={`text-xl font-bold font-mono leading-none ${
                        ev.score < 30 ? 'text-emerald-500' : ev.score < 60 ? 'text-amber-500' : 'text-red-500'
                      }`}>{ev.score}</div>
                      <div className="text-[10px] text-muted-foreground mt-1 font-medium tracking-wider">RISK</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}