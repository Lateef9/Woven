import { useEffect, useState } from 'react'

type WikiFact = {
  fact_text: string
  source_message_id?: string
}

type WikiTriple = {
  source: string
  relation: string
  target: string
}

export default function WikiPage() {
  const [facts, setFacts] = useState<WikiFact[]>([])
  const [triples, setTriples] = useState<WikiTriple[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [factsRes, graphRes] = await Promise.all([
          fetch('/api/wiki/facts?limit=50'),
          fetch('/api/wiki/graph?limit=50'),
        ])

        if (!factsRes.ok || !graphRes.ok) {
          throw new Error('Failed to load wiki knowledge')
        }

        const factsData = await factsRes.json()
        const graphData = await graphRes.json()

        if (!cancelled) {
          setFacts(Array.isArray(factsData.facts) ? factsData.facts : [])
          setTriples(Array.isArray(graphData.triples) ? graphData.triples : [])
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load wiki knowledge')
          setFacts([])
          setTriples([])
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="space-y-10">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight">Wiki</h2>
        <p className="max-w-2xl text-slate-600">
          Knowledge extracted from team conversations — facts and how things connect.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">Gathering knowledge…</p>}

      {!loading && error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {!loading && !error && (
        <>
          <section className="space-y-4">
            <h3 className="text-lg font-semibold tracking-tight text-slate-900">Facts</h3>
            {facts.length === 0 ? (
              <p className="text-sm text-slate-500">
                No facts yet. Ingest a conversation to start building the wiki.
              </p>
            ) : (
              <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
                {facts.map((fact, index) => (
                  <li key={`${fact.source_message_id ?? 'fact'}-${index}`}>
                    {fact.fact_text}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-4">
            <h3 className="text-lg font-semibold tracking-tight text-slate-900">Graph</h3>
            {triples.length === 0 ? (
              <p className="text-sm text-slate-500">
                No relationships yet. Graph links appear as entities are extracted.
              </p>
            ) : (
              <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
                {triples.map((t, index) => (
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
