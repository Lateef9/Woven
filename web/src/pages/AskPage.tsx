import { FormEvent, useEffect, useRef, useState } from 'react'
import { askQuestion, askQuestionStream, type AskMeta } from '../lib/askApi'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  meta?: AskMeta
}

function createId() {
  return crypto.randomUUID()
}

function formatMeta(meta: AskMeta): string {
  const facts = meta.semantic_hits?.length ?? 0
  const graph = meta.graph_hits?.length ?? 0
  return `route=${meta.route}, facts=${facts}, graph=${graph}`
}

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = listRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages])

  function updateAssistant(id: string, updater: (msg: ChatMessage) => ChatMessage) {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)))
  }

  async function handleSend(event?: FormEvent) {
    event?.preventDefault()
    const content = input.trim()
    if (!content || busy) return

    const assistantId = createId()
    setMessages((prev) => [
      ...prev,
      { id: createId(), role: 'user', content },
      { id: assistantId, role: 'assistant', content: 'Thinking...' },
    ])
    setInput('')
    setBusy(true)

    let streamed = ''

    try {
      await askQuestionStream(
        content,
        (delta) => {
          streamed += delta
          const text = streamed
          updateAssistant(assistantId, (msg) => ({
            ...msg,
            content: text,
          }))
        },
        (meta) => {
          updateAssistant(assistantId, (msg) => ({
            ...msg,
            content: streamed || msg.content,
            meta,
          }))
        },
      )

      if (!streamed) {
        // Stream finished with no text — try POST fallback
        throw new Error('Empty stream')
      }
    } catch {
      try {
        const result = await askQuestion(content)
        updateAssistant(assistantId, () => ({
          id: assistantId,
          role: 'assistant',
          content: result.answer || 'Sorry, the backend failed.',
          meta: {
            route: result.route,
            semantic_hits: result.semantic_hits,
            graph_hits: result.graph_hits,
          },
        }))
      } catch {
        updateAssistant(assistantId, (msg) => ({
          ...msg,
          content: 'Sorry, the backend failed.',
          meta: undefined,
        }))
      }
    } finally {
      setBusy(false)
    }
  }

  const canSend = input.trim().length > 0 && !busy

  return (
    <section className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">Ask</h2>
        <p className="text-slate-600">
          Chat with Woven&apos;s dual memory (semantic + graph).
        </p>
      </div>

      <div
        ref={listRef}
        className="min-h-0 flex-1 overflow-y-auto border-y border-slate-200 py-4"
      >
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">No messages yet. Ask a question below.</p>
        ) : (
          <ul className="space-y-4">
            {messages.map((message) => (
              <li key={message.id} className="flex flex-col gap-1">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  {message.role === 'user' ? 'You' : 'Woven'}
                </span>
                <p
                  className={`whitespace-pre-wrap text-sm leading-relaxed ${
                    message.role === 'user' ? 'text-slate-900' : 'text-slate-700'
                  }`}
                >
                  {message.content}
                </p>
                {message.role === 'assistant' && message.meta && (
                  <p className="text-xs text-slate-400">{formatMeta(message.meta)}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <form onSubmit={handleSend} className="flex items-end gap-3">
        <label className="sr-only" htmlFor="ask-input">
          Message
        </label>
        <textarea
          id="ask-input"
          rows={2}
          value={input}
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleSend()
            }
          }}
          placeholder="Ask about your team knowledge…"
          className="min-h-[2.75rem] flex-1 resize-none border-0 border-b border-slate-300 bg-transparent px-0 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="shrink-0 px-3 py-2 text-sm font-medium text-slate-900 disabled:cursor-not-allowed disabled:text-slate-300"
        >
          {busy ? '…' : 'Send'}
        </button>
      </form>
    </section>
  )
}
