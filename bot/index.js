import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { generateMockThread } from './mockAdapter.js';
import { ingestMessage } from './ingest.js';
import { hasSlackCredentials, startSlackBot } from './slackAdapter.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, '.env') });
dotenv.config({ path: path.join(__dirname, '..', '.env') });

const app = express();
const PORT = process.env.PORT || 3001;

const forcedMode = (process.env.BOT_MODE || '').toLowerCase();
const botMode =
  forcedMode === 'mock' || forcedMode === 'slack'
    ? forcedMode
    : hasSlackCredentials()
      ? 'slack'
      : 'mock';

// Middleware
app.use(cors());
app.use(express.json());

// Webhook endpoint (generic / future adapters)
app.post('/webhook', (req, res) => {
  const data = req.body;
  console.log('Received webhook data:', data);
  res.json({ status: 'received' });
});

// Mock thread endpoint — always available
app.get('/trigger-mock', async (req, res) => {
  try {
    const clearResponse = await fetch('http://localhost:8000/clear-stores', {
      method: 'POST',
    });
    if (!clearResponse.ok) {
      throw new Error(`clear-stores failed with status ${clearResponse.status}`);
    }

    const mockData = generateMockThread();
    await Promise.all(mockData.map((message) => ingestMessage(message)));

    res.json({
      status: 'success',
      messages_sent: mockData.length,
      stores_cleared: true,
      bot_mode: botMode,
    });
  } catch (error) {
    console.error('Error sending mock data to Python backend:', error.message);
    res.status(500).json({
      status: 'error',
      message: 'Failed to communicate with Python backend',
    });
  }
});

app.get('/', (req, res) => {
  res.json({ service: 'woven-bot', mode: botMode });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', mode: botMode });
});

async function main() {
  console.log(`Bot mode: ${botMode}`);

  if (botMode === 'slack') {
    try {
      await startSlackBot();
    } catch (error) {
      console.error('Failed to start Slack listener:', error.message);
      console.error('Falling back to mock-only HTTP mode.');
    }
  } else {
    console.log('Slack credentials not set — mock HTTP endpoints only.');
  }

  app.listen(PORT, () => {
    console.log(`Bot microservice is running on http://localhost:${PORT}`);
    console.log(`Mock ingest: GET http://localhost:${PORT}/trigger-mock`);
  });
}

main().catch((error) => {
  console.error('Bot failed to start:', error);
  process.exit(1);
});
