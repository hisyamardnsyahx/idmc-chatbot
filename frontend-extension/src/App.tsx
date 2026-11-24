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
          'Volume kendaraan CCTV perbatasan kota',
          'Data kepegawaian ASN berdasarkan pendidikan',
          'Peta rencana arsitektur SPBE DIY',
        ]}
        conversationStore={previewConversationStore}
        expandedUrl={new URL('.', window.location.href).href}
      />
    )
  }
  return <ChatPage />
}
