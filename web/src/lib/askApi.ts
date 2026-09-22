export type AskRoute = 'semantic' | 'graph' | 'both'

export type AskMeta = {
  route: AskRoute
  semantic_hits: unknown[]
  graph_hits: unknown[]
}

export type AskResponse = {
  answer: string
  route: AskRoute
  semantic_hits: unknown[]
  graph_hits: unknown[]
}

export async function askQuestion(question: string): Promise<AskResponse> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!res.ok) {
    throw new Error(`Ask request failed (${res.status})`)
  }

  return res.json() as Promise<AskResponse>
}

/**
 * Consume GET /api/ask/stream SSE:
 * - default events: `data: <text delta>`
 * - final event: `event: done` with JSON meta
 */
export async function askQuestionStream(
  question: string,
  onDelta: (text: string) => void,
  onDone?: (meta: AskMeta) => void,
): Promise<void> {
  const url = `/api/ask/stream?question=${encodeURIComponent(question)}`
  const res = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
  })

  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed (${res.status})`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'

  const flushBlock = (block: string) => {
    const lines = block.split(/\r?\n/)
    let eventName = currentEvent
    const dataLines: string[] = []

    for (const line of lines) {
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        // Preserve leading space after "data:" only if present once (SSE spec)
        dataLines.push(line.slice(5).startsWith(' ') ? line.slice(6) : line.slice(5))
      }
    }

    const data = dataLines.join('\n')
    if (eventName === 'done') {
      try {
        const meta = JSON.parse(data) as AskMeta
        onDone?.(meta)
      } catch {
        onDone?.({ route: 'both', semantic_hits: [], graph_hits: [] })
      }
    } else if (eventName === 'error') {
      throw new Error(data || 'Stream error')
    } else if (data) {
      onDelta(data)
    }

    currentEvent = 'message'
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() ?? ''

    for (const block of parts) {
      if (block.trim()) flushBlock(block)
    }
  }

  if (buffer.trim()) {
    flushBlock(buffer)
  }
}
