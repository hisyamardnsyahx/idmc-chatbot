import { cn } from './lib/utils'
import { ChatOverlay } from './components/chatbot'
import type { ChatUser } from './components/chatbot'

// Static sample data for the local host page only.
const user: ChatUser = { name: 'User', role: 'Pengguna' }

const suggestions = ['Dashboard Koperasi', 'Dashboard Koperasi', 'Dashboard Koperasi']

// Empty host page standing in for the dashboard the widget will float over.
function App() {
  return (
    <div
      className={cn(
        'idmc-host',
        '[min-block-size:100vh] [background:var(--idmc-color-neutral-300)]',
      )}
    >
      <ChatOverlay user={user} suggestions={suggestions} />
    </div>
  )
}

export default App
