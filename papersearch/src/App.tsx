import { useState, useCallback } from 'react'
import TopNavBar from './components/Layout/TopNavBar'
import MainLayout from './components/Layout/MainLayout'
import LeftPanel from './components/Layout/LeftPanel'
import CenterPanel from './components/Layout/CenterPanel'
import RightPanel from './components/Layout/RightPanel'
import StatusBar from './components/Layout/StatusBar'
import UploadModal from './components/UploadModal/UploadModal'
import SettingsModal from './components/SettingsModal/SettingsModal'
import HistoryDrawer from './components/HistoryDrawer/HistoryDrawer'
import { useAppStore } from './stores/useAppStore'
import { useSSE } from './hooks/useSSE'

const API_BASE = 'http://localhost:5001'

function App() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  const currentTaskId = useAppStore((s) => s.currentTaskId)
  const startTask = useAppStore((s) => s.startTask)

  // 建立 SSE 连接，接收实时 Agent 事件
  useSSE(currentTaskId)

  const handleTextReady = useCallback(async (text: string) => {
    setUploadOpen(false)
    // Start a new task with the extracted text
    try {
      const settingsStr = localStorage.getItem('papersearch-settings')
      const settings = settingsStr ? JSON.parse(settingsStr) : {}
      const res = await fetch(`${API_BASE}/api/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paper: text,
          auto_mode: true,
          sources: settings.sources || undefined,
          threshold: settings.threshold || 60,
        }),
      })
      const data = await res.json()
      if (data.task_id) {
        startTask(data.task_id, {
          auto_mode: true,
          sources: settings.sources || [],
          threshold: settings.threshold || 60,
        })
      }
    } catch (e) {
      console.error('Failed to start task:', e)
    }
  }, [startTask])

  return (
    <div className="flex flex-col h-screen">
      <TopNavBar
        onUpload={() => setUploadOpen(true)}
        onNewTask={() => setUploadOpen(true)}
        onSettings={() => setSettingsOpen(true)}
        onHistory={() => setHistoryOpen(true)}
      />
      <MainLayout>
        <LeftPanel />
        <CenterPanel />
        <RightPanel />
      </MainLayout>
      <StatusBar />
      <UploadModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onTextReady={handleTextReady}
      />
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      <HistoryDrawer
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
      />
    </div>
  );
}

export default App
