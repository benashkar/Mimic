import { Routes, Route, Link } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'

function App() {
  return (
    <>
      <nav style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
        <Link to="/" style={{ marginRight: '1rem' }}>Dashboard</Link>
        <Link to="/prompts" style={{ marginRight: '1rem' }}>Prompts</Link>
        <Link to="/stories" style={{ marginRight: '1rem' }}>Stories</Link>
      </nav>
      <main style={{ padding: '1rem' }}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/prompts" element={<div><h1>Prompt Library</h1><p>Coming in Phase 3.</p></div>} />
          <Route path="/stories" element={<div><h1>Stories</h1><p>Coming in Phase 6.</p></div>} />
        </Routes>
      </main>
    </>
  )
}

export default App
