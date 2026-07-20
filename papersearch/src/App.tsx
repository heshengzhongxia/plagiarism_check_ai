import TopNavBar from './components/Layout/TopNavBar'
import MainLayout from './components/Layout/MainLayout'
import LeftPanel from './components/Layout/LeftPanel'
import CenterPanel from './components/Layout/CenterPanel'
import RightPanel from './components/Layout/RightPanel'
import StatusBar from './components/Layout/StatusBar'

function App() {
  return (
    <div className="flex flex-col h-screen">
      <TopNavBar />
      <MainLayout>
        <LeftPanel />
        <CenterPanel />
        <RightPanel />
      </MainLayout>
      <StatusBar />
    </div>
  );
}

export default App
