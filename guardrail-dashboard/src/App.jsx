import { useEffect, useState } from 'react';
import Dashboard from './Dashboard';
import GovernancePanel from './GovernancePanel';
import CyberBackground from './CyberBackground';
import { Shield, Activity } from 'lucide-react';

const TABS = [
  { id: 'vitals', label: 'Vitals', icon: <Activity size={14} /> },
  { id: 'governance', label: 'Governance', icon: <Shield size={14} /> },
];
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const SELECTED_MODEL_KEY = 'guardrails:selected-model-id';

function App() {
  const [activeTab, setActiveTab] = useState('vitals');
  const [models, setModels] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    const loadModels = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/models`, { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const availableModels = await response.json();
        if (!Array.isArray(availableModels)) throw new Error('Invalid models response');

        let savedModelId = null;
        try {
          savedModelId = window.localStorage.getItem(SELECTED_MODEL_KEY);
        } catch {
          // Selection still works when browser storage is unavailable.
        }

        const modelId = availableModels.some(model => model.model_id === savedModelId)
          ? savedModelId
          : availableModels[0]?.model_id ?? null;

        if (controller.signal.aborted) return;
        setModels(availableModels);
        setSelectedModelId(modelId);
        if (modelId) {
          try {
            window.localStorage.setItem(SELECTED_MODEL_KEY, modelId);
          } catch {
            // Selection still works when browser storage is unavailable.
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) setModelsError(error.message);
      } finally {
        if (!controller.signal.aborted) setModelsLoading(false);
      }
    };

    loadModels();
    return () => controller.abort();
  }, []);

  const selectModel = (event) => {
    const modelId = event.target.value;
    setSelectedModelId(modelId);
    try {
      window.localStorage.setItem(SELECTED_MODEL_KEY, modelId);
    } catch {
      // Selection still works when browser storage is unavailable.
    }
  };

  return (
    <div className="App min-h-screen bg-[#070707] relative">
      {activeTab === 'governance' && <CyberBackground />}

      {/* Tab Bar */}
      <div className="sticky top-0 z-50 backdrop-blur-xl bg-[#070707]/80 border-b border-orange-500/15">
        <div className="flex flex-wrap items-center gap-1 px-8 py-2">
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
          {selectedModelId && (
            <div className="ml-auto flex items-center gap-2">
              <label htmlFor="model-selector" className="text-xs font-black uppercase tracking-wider text-orange-200/60">
                Model
              </label>
              <select
                id="model-selector"
                value={selectedModelId}
                onChange={selectModel}
                className="max-w-72 rounded-lg border border-orange-500/40 bg-[#1a0b06] px-3 py-2 text-xs font-bold text-orange-200 outline-none focus:border-orange-400"
              >
                {models.map(model => (
                  <option key={model.model_id} value={model.model_id}>
                    {model.model_name === model.model_id
                      ? model.model_id
                      : `${model.model_name} (${model.model_id})`}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Tab Content */}
      {modelsLoading && <p className="p-8 text-orange-200/60">Loading models...</p>}
      {modelsError && <p className="p-8 text-red-300">Failed to load models: {modelsError}</p>}
      {!modelsLoading && !modelsError && !selectedModelId && (
        <p className="p-8 text-orange-200/60">No models registered yet</p>
      )}
      {selectedModelId && activeTab === 'vitals' && <Dashboard key={selectedModelId} modelId={selectedModelId} />}
      {selectedModelId && activeTab === 'governance' && (
        <div className="relative z-10">
          <div className="absolute top-[-20%] left-[20%] w-[650px] h-[500px] bg-orange-600/20 rounded-full blur-[150px] pointer-events-none z-[1]" />
          <div className="absolute top-[-18%] right-[-8%] w-[520px] h-[420px] bg-red-600/15 rounded-full blur-[130px] pointer-events-none z-[1]" />
          <GovernancePanel key={selectedModelId} modelId={selectedModelId} />
        </div>
      )}
    </div>
  );
}

export default App;
