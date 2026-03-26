import { useState, useEffect, useRef } from 'react';
import { useRealtimeLogs } from '@/hooks/use-realtime-logs';
import { useAuth } from '@/context/AuthContext';


import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import { AlertCircle, ShieldCheck, ShieldAlert, Fingerprint, Activity, Clock, Globe, Shield } from 'lucide-react';
import ReactMarkdown from 'react-markdown';


// Interfaces mapping to the SSE payload
interface RiskFactor {
  factor: string;
  contribution: number;
  description?: string;
}


interface LiveEvent {
  request_id: string;
  user_id: string;
  ip: string;
  country: string;
  city: string;
  score: number;
  decision: string;
  explanation: string;
  resource: string;
  risk_factors: RiskFactor[];
  dna_match: number;
  is_new_user: boolean;
  timestamp: string;
}

const DECISION_STYLES: Record<string, { bg: string, text: string, border: string }> = {
  ALLOW: { bg: 'bg-emerald-500/10', text: 'text-emerald-500', border: 'border-emerald-500/30' },
  OTP: { bg: 'bg-amber-500/10', text: 'text-amber-500', border: 'border-amber-500/30' },
  STEPUP: { bg: 'bg-orange-500/10', text: 'text-orange-500', border: 'border-orange-500/30' },
  REQUIRE_MFA: { bg: 'bg-orange-500/10', text: 'text-orange-500', border: 'border-orange-500/30' },
  BLOCK: { bg: 'bg-red-500/10', text: 'text-red-500', border: 'border-red-500/30' },
};

const getDecisionLabel = (decision: string) => {
  if (decision === 'STEPUP') return 'REQUIRE_MFA';
  return decision;
};


export default function AdminSecurityDashboard() {
  const { events, connected: isConnected, mutateEvent } = useRealtimeLogs();
  const { apiKey } = useAuth();
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);



  useEffect(() => {
    if (events.length > 0 && !selectedEventId) {
      setSelectedEventId(events[0].request_id);
    }
  }, [events, selectedEventId]);


  const selectedData = events.find(e => e.request_id === selectedEventId) || events[0];

  // Helper to construct radar chart data from the exact 10 features
  const buildRadarData = (rf: RiskFactor[]) => {
    // We map the SHAP risk_factors array back into 6 readable dimensions for the radar
    let timeRisk = 0, locRisk = 0, devRisk = 0, privRisk = 0, failsRisk = 0, dormRisk = 0;
    
    if (Array.isArray(rf)) {
      rf.forEach(f => {
        // Temporal
        if (f.factor === 'off_hours' || f.factor.startsWith('hour_')) {
          timeRisk += f.contribution;
        }
        // Geolocation
        if (f.factor === 'new_country' || f.factor === 'country_change' || f.factor === 'impossible_travel') {
          locRisk += f.contribution;
        }
        // Device / Anomaly Engine
        if (f.factor === 'new_device' || f.factor === 'is_new_device' || f.factor === 'ml_iso' || f.factor === 'ml_xgboost') {
          devRisk += f.contribution;
        }
        // Privilege & Resource Sensitivity
        if (f.factor === 'privilege' || f.factor === 'resource_sensitivity' || f.factor === 'privilege_gap_score') {
          privRisk += f.contribution;
        }
        // Login Failures and Bot signals
        if (f.factor === 'multi_attack' || f.factor === 'failed_attempts') {
          failsRisk += f.contribution;
        }
        // Dormancy or Profile Mismatch
        if (f.factor === 'dna_mismatch' || f.factor === 'days_since_last_login' || f.factor === 'dormancy') {
          dormRisk += f.contribution;
        }
      });
    }


    const clamp = (val: number) => Math.min(100, Math.max(0, val * 100)); // scale for visual representation

    return [
      { dimension: 'Temporal', risk: clamp(timeRisk), fullMark: 100 },
      { dimension: 'Geolocation', risk: clamp(locRisk), fullMark: 100 },
      { dimension: 'Device', risk: clamp(devRisk), fullMark: 100 },
      { dimension: 'Privilege', risk: clamp(privRisk), fullMark: 100 },
      { dimension: 'Auth Fails', risk: clamp(failsRisk), fullMark: 100 },
      { dimension: 'Dormancy', risk: clamp(dormRisk), fullMark: 100 }
    ];
  };

  const handleHITLAction = async (action: string) => {
    if (!selectedEventId || !apiKey) return;
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

      const res = await fetch(`${apiUrl}/v1/evaluate/hitl`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },

        body: JSON.stringify({ request_id: selectedEventId, decision: action === 'APPROVE' ? 'ALLOW' : action })
      });
      if (res.ok) {
        const data = await res.json();
        const effectiveDecision = data.effective_decision || (action === 'APPROVE' ? 'ALLOW' : action);
        // Optimistically update the UI to reflect the Human-In-The-Loop decision
        mutateEvent(selectedEventId, { decision: effectiveDecision });
      } else {

        console.error('HITL Backend rejected request');
      }
    } catch (e) {
      console.error('Failed to submit HITL action', e);
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-teal-400 to-emerald-600">
            Live Risk Radar
          </h1>
          <p className="text-muted-foreground">Real-time human-in-the-loop security monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
          </span>
          <span className="text-sm font-medium text-muted-foreground">{isConnected ? 'Listening to SSE Stream' : 'Disconnected'}</span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-6 min-h-0">
        
        {/* LEFT COLUMN: Feed */}
        <Card className="md:col-span-4 flex flex-col border-0 shadow-lg bg-card/50 backdrop-blur-xl">
          <CardHeader className="shrink-0 border-b border-border/50 bg-muted/20">
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5 text-teal-500" />
              Incoming Events
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden">
            <ScrollArea className="h-full">
              {events.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  <p className="animate-pulse">Waiting for logins...</p>
                  <p className="text-xs mt-2">Try logging in on the Company Demo to see events here.</p>
                </div>
              ) : (
                <div className="divide-y divide-border/50">
                  {events.map(ev => {
                    const st = DECISION_STYLES[ev.decision] || DECISION_STYLES.ALLOW;
                    const isSelected = selectedEventId === ev.request_id;
                    return (
                      <button
                        key={ev.request_id}
                        onClick={() => setSelectedEventId(ev.request_id)}
                        className={`w-full text-left p-4 transition-all duration-300 relative overflow-hidden group hover:bg-muted/40 ${isSelected ? 'bg-muted/60 border-l-4 border-teal-500 shadow-xl' : 'border-l-4 border-transparent'}`}
                      >
                        <div className="absolute inset-0 bg-gradient-to-r from-teal-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div className="flex justify-between items-start mb-2 relative z-10">
                          <code className="text-sm font-bold">{ev.user_id}</code>
                          <Badge variant="outline" className={`${st.bg} ${st.text} ${st.border}`}>
                            {getDecisionLabel(ev.decision)}
                          </Badge>

                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1"><Globe className="w-3 h-3"/> {ev.city}, {ev.country}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3"/> {new Date(ev.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* RIGHT COLUMN: Details & Radar */}
        <div className="md:col-span-8 flex flex-col gap-6 min-h-0">
          
          {selectedData ? (
            <>
              {/* Top Row: Score & Radar */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Score Card */}
                <Card className="border border-white/10 shadow-2xl bg-gradient-to-br from-card to-card/50 backdrop-blur-2xl overflow-hidden relative group">
                  <div className="absolute -right-20 -top-20 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl pointer-events-none group-hover:bg-teal-500/20 transition-all duration-700" />
                  <CardHeader>
                    <CardTitle className="text-lg">Risk Assessment</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between mb-6">
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Confidence Score</p>
                        <p className={`text-6xl font-black ${selectedData.score > 70 ? 'text-red-500' : selectedData.score > 40 ? 'text-orange-400' : 'text-emerald-500'}`}>
                          {selectedData.score}
                        </p>
                      </div>
                      <Badge className={`text-lg px-6 py-2 ${DECISION_STYLES[selectedData.decision]?.bg} ${DECISION_STYLES[selectedData.decision]?.text}`}>
                        {getDecisionLabel(selectedData.decision)}
                      </Badge>

                    </div>
                    
                    <div className="space-y-4 bg-muted/30 p-4 rounded-xl border border-border/50">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-teal-400 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold">LLM Analysis</p>
                          <div className="text-sm italic text-muted-foreground mt-1 prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown>{selectedData.explanation?.replace(/```markdown|```/g, '')}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Radar Chart */}
                <Card className="border border-white/10 shadow-2xl flex flex-col bg-card/60 backdrop-blur-2xl">
                  <CardHeader className="pb-0">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Fingerprint className="w-5 h-5 text-teal-500" />
                      Behavioral DNA
                    </CardTitle>
                    <CardDescription>Match: {selectedData.dna_match}% | {selectedData.is_new_user ? 'New User' : 'Returning'}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 w-full h-[250px] p-0 -mt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={buildRadarData(selectedData.risk_factors)}>
                        <PolarGrid stroke="rgba(255,255,255,0.1)" />
                        <PolarAngleAxis dataKey="dimension" tick={{ fill: '#8888a8', fontSize: 11 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                        <Radar
                          name="Risk Dimension"
                          dataKey="risk"
                          stroke="#14b8a6"
                          fill="#14b8a6"
                          fillOpacity={0.3}
                        />
                        <RechartsTooltip contentStyle={{ backgroundColor: '#17171f', borderColor: '#2a2a38', fontSize: '12px' }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              {/* Bottom Row: Details Tracker & HITL */}
              <Card className="border border-white/10 shadow-2xl flex-1 overflow-hidden flex flex-col bg-card/60 backdrop-blur-2xl">
                <CardHeader className="bg-muted/5 border-b border-white/5 py-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">SHAP Feature Attribution</CardTitle>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="border-emerald-500/50 text-emerald-500 hover:bg-emerald-500/10" onClick={() => handleHITLAction('APPROVE')}>
                        <ShieldCheck className="w-4 h-4 mr-1" /> Approve
                      </Button>
                      <Button size="sm" variant="outline" className="border-orange-500/50 text-orange-500 hover:bg-orange-500/10" onClick={() => handleHITLAction('REQUIRE_MFA')}>
                        <Shield className="w-4 h-4 mr-1" /> Require MFA
                      </Button>
                      <Button size="sm" variant="outline" className="border-red-500/50 text-red-500 hover:bg-red-500/10" onClick={() => handleHITLAction('BLOCK')}>
                        <ShieldAlert className="w-4 h-4 mr-1" /> Block
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0 overflow-y-auto max-h-[250px]">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/30 sticky top-0">
                      <tr>
                        <th className="py-2 px-4 text-left font-medium text-muted-foreground w-1/3">Feature</th>
                        <th className="py-2 px-4 text-right font-medium text-muted-foreground">Impact</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {(selectedData.risk_factors || [])
                        .sort((a,b) => b.contribution - a.contribution)
                        .map((rf, idx) => (
                        <tr key={idx} className="hover:bg-muted/20">

                          <td className="py-2 px-4 font-mono text-xs">{rf.factor}</td>
                          <td className="py-2 px-4 text-right">
                            <span className={`font-medium ${rf.contribution > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                              {rf.contribution > 0 ? '+' : ''}{rf.contribution.toFixed(3)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border/50 rounded-xl bg-card/20">
              <Shield className="w-12 h-12 mb-4 opacity-50" />
              <p>Select an event to view DNA details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
