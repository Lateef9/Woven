import express from 'express';
import cors from 'cors';
import { generateMockThread } from './mockAdapter.js';

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Webhook endpoint
app.post('/webhook', (req, res) => {
  const data = req.body;
  console.log('Received webhook data:', data);
  res.json({ status: 'received' });
});

// Mock thread endpoint
app.get('/trigger-mock', (req, res) => {
  const mockData = generateMockThread();
  res.json(mockData);
});

app.get('/', (req, res) => {
  res.json("Hiiii");
});

// Start the server
app.listen(PORT, () => {
  console.log(`Bot microservice is running on http://localhost:${PORT}`);
});
