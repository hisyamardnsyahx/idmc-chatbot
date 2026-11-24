import { ChatOverlay } from './components/chatbot'
import { ChatPage } from './web/ChatPage'
import { previewConversationStore } from './web/conversationStorage'

export default function App() {
  if (new URLSearchParams(window.location.search).get('view') === 'overlay') {
    return (
      <ChatOverlay
        user={{ name: 'User', role: 'Pengguna' }}
        suggestions={[
          'Berapa jumlah sentra industri kecil dan menengah (IKM) di DIY?',
          'Data penduduk DIY',
          'Statistik pendidikan',
          'Dashboard Koperasi',
        ]}
        conversationStore={previewConversationStore}
        expandedUrl={new URL('.', window.location.href).href}
      />
    )
  }
  return <ChatPage />
}
