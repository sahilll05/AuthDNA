import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import ScrollReveal from "@/components/ScrollReveal";
import { motion } from "framer-motion";
import {
  Shield, Zap, Brain, Eye, Globe, Bell, BarChart3,
  ArrowRight, Check, ChevronRight, Star, Lock, Cpu
} from "lucide-react";
import { useState, useEffect, useRef } from "react";

/* ─── Animated Counter ─── */
const Counter = ({ end, suffix = "", label }: { end: number; suffix?: string; label: string }) => {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const duration = 1500;
          const startTime = performance.now();
          const animate = (now: number) => {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * end));
            if (progress < 1) requestAnimationFrame(animate);
          };
          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.5 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [end]);

  return (
    <div ref={ref} className="text-center">
      <div className="text-3xl md:text-4xl font-bold text-foreground tabular-nums">
        {count}{suffix}
      </div>
      <div className="text-sm text-muted-foreground mt-1">{label}</div>
    </div>
  );
};

/* ─── Hero Code Preview ─── */
const CodePreview = () => {
  const lines = [
    { text: 'POST /v1/evaluate', color: 'text-primary' },
    { text: 'X-API-Key: sk_live_abc123', color: 'text-muted-foreground' },
    { text: '{', color: 'text-foreground' },
    { text: '  "user_id": "bob@acme.com",', color: 'text-muted-foreground' },
    { text: '  "ip": "203.0.113.42",', color: 'text-muted-foreground' },
    { text: '  "device_fp": "chrome-win-1920"', color: 'text-muted-foreground' },
    { text: '}', color: 'text-foreground' },
    { text: '', color: '' },
    { text: '→ {"decision":"ALLOW","score":8.4}', color: 'text-success' },
  ];

  return (
    <div className="code-block text-xs sm:text-sm leading-relaxed">
      {lines.map((line, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.8 + i * 0.1, duration: 0.3 }}
          className={line.color}
        >
          {line.text || '\u00A0'}
        </motion.div>
      ))}
    </div>
  );
};

/* ─── Feature Cards ─── */
const features = [
  { icon: Cpu, title: "ML Ensemble Engine", desc: "Isolation Forest + XGBoost + Random Forest working together for 98.4% F1 accuracy." },
  { icon: Shield, title: "Behavioral DNA Profiles", desc: "Every user gets a unique behavioral fingerprint. Deviations instantly raise risk scores." },
  { icon: Eye, title: "Explainable AI", desc: "Human-readable explanations for every decision. No more black-box security." },
  { icon: Zap, title: "200ms Response Time", desc: "Fast enough to sit in your login flow without users noticing any delay." },
  { icon: Lock, title: "Multi-Tenant Isolation", desc: "Complete data isolation between companies. Zero data bleed architecture." },
  { icon: Bell, title: "Webhooks & Alerts", desc: "Instant notifications when threats are detected. Connect to Slack, email, or PagerDuty." },
];

/* ─── Comparison ─── */
const comparisonRows = [
  { feature: "Setup time", us: "30 min", okta: "2 weeks", auth0: "1 week", inhouse: "6-12 mo" },
  { feature: "ML ensemble", us: true, okta: "Maybe", auth0: false, inhouse: false },
  { feature: "Behavioral DNA", us: true, okta: false, auth0: false, inhouse: false },
  { feature: "Explainable AI", us: true, okta: false, auth0: false, inhouse: false },
  { feature: "Response time", us: "200ms", okta: "500ms", auth0: "400ms", inhouse: "Varies" },
  { feature: "F1 Score", us: "98.4%", okta: "N/A", auth0: "N/A", inhouse: "Unknown" },
];

const CellValue = ({ value }: { value: string | boolean }) => {
  if (value === true) return <Check className="text-success mx-auto" size={18} />;
  if (value === false) return <span className="text-muted-foreground">✗</span>;
  return <span>{value}</span>;
};

/* ─── Testimonials ─── */
const testimonials = [
  { name: "Arjun Mehta", role: "CTO, FinEdge", quote: "Blocked 95% of credential stuffing attacks in the first week. Integration took 20 minutes.", stars: 5 },
  { name: "Sarah Lindström", role: "Head of Security, Velox SaaS", quote: "The explainable AI is a game-changer for our compliance reporting. We finally know why things get blocked.", stars: 5 },
  { name: "Carlos Rivera", role: "Founder, ShopStream", quote: "Zero account takeovers since integration. Our customers trust us more now.", stars: 5 },
];

const LandingPage = () => {
  return (
    <div className="overflow-hidden">
      {/* ─── HERO ─── */}
      <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 section-padding">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.04] via-transparent to-accent/[0.03]" />
        <div className="container-wide relative">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <div>
              <motion.div
                initial={{ opacity: 0, y: 20, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0)" }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-6">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse-dot" />
                  AI-Powered Login Security
                </div>
                <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-extrabold text-foreground leading-[1.08] mb-5">
                  Know if it's the real user
                  <br />
                  <span className="gradient-text">or an attacker.</span>
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed max-w-lg mb-8">
                  AI-powered login risk assessment API. Detect credential theft, account takeover, and suspicious logins with 98.4% accuracy — in under 200ms.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link to="/register">
                    <Button variant="hero" size="lg">
                      Get Free API Key
                      <ArrowRight size={18} />
                    </Button>
                  </Link>
                  <Link to="/docs">
                    <Button variant="heroOutline" size="lg">
                      View Documentation
                      <ChevronRight size={18} />
                    </Button>
                  </Link>
                </div>
                <p className="mt-5 text-xs text-muted-foreground">
                  No credit card required · 100 requests/hour free
                </p>
              </motion.div>
            </div>

            <motion.div
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="relative"
            >
              <div className="absolute -inset-4 bg-gradient-to-br from-primary/10 to-accent/10 rounded-2xl blur-2xl opacity-60" />
              <div className="relative glass-card p-1 shadow-xl">
                <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-border/50">
                  <span className="w-2.5 h-2.5 rounded-full bg-destructive/60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-warning/60" />
                  <span className="w-2.5 h-2.5 rounded-full bg-success/60" />
                  <span className="ml-3 text-xs text-muted-foreground font-mono">terminal</span>
                </div>
                <div className="p-4">
                  <CodePreview />
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ─── METRICS BAR ─── */}
      <section className="py-12 border-y border-border/50 bg-card/50">
        <div className="container-wide section-padding">
          <ScrollReveal>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <Counter end={98} suffix="%" label="F1 Score" />
              <Counter end={99} suffix="%" label="Recall Rate" />
              <Counter end={0} suffix=".14%" label="False Alarm Rate" />
              <Counter end={200} suffix="ms" label="Response Time" />
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ─── HOW IT WORKS ─── */}
      <section className="py-20 md:py-28 section-padding">
        <div className="container-narrow">
          <ScrollReveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3">How it works</h2>
              <p className="text-muted-foreground text-lg max-w-xl mx-auto">Three steps to protect every login event</p>
            </div>
          </ScrollReveal>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { step: "01", title: "Get Your API Key", desc: "Register in 30 seconds and receive your authentication credentials." },
              { step: "02", title: "Send Login Signals", desc: "Forward IP, device fingerprint, and user_id with each authentication event." },
              { step: "03", title: "Get Decision", desc: "Receive an instant ALLOW, OTP, STEPUP, or BLOCK decision with risk score." },
            ].map((item, i) => (
              <ScrollReveal key={i} delay={i * 0.1}>
                <div className="glass-card p-6 hover-lift group">
                  <div className="text-xs font-mono font-semibold text-primary mb-3">{item.step}</div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">{item.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── 6 INTELLIGENCE LAYERS ─── */}
      <section className="py-20 md:py-28 section-padding bg-card/50">
        <div className="container-wide">
          <ScrollReveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3">6 layers of AI protecting every login</h2>
              <p className="text-muted-foreground text-lg max-w-xl mx-auto">Our multi-model approach ensures no attack goes undetected</p>
            </div>
          </ScrollReveal>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f, i) => (
              <ScrollReveal key={i} delay={i * 0.08}>
                <div className="glass-card p-6 h-full hover-lift group">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/15 transition-colors">
                    <f.icon className="text-primary" size={20} />
                  </div>
                  <h3 className="text-base font-semibold text-foreground mb-2">{f.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── COMPARISON TABLE ─── */}
      <section className="py-20 md:py-28 section-padding">
        <div className="container-narrow">
          <ScrollReveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3">Why choose AuthDNA?</h2>
              <p className="text-muted-foreground text-lg">See how we compare to alternatives</p>
            </div>
          </ScrollReveal>
          <ScrollReveal>
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-4 font-medium text-muted-foreground">Feature</th>
                      <th className="p-4 font-semibold text-primary">AuthDNA</th>
                      <th className="p-4 font-medium text-muted-foreground">Okta</th>
                      <th className="p-4 font-medium text-muted-foreground">Auth0</th>
                      <th className="p-4 font-medium text-muted-foreground">In-House</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((row, i) => (
                      <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="p-4 font-medium text-foreground">{row.feature}</td>
                        <td className="p-4 text-center font-semibold text-foreground"><CellValue value={row.us} /></td>
                        <td className="p-4 text-center text-muted-foreground"><CellValue value={row.okta} /></td>
                        <td className="p-4 text-center text-muted-foreground"><CellValue value={row.auth0} /></td>
                        <td className="p-4 text-center text-muted-foreground"><CellValue value={row.inhouse} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ─── TESTIMONIALS ─── */}
      <section className="py-20 md:py-28 section-padding bg-card/50">
        <div className="container-narrow">
          <ScrollReveal>
            <div className="text-center mb-14">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3">Trusted by security-first teams</h2>
            </div>
          </ScrollReveal>
          <div className="grid md:grid-cols-3 gap-5">
            {testimonials.map((t, i) => (
              <ScrollReveal key={i} delay={i * 0.1}>
                <div className="glass-card p-6 h-full flex flex-col hover-lift">
                  <div className="flex gap-0.5 mb-4">
                    {Array.from({ length: t.stars }).map((_, j) => (
                      <Star key={j} className="text-warning fill-warning" size={14} />
                    ))}
                  </div>
                  <p className="text-sm text-foreground leading-relaxed mb-4 flex-1">"{t.quote}"</p>
                  <div>
                    <div className="text-sm font-semibold text-foreground">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.role}</div>
                  </div>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ─── CTA ─── */}
      <section className="py-20 md:py-28 section-padding">
        <div className="container-narrow">
          <ScrollReveal>
            <div className="glass-card p-10 md:p-16 text-center bg-gradient-to-br from-primary/[0.06] to-accent/[0.04]">
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                Protect your users' logins in 30 minutes
              </h2>
              <p className="text-muted-foreground text-lg mb-8 max-w-lg mx-auto">
                Start free with 100 requests per hour. No credit card required.
              </p>
              <Link to="/register">
                <Button variant="hero" size="lg">
                  Get Free API Key
                  <ArrowRight size={18} />
                </Button>
              </Link>
            </div>
          </ScrollReveal>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
