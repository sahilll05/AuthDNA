import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLogs } from '@/hooks/use-dashboard';
import ReactMarkdown from 'react-markdown';


const DECISION_BADGE: Record<string, string> = {
  ALLOW: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  OTP: 'bg-amber-100 text-amber-800 border-amber-300',
  STEPUP: 'bg-orange-100 text-orange-800 border-orange-300',
  BLOCK: 'bg-red-100 text-red-800 border-red-300',
};

export default function LogsPage() {
  const [filterUser, setFilterUser] = useState('');
  const [limit, setLimit] = useState(50);
  const { logs, loading, error } = useLogs(filterUser || undefined, limit);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Logs</h1>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row justify-between gap-4">
            <CardTitle>Login Evaluation Logs</CardTitle>
            <div className="flex gap-2">
              <Input
                placeholder="Filter by user..."
                value={filterUser}
                onChange={(e) => setFilterUser(e.target.value)}
                className="w-48"
              />
              <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                  <SelectItem value="200">200</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading && <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" /></div>}
          {error && <p className="text-red-500 text-center py-4">{error}</p>}
          {!loading && !error && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-3 px-2">Time</th>
                    <th className="py-3 px-2">User</th>
                    <th className="py-3 px-2">IP</th>
                    <th className="py-3 px-2">Country</th>
                    <th className="py-3 px-2">Score</th>
                    <th className="py-3 px-2">Decision</th>
                    <th className="py-3 px-2">Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.length === 0 && (
                    <tr><td colSpan={7} className="text-center py-8 text-muted-foreground">No logs yet</td></tr>
                  )}
                  {logs.map((log, i) => (
                    <tr key={i} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-2 text-xs text-muted-foreground whitespace-nowrap">
                        {log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}
                      </td>
                      <td className="py-3 px-2 font-medium">{log.user_id}</td>
                      <td className="py-3 px-2 font-mono text-xs">{log.ip}</td>
                      <td className="py-3 px-2">{log.country}</td>
                      <td className="py-3 px-2">
                        <span className={`font-bold ${
                          log.score < 30 ? 'text-emerald-600' : log.score < 60 ? 'text-amber-600' : 'text-red-600'
                        }`}>{log.score}</span>
                      </td>
                      <td className="py-3 px-2">
                        <Badge variant="outline" className={DECISION_BADGE[log.decision] || ''}>
                          {log.decision}
                        </Badge>
                      </td>
                      <td className="py-3 px-2 text-xs text-muted-foreground max-w-[200px] truncate overflow-hidden" title={log.explanation}>
                        <div className="prose prose-invert prose-[10px] max-w-none pointer-events-none line-clamp-1">
                          <ReactMarkdown>{log.explanation?.replace(/```markdown|```/g, '')}</ReactMarkdown>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}