const INGEST_URL = process.env.INGEST_URL || 'http://localhost:8000/ingest-mock';

/**
 * POST a Phase-1 Message schema object to the FastAPI ingest endpoint.
 */
export async function ingestMessage(message) {
  const response = await fetch(INGEST_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Ingest failed (${response.status}): ${body}`);
  }

  return response.json().catch(() => ({ status: 'ok' }));
}
