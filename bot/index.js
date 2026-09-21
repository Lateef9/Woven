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
app.get('/trigger-mock', async (req, res) => {
  try {
    // Clear previous data in Weaviate / Neo4j / Mongo before ingesting the new thread
    const clearResponse = await fetch('http://localhost:8000/clear-stores', {
      method: 'POST'
    });
    if (!clearResponse.ok) {
      throw new Error(`clear-stores failed with status ${clearResponse.status}`);
    }

    const mockData = generateMockThread();
    
    // Map each message to a fetch Promise
    const requests = mockData.map(message => 
      fetch('http://localhost:8000/ingest-mock', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(message)
      })
    );

    // Wait for all POST requests to finish
    await Promise.all(requests);
    
    res.json({ status: 'success', messages_sent: mockData.length, stores_cleared: true });
  } catch (error) {
    console.error('Error sending mock data to Python backend:', error.message);
    res.status(500).json({ status: 'error', message: 'Failed to communicate with Python backend' });
  }
});

app.get('/', (req, res) => {
  res.json("Hiiii");
});

// Start the server
app.listen(PORT, () => {
  console.log(`Bot microservice is running on http://localhost:${PORT}`);
});
