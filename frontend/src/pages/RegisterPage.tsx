// src/pages/RegisterPage.tsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { registerTenant } from "@/api/auth";

export default function RegisterPage() {
  const [form, setForm] = useState({
    companyName: "",
    email: "",
    adminSecret: "",
    tier: "free",
    webhookUrl: "",
  });
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [keySaved, setKeySaved] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const resp = await registerTenant({
        company_name: form.companyName,
        email: form.email,
        admin_secret: form.adminSecret,
        tier: form.tier,
        webhook_url: form.webhookUrl || undefined,
      });
      const apiKey = resp.data?.api_key;
      setRevealedKey(apiKey);
      if (apiKey) await login(apiKey);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  const copyKey = () => {
    if (revealedKey) {
      navigator.clipboard.writeText(revealedKey);
      toast.success("API key copied to clipboard!");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      {/* Header — matches your existing 8081 style */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-2 mb-4">
          <div className="w-10 h-10 rounded-full bg-teal-600 flex items-center justify-center">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <span className="text-2xl font-bold">AuthDNA</span>
        </div>
        <h1 className="text-2xl font-bold">Create your account</h1>
        <p className="text-muted-foreground mt-1">Get your API key in 30 seconds</p>
      </div>

      {/* Form Card */}
      <Card className="w-full max-w-md">
        <form onSubmit={handleSubmit}>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="companyName">Company Name</Label>
              <Input
                id="companyName"
                value={form.companyName}
                onChange={(e) => setForm({ ...form, companyName: e.target.value })}
                placeholder="company name"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Work Email</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@company.com"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="adminSecret">Admin Secret</Label>
              <Input
                id="adminSecret"
                type="password"
                value={form.adminSecret}
                onChange={(e) => setForm({ ...form, adminSecret: e.target.value })}
                placeholder="Provided by platform admin"
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Plan</Label>
              <Select value={form.tier} onValueChange={(v) => setForm({ ...form, tier: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free — 100 req/hour</SelectItem>
                  <SelectItem value="pro">Pro — 1,000 req/hour</SelectItem>
                  <SelectItem value="enterprise">Enterprise — 10,000 req/hour</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhookUrl">
                Webhook URL <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="webhookUrl"
                type="url"
                value={form.webhookUrl}
                onChange={(e) => setForm({ ...form, webhookUrl: e.target.value })}
                placeholder="https://your-server.com/webhook"
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>

          <CardFooter className="flex flex-col gap-4">
            <Button type="submit" className="w-full bg-teal-600 hover:bg-teal-700" disabled={isLoading}>
              {isLoading ? "Creating Account..." : "Create Account & Get API Key →"}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Already have an API key?{" "}
              <Link to="/login" className="text-teal-600 hover:underline">
                Log in
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>

      {/* API Key Reveal Dialog */}
      <Dialog open={!!revealedKey} onOpenChange={() => { }}>
        <DialogContent className="sm:max-w-lg" onInteractOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>🎉 Welcome to AuthDNA!</DialogTitle>
            <DialogDescription>
              Your company has been registered. Save your API key now — it won't be shown again!
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="bg-muted rounded-lg p-4 flex items-center gap-3 border border-teal-500/30">
              <code className="text-sm font-mono text-teal-600 flex-1 break-all">
                {revealedKey}
              </code>
              <Button size="sm" variant="secondary" onClick={copyKey}>
                📋 Copy
              </Button>
            </div>

            <Alert>
              <AlertDescription className="text-destructive font-medium">
                ⚠️ This key will NOT be shown again. Store it in your environment variables.
              </AlertDescription>
            </Alert>

            <div className="flex items-center gap-2">
              <Checkbox
                id="keySaved"
                checked={keySaved}
                onCheckedChange={(v) => setKeySaved(v === true)}
              />
              <Label htmlFor="keySaved" className="text-sm cursor-pointer">
                I have saved my API key securely
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button
              className="w-full bg-teal-600 hover:bg-teal-700"
              disabled={!keySaved}
              onClick={() => navigate("/app/dashboard")}
            >
              Go to Dashboard →
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}