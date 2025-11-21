import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import WanList from './pages/WanList';
import WanDetail from './pages/WanDetail';
import PeerDetail from './pages/PeerDetail';
import Services from './pages/Services';
import Jobs from './pages/Jobs';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/wan" element={<WanList />} />
        <Route path="/wan/:wanId" element={<WanDetail />} />
        <Route path="/peers/:peerId" element={<PeerDetail />} />
        <Route path="/services" element={<Services />} />
        <Route path="/jobs" element={<Jobs />} />
      </Routes>
    </Layout>
  );
}

export default App;
