import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import evaluateAPI, { type EvaluateResponse } from '@/api/evaluate';
import ReactMarkdown from 'react-markdown';


const PRESETS: Record<string, any> = {
  normal: { user_id: 'alice@demo.com', ip: '49.36.128.100', device_fp: 'chrome-win-1920x1080', resource: 'general', failed_attempts: 0, role: 'viewer' },
  new_device: { user_id: 'alice@demo.com', ip: '49.36.128.100', device_fp: 'firefox-mac-2560x1440', resource: 'dashboard', failed_attempts: 0, role: 'viewer' },
  impossible_travel: { user_id: 'alice@demo.com', ip: '185.220.100.252', device_fp: 'chrome-win-1920x1080', resource: 'financial_data', failed_attempts: 0, role: 'viewer' },
  brute_force: { user_id: 'alice@demo.com', ip: '203.0.113.42', device_fp: 'chrome-win-1920x1080', resource: 'general', failed_attempts: 8, role: 'viewer' },
  everything_bad: { user_id: 'alice@demo.com', ip: '89.33.8.54', device_fp: 'unknown-linux-800x600', resource: 'admin_panel', failed_attempts: 10, role: 'viewer' },
};

const DECISION_COLORS: Record<string, string> = {
  ALLOW: 'bg-emerald-500', OTP: 'bg-amber-500', STEPUP: 'bg-orange-500', BLOCK: 'bg-red-500',
};

export default function PlaygroundPage() {
  const [form, setForm] = useState(PRESETS.normal);
  const [response, setResponse] = useState<EvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handlePreset = (key: string) => {
    setForm(PRESETS[key]);
    setResponse(null);
    setError('');
  };

  const handleSend = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await evaluateAPI.evaluate(form);
      setResponse(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Playground</h1>
        <p className="text-muted-foreground">Test the evaluate endpoint from your dashboard</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.keys(PRESETS).map(key => (
          <Button key={key} variant="outline" size="sm" onClick={() => handlePreset(key)}>
            ▶ {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </Button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Request */}
        <Card>
          <CardHeader><CardTitle>Request Body</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>user_id</Label>
              <Input value={form.user_id} onChange={e => setForm({...form, user_id: e.target.value})} />
            </div>
            <div>
              <Label>ip</Label>
              <Input value={form.ip} onChange={e => setForm({...form, ip: e.target.value})} />
            </div>
            <div>
              <Label>device_fp</Label>
              <Input value={form.device_fp} onChange={e => setForm({...form, device_fp: e.target.value})} />
            </div>
            <div>
              <Label>resource</Label>
              <Select value={form.resource} onValueChange={v => setForm({...form, resource: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['general','dashboard','profile','reports','settings','billing','user_management','api_keys','financial_data','admin_panel'].map(r => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>failed_attempts</Label>
              <Input type="number" min={0} value={form.failed_attempts}
                     onChange={e => setForm({...form, failed_attempts: parseInt(e.target.value) || 0})} />
            </div>
            <div>
              <Label>role</Label>
              <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['viewer','analyst','developer','hr','manager','admin'].map(r => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button className="w-full" onClick={handleSend} disabled={loading}>
              {loading ? 'Evaluating...' : 'Send Request'}
            </Button>
          </CardContent>
        </Card>

        {/* Response */}
        <Card>
          <CardHeader><CardTitle>Response</CardTitle></CardHeader>
          <CardContent>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            {!response && !error && (
              <p className="text-center text-muted-foreground py-12">Choose a preset or fill the form and send a request</p>
            )}
            {response && (
              <div className="space-y-4">
                {/* Score + Decision */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className={`text-5xl font-bold ${
                      response.score < 30 ? 'text-emerald-500' : response.score < 60 ? 'text-amber-500' :
                      response.score < 80 ? 'text-orange-500' : 'text-red-500'
                    }`}>{response.score}</p>
                    <p className="text-muted-foreground text-sm">Risk Score</p>
                  </div>
                  <Badge className={`text-lg px-4 py-1 ${DECISION_COLORS[response.decision] || ''}`}>
                    {response.decision}
                  </Badge>
                </div>

                {/* Explanation */}
                <div className="bg-muted/50 rounded-lg p-3 prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{response.explanation?.replace(/```markdown|```/g, '')}</ReactMarkdown>
                </div>

                {/* DNA + Timing */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">DNA Match:</span>
                    <span className="font-bold ml-1">{response.dna_match}%</span>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">Time:</span>
                    <span className="font-bold ml-1">{response.processing_time_ms}ms</span>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">New User:</span>
                    <span className="font-bold ml-1">{response.is_new_user ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">ID:</span>
                    <span className="font-mono text-xs ml-1">{response.request_id}</span>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">IP:</span>
                    <span className="font-mono text-xs ml-1">{response.ip}</span>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <span className="text-muted-foreground">Location:</span>
                    <span className="font-bold ml-1">{response.city}, {response.country}</span>
                  </div>
                </div>

                {/* Risk Factors */}
                <div>
                  <h4 className="font-semibold text-sm mb-2">Risk Factors</h4>
                  <div className="space-y-1">
                    {response.risk_factors.map((f, i) => (
                      <div key={i} className="flex items-center justify-between text-sm py-1 border-b last:border-0">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${f.contribution > 0 ? 'bg-red-500' : 'bg-emerald-500'}`} />
                          <span>{f.factor}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`font-mono text-xs ${f.contribution > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                            {f.contribution > 0 ? '+' : ''}{f.contribution}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}