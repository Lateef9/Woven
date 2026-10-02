import { useEffect, useState } from 'react'

type WikiChannel = {
  channel_id: string
  name: string
  platform: string
}

type WikiFact = {
  fact_text: string
  source_message_id?: string
}

type WikiPerson = {
  id: string
  name: string
  type: string
}

type WikiTriple = {
  source: string
  relation: string
  target: string
}

type WikiChannelPage = {
  channel_id: string
  name: string
  platform: string
  overview: string
  facts: WikiFact[]
  people: WikiPerson[]
  relationships: WikiTriple[]
}

export default function WikiPage() {
  const [channels, setChannels] = useState<WikiChannel[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [page, setPage] = useState<WikiChannelPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadChannels() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch('/api/wiki/channels')
        if (!res.ok) {
          throw new Error('Failed to load wiki channels')
        }
        const data = await res.json()
        if (!cancelled) {
          setChannels(Array.isArray(data.channels) ? data.channels : [])
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load wiki channels')
          setChannels([])
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadChannels()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setPage(null)
      return
    }

    const channelId = selectedId
    let cancelled = false

    async function loadDetail() {
      setDetailLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/wiki/channels/${encodeURIComponent(channelId)}`)
        if (!res.ok) {
          throw new Error('Failed to load channel wiki')
        }
        const data = (await res.json()) as WikiChannelPage
        if (!cancelled) {
          setPage(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load channel wiki')
          setPage(null)
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false)
        }
      }
    }

    loadDetail()
    return () => {
      cancelled = true
    }
  }, [selectedId])

  if (selectedId) {
    return (
      <section className="space-y-10">
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => {
              setSelectedId(null)
              setPage(null)
              setError(null)
            }}
            className="text-sm text-slate-500 hover:text-slate-900"
          >
            ← All channels
          </button>
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">
              {page?.name ? `#${page.name}` : 'Channel wiki'}
            </h2>
            <p className="text-sm text-slate-500">
              {page?.platform ?? '…'}
              {page?.channel_id ? ` · ${page.channel_id}` : ''}
            </p>
          </div>
        </div>

        {detailLoading && <p className="text-sm text-slate-500">Loading channel wiki…</p>}

        {!detailLoading && error && <p className="text-sm text-red-600">{error}</p>}

        {!detailLoading && !error && page && (
          <>
            <section className="space-y-3">
              <h3 className="text-lg font-semibold tracking-tight text-slate-900">Overview</h3>
              <p className="max-w-2xl text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">
                {page.overview || 'No overview yet.'}
              </p>
            </section>

            <section className="space-y-3">
              <h3 className="text-lg font-semibold tracking-tight text-slate-900">Facts</h3>
              {page.facts.length === 0 ? (
                <p className="text-sm text-slate-500">No facts for this channel yet.</p>
              ) : (
                <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
                  {page.facts.map((fact, index) => (
                    <li key={`${fact.source_message_id ?? 'fact'}-${index}`}>
                      {fact.fact_text}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-3">
              <h3 className="text-lg font-semibold tracking-tight text-slate-900">People</h3>
              {page.people.length === 0 ? (
                <p className="text-sm text-slate-500">No people linked to this channel yet.</p>
              ) : (
                <ul className="space-y-1.5 text-sm text-slate-700">
                  {page.people.map((person) => (
                    <li key={person.id || person.name}>
                      <span className="font-medium text-slate-900">{person.name}</span>
                      {person.id && (
                        <span className="ml-2 font-mono text-xs text-slate-400">{person.id}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-3">
              <h3 className="text-lg font-semibold tracking-tight text-slate-900">Graph</h3>
              {page.relationships.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No relationships for this channel yet.
                </p>
              ) : (
                <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
                  {page.relationships.map((t, index) => (
                    <li key={`${t.source}-${t.relation}-${t.target}-${index}`}>
                      <span className="font-medium text-slate-900">{t.source}</span>
                      <span className="text-slate-400"> — </span>
                      <span className="text-slate-500">{t.relation}</span>
                      <span className="text-slate-400"> → </span>
                      <span className="font-medium text-slate-900">{t.target}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </section>
    )
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight">Wiki</h2>
        <p className="max-w-2xl text-slate-600">
          Per-channel knowledge pages built from ingested conversations.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading channels…</p>}

      {!loading && error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && channels.length === 0 && (
        <p className="text-sm text-slate-500">
          No channels yet. Ingest a conversation to start building the wiki.
        </p>
      )}

      {!loading && !error && channels.length > 0 && (
        <ul className="divide-y divide-slate-200 border-y border-slate-200">
          {channels.map((channel) => (
            <li key={channel.channel_id}>
              <button
                type="button"
                onClick={() => setSelectedId(channel.channel_id)}
                className="flex w-full items-baseline justify-between gap-4 py-3 text-left hover:bg-slate-50"
              >
                <span className="font-medium text-slate-900">#{channel.name}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {channel.platform}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
