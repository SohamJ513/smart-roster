import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import ResourcePage from './components/ResourcePage'
import RosterHome from './pages/RosterHome'
import RosterPage from './pages/RosterPage'
import { RESOURCES } from './resources'

export default function App() {
  const qc = useQueryClient()
  const reset = useMutation({ mutationFn: api.resetDemo, onSuccess: () => qc.invalidateQueries() })
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Smart Roster</div>
        <nav>
          <NavLink to="/roster">Rosters</NavLink>
          <p className="nav-title">Configuration</p>
          {RESOURCES.map((r) => <NavLink key={r.path} to={`/config/${r.path}`}>{r.title}</NavLink>)}
        </nav>
        <button className="link reset" onClick={() => reset.mutate()} disabled={reset.isPending}>
          {reset.isPending ? 'Resetting…' : 'Reset demo data'}
        </button>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/roster" replace />} />
          <Route path="/roster" element={<RosterHome />} />
          <Route path="/roster/:id" element={<RosterPage />} />
          {RESOURCES.map((r) => <Route key={r.path} path={`/config/${r.path}`} element={<ResourcePage spec={r} />} />)}
        </Routes>
      </main>
    </div>
  )
}
