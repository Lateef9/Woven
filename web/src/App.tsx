import { useState } from 'react'
import ChannelsPage from './pages/ChannelsPage'
import AskPage from './pages/AskPage'
import WikiPage from './pages/WikiPage'

type Page = 'channels' | 'ask' | 'wiki'

const NAV: { id: Page; label: string }[] = [
  { id: 'channels', label: 'Channels' },
  { id: 'ask', label: 'Ask' },
  { id: 'wiki', label: 'Wiki' },
]

function App() {
  const [page, setPage] = useState<Page>('ask')

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200/80 bg-white/70 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-4">
          <div className="text-lg font-semibold tracking-tight text-slate-900">Woven</div>
          <nav className="flex items-center gap-1">
            {NAV.map((item, index) => (
              <div key={item.id} className="flex items-center gap-1">
                {index > 0 && <span className="px-1 text-slate-300">|</span>}
                <button
                  type="button"
                  onClick={() => setPage(item.id)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    page === item.id
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              </div>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        {page === 'channels' && <ChannelsPage />}
        {page === 'ask' && <AskPage />}
        {page === 'wiki' && <WikiPage />}
      </main>
    </div>
  )
}

export default App
