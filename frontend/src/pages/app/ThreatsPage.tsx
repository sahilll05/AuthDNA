import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useLogs } from '@/hooks/use-dashboard';
import ReactMarkdown from 'react-markdown';


const DECISION_BADGE: Record<string, string> = {
  OTP: 'bg-amber-500 text-white',
  STEPUP: 'bg-orange-500 text-white',
  BLOCK: 'bg-red-500 text-white',
};

export default function ThreatsPage() {
  const { logs, loading, error } = useLogs(undefined, 100);

  const threats = logs.filter(l => l.decision !== 'ALLOW');

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Threats</h1>

      <Card>
        <CardHeader>
          <CardTitle>Live Threat Feed</CardTitle>
          <p className="text-sm text-muted-foreground">
            Showing blocked, OTP, and step-up logins — {threats.length} threats detected
          </p>
        </CardHeader>
        <CardContent>
          {loading && <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" /></div>}
          {error && <p className="text-red-500">{error}</p>}
          {!loading && threats.length === 0 && (
            <p className="text-center py-8 text-muted-foreground">No threats detected yet 🎉</p>
          )}
          <div className="space-y-4">
            {threats.map((t, i) => (
              <Card key={i} className="border shadow-sm">
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <Badge className={DECISION_BADGE[t.decision] || 'bg-zinc-500'}>
                        {t.decision}
                      </Badge>
                      <div>
                        <p className="font-bold">{t.user_id}</p>
                        <p className="text-sm text-muted-foreground">
                          {t.country || 'Unknown'} · {t.ip} · {t.resource}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-2xl font-bold ${
                        t.score >= 80 ? 'text-red-500' : t.score >= 60 ? 'text-orange-500' : 'text-amber-500'
                      }`}>{t.score}</p>
                      <p className="text-xs text-muted-foreground">
                        {t.timestamp ? new Date(t.timestamp).toLocaleString() : ''}
                      </p>
                    </div>
                  </div>
                  {t.explanation && (
                    <div className="mt-3 text-sm italic text-muted-foreground bg-muted/50 rounded p-2 prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown>{t.explanation?.replace(/```markdown|```/g, '')}</ReactMarkdown>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}