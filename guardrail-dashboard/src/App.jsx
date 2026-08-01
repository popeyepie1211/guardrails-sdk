import { useState } from 'react';
import Dashboard from './Dashboard';
import GovernancePanel from './GovernancePanel';
import CyberBackground from './CyberBackground';
import { Shield, Activity } from 'lucide-react';

const TABS = [
  { id: 'vitals', label: 'Vitals', icon: <Activity size={14} /> },
  { id: 'governance', label: 'Governance', icon: <Shield size={14} /> },
];

function App() {
  const [activeTab, setActiveTab] = useState('vitals');

  return (
    <div className="App min-h-screen bg-[#070707] relative">
      {activeTab === 'governance' && <CyberBackground />}

      {/* Tab Bar */}
      <div className="sticky top-0 z-50 backdrop-blur-xl bg-[#070707]/80 border-b border-orange-500/15">
        <div className="flex items-center gap-1 px-8 py-2">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-black uppercase tracking-wider
                transition-all duration-200
                ${activeTab === tab.id
                  ? 'bg-orange-500/15 text-orange-300 border border-orange-500/40 shadow-[0_0_12px_rgba(249,115,22,0.15)]'
                  : 'text-orange-200/40 hover:text-orange-200/70 hover:bg-orange-500/5 border border-transparent'
                }
              `}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'vitals' && <Dashboard />}
      {activeTab === 'governance' && (
        <div className="relative z-10">
          <div className="absolute top-[-20%] left-[20%] w-[650px] h-[500px] bg-orange-600/20 rounded-full blur-[150px] pointer-events-none z-[1]" />
          <div className="absolute top-[-18%] right-[-8%] w-[520px] h-[420px] bg-red-600/15 rounded-full blur-[130px] pointer-events-none z-[1]" />
          <GovernancePanel />
        </div>
      )}
    </div>
  );
}

export default App;