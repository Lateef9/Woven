import { FormEvent, useEffect, useRef, useState } from 'react'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

function createId() {
  return crypto.randomUUID()
}

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = listRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages])

  function handleSend(event?: FormEvent) {
    event?.preventDefault()
    const content = input.trim()
    if (!content) return

    setMessages((prev) => [
      ...prev,
      { id: createId(), role: 'user', content },
      { id: createId(), role: 'assistant', content: 'Thinking...' },
    ])
    setInput('')
  }

  const canSend = input.trim().length > 0

  return (
    <section className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">Ask</h2>
        <p className="text-slate-600">
          Chat with Woven&apos;s dual memory. Backend wiring comes next.
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
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="Ask about your team knowledge…"
          className="min-h-[2.75rem] flex-1 resize-none border-0 border-b border-slate-300 bg-transparent px-0 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="shrink-0 px-3 py-2 text-sm font-medium text-slate-900 disabled:cursor-not-allowed disabled:text-slate-300"
        >
          Send
        </button>
      </form>
    </section>
  )
}
