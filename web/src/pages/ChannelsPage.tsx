import { useEffect, useState } from 'react'

type Channel = {
  channel_id: string
  name: string
  platform: string
}

export default function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch('/api/channels')
        if (!res.ok) {
          throw new Error(`Failed to load channels (${res.status})`)
        }
        const data = await res.json()
        if (!cancelled) {
          setChannels(Array.isArray(data) ? data : [])
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load channels')
          setChannels([])
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
    <section className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight">Channels</h2>
        <p className="max-w-2xl text-slate-600">
          Conversations ingested into Woven.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading channels…</p>}

      {!loading && error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {!loading && !error && channels.length === 0 && (
        <p className="text-sm text-slate-500">
          No channels yet. Trigger a mock ingest to populate this list.
        </p>
      )}

      {!loading && !error && channels.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-slate-500">
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Platform</th>
                <th className="py-2 font-medium">Channel ID</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((channel) => (
                <tr key={channel.channel_id} className="border-b border-slate-200">
                  <td className="py-3 pr-4 font-medium text-slate-900">{channel.name}</td>
                  <td className="py-3 pr-4 text-slate-600">{channel.platform}</td>
                  <td className="py-3 font-mono text-xs text-slate-500">{channel.channel_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
