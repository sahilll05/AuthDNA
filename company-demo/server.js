/**
 * Demo company server at localhost:3000
 * Simulates a company's login page that integrates AuthDNA for risk evaluation.
 */
const express = require('express');
const path = require('path');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname)));

// Proxy the evaluate call server-side to avoid exposing the API key in the browser
app.post('/api/login', async (req, res) => {
  const { username, password, deviceContext, simulatedIp, simulatedFails, simulatedRole, simulatedResource } = req.body;

  const apiKey = process.env.AUTHDNA_API_KEY || '';
  const authdnaUrl = process.env.AUTHDNA_URL || 'http://localhost:8000';

  if (!apiKey) {
    return res.status(500).json({ error: 'AUTHDNA_API_KEY not configured. See README.' });
  }

  // Determine IP
  const realIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
  const clientIp = simulatedIp || realIp;

  // Build the evaluate payload
  const payload = {
    user_id: username,
    resource: simulatedResource || 'dashboard',
    failed_attempts: simulatedFails || 0,
    role: simulatedRole || 'viewer',
    client_context: deviceContext || null,
    ip: clientIp
  };

  try {
    const fetch_provider = (typeof fetch !== 'undefined') ? fetch : require('node-fetch');
    const evalResp = await fetch_provider(`${authdnaUrl}/v1/evaluate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify(payload),
    });

    const result = await evalResp.json();

    if (!evalResp.ok) {
      return res.status(evalResp.status).json({ error: result.detail || 'AuthDNA error' });
    }

    // In a real app you'd check result.decision and enforce MFA / block here
    const loginAllowed = result.decision !== 'BLOCK';

    res.json({
      success: loginAllowed,
      decision: result.decision,
      request_id: result.request_id,
      ip: result.ip,
      country: result.country,
      city: result.city
    });
  } catch (err) {
    console.error('AuthDNA evaluate error:', err);
    res.status(500).json({ error: 'Failed to contact AuthDNA: ' + err.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  const key = process.env.AUTHDNA_API_KEY || '';
  console.log(`\n🏢 Demo Company Site running at http://localhost:${PORT}`);
  console.log(`   AuthDNA backend: ${process.env.AUTHDNA_URL || 'http://localhost:8000'}`);
  if (!key || key === 'sk_live_put_your_key_here') {
    console.log(`\n   ⚠️  Set AUTHDNA_API_KEY in company-demo/.env to enable risk scoring`);
    console.log(`   Copy .env.example → .env and paste your API key\n`);
  } else {
    console.log(`   ✅ API key loaded: ${key.substring(0, 12)}... (${key.length} chars)`);
    console.log(`   ✅ Key trimmed length: ${key.trim().length} chars (should match above)`);
  }
});
