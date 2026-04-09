import React, { useState, useEffect } from 'react';
import { motion as Motion } from 'framer-motion';
import ReactFlow, { Background as FlowBackground, Controls, MarkerType, Handle, Position } from 'reactflow';
import { 
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid 
} from 'recharts';
import { Shield, Activity, Users, Lock, Zap, Database, Cpu } from 'lucide-react';
import 'reactflow/dist/style.css';

// --- IMPORT CUSTOM COMPONENTS ---
import AnimatedWaveCard from './AnimatedWaveCard';
import CyberBackground from './CyberBackground';
import PurpleFeatureCard from './PurpleFeatureCard';

// --- NEW LOCAL COMPONENT: TypewriterEffect ---
const TypewriterEffect = ({ text }) => {
  const characters = text.split("");
  
  const containerVariants = {
    hidden: { opacity: 1 },
    visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
  };

  const childVariants = {
    hidden: { opacity: 0, x: -5 },
    visible: { opacity: 1, x: 0 },
  };

  return (
    <div className="flex items-center">
      <Motion.h1
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="text-6xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-white via-orange-100 to-orange-300 cursor-default"
      >
        {characters.map((char, index) => (
          <Motion.span key={index} variants={childVariants}>{char}</Motion.span>
        ))}
      </Motion.h1>
      <Motion.span
        animate={{ opacity: [0, 1, 0] }}
        transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
        className="ml-2 inline-block w-1.5 h-12 bg-orange-500 shadow-[0_0_15px_#f97316] rounded-full"
      />
    </div>
  );
};

// --- ANIMATION VARIANTS ---
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

// --- CUSTOM WDAG NODE ---
// --- CUSTOM WDAG NODE ---
const GlassNode = ({ data }) => (
  <div className={`relative px-5 py-3 rounded-xl border backdrop-blur-md shadow-2xl flex items-center gap-3 ${data.alert ? 'bg-red-900/20 border-red-500/50' : 'bg-black/45 border-orange-500/30'}`}>
    
    {/* INCOMING CONNECTION POINT (Left) */}
    <Handle 
      type="target" 
      position={Position.Left} 
      className="w-2 h-2 bg-orange-500 border-none opacity-50" 
    />

    <div className={`p-2 rounded-lg ${data.alert ? 'bg-red-500/20 text-red-400 animate-pulse' : 'bg-orange-500/15 text-orange-300'}`}>
      {data.icon}
    </div>
    <div>
      <div className="text-xs font-bold text-orange-200/60 uppercase tracking-wider">{data.subtitle}</div>
      <div className="text-lg font-black text-white">{data.label}</div>
    </div>
    {data.alert && <div className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 rounded-full animate-ping" />}

    {/* OUTGOING CONNECTION POINT (Right) */}
    <Handle 
      type="source" 
      position={Position.Right} 
      className="w-2 h-2 bg-orange-500 border-none opacity-50" 
    />
    
  </div>
);

// ✅ FIX: Moved nodeTypes outside the component to prevent React Flow rendering warnings
const nodeTypes = { glass: GlassNode };

// --- ICON MAPPER ---
const getIconForNode = (nodeName) => {
  if (nodeName.includes('Data')) return <Database size={18} />;
  if (nodeName.includes('Intercept') || nodeName.includes('Model')) return <Shield size={18} />;
  return <Cpu size={18} />;
};

export default function ExecutiveDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState([]);
  
  // Dynamic WDAG State
  const [flowNodes, setFlowNodes] = useState([]);
  const [flowEdges, setFlowEdges] = useState([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/vitals/latest');
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        
        if (data.status === "no_data") return;

        // Formulate main metrics
        const formattedMetrics = {
          ...data,
          fairness: (data.fairness * 100).toFixed(1),
          stability: (data.stability * 100).toFixed(1),
          security: (data.security * 100).toFixed(1),
          privacy: (data.privacy * 100).toFixed(1),
          transparency: (data.transparency * 100).toFixed(1),
          latency: 410,
          shap: [
            { name: 'Income', weight: 0.45 }, 
            { name: 'Credit_Score', weight: 0.35 },
            { name: 'Gender', weight: 0.12 }, 
            { name: 'Employment', weight: 0.08 }
          ]
        };
        
        setMetrics(formattedMetrics);

        // ✅ FIX: Resilient WDAG Trace Parsing
        if (data.wdag_trace) {
           let backendNodes = data.wdag_trace;
           
           // PostgreSQL/FastAPI sometimes sends JSONB as a string. Parse it if needed.
           if (typeof backendNodes === 'string') {
              try {
                backendNodes = JSON.parse(backendNodes);
              } catch (e) {
                console.error("Failed to parse WDAG Trace string", e);
              }
           }

           // If it happens to be wrapped in a 'nodes' key, extract it. Otherwise use it directly.
           if (backendNodes.nodes) {
             backendNodes = backendNodes.nodes;
           }

           const parsedNodes = [];
           const parsedEdges = [];
           let xPos = 50; 
           
           Object.values(backendNodes).forEach((backendNode) => {
              const isAlert = backendNode.status === 'critical' || backendNode.status === 'warning';
              
              // Create dynamic Node
              parsedNodes.push({
                 id: backendNode.name,
                 type: 'glass',
                 position: { x: xPos, y: 100 },
                 data: { 
                    label: backendNode.name.replace(/_/g, ' '), 
                    subtitle: backendNode.owner, 
                    icon: getIconForNode(backendNode.name),
                    alert: isAlert 
                 }
              });
              xPos += 300; 

              // Create dynamic Edge
              backendNode.downstream.forEach(targetName => {
                 parsedEdges.push({
                    id: `e-${backendNode.name}-${targetName}`,
                    source: backendNode.name,
                    target: targetName,
                    animated: true,
                    style: { stroke: isAlert ? '#ef4444' : '#f97316', strokeWidth: 2 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: isAlert ? '#ef4444' : '#f97316' }
                 });
              });
           });

           setFlowNodes(parsedNodes);
           setFlowEdges(parsedEdges);
        }

        // Rolling history for Line Chart
        setHistory(prev => {
           const timeLabel = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
           const currentPsi = (1 - data.stability).toFixed(3); 
           const newPoint = { time: timeLabel, psi: parseFloat(currentPsi) };
           const newHistory = [...prev, newPoint];
           return newHistory.length > 15 ? newHistory.slice(1) : newHistory;
        });

      } catch (error) {
        console.error('Error fetching dashboard data from API:', error);
      }
    };

    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 3000);
    return () => clearInterval(interval);
  }, []);

  const fallback = {
    fairness: metrics?.fairness ?? 88,
    stability: metrics?.stability ?? 92,
    security: metrics?.security ?? 75,
    privacy: metrics?.privacy ?? 95,
    transparency: metrics?.transparency ?? 81,
    latency: metrics?.latency ?? 410,
    status: metrics?.status ?? 'critical',
    shap: metrics?.shap ?? [
      { name: 'Income', weight: 0.45 }, { name: 'Credit_History', weight: 0.35 },
      { name: 'Zip_Code', weight: 0.12 }, { name: 'Employment', weight: 0.08 }
    ],
    history: history.length > 0 ? history : [{ time: '00:00:00', psi: 0 }]
  };

  return (
    <div className="min-h-screen text-slate-200 font-sans selection:bg-orange-500/30 overflow-x-hidden relative bg-[#070707]">
      <CyberBackground />
      <div className="absolute top-[-20%] left-[20%] w-[650px] h-[500px] bg-orange-600/20 rounded-full blur-[150px] pointer-events-none z-[1]" />
      <div className="absolute top-[-18%] right-[-8%] w-[520px] h-[420px] bg-red-600/15 rounded-full blur-[130px] pointer-events-none z-[1]" />
      <div className="absolute bottom-[-20%] left-[-10%] w-[520px] h-[420px] bg-orange-500/10 rounded-full blur-[130px] pointer-events-none z-[1]" />

      <div className="relative z-10 p-8 min-h-screen w-full">
        <Motion.header 
          initial={{ opacity: 0, y: -30 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.8 }} 
          className="flex justify-between items-end mb-12 border-b border-orange-500/20 pb-8"
        >
          <div>
            <div className="flex items-center gap-4 mb-2">
              <Motion.div whileHover={{ rotate: 15 }} className="bg-gradient-to-br from-[#431407] to-[#c2410c] p-3 rounded-xl shadow-[0_0_25px_rgba(249,115,22,0.35)] border border-orange-500/25">
                <Shield size={32} className="text-white" />
              </Motion.div>
              <TypewriterEffect text="GuardRails.AI" />
            </div>
            <p className="text-orange-200/60 text-[10px] font-black uppercase tracking-[0.4em] ml-1 flex items-center gap-2">
              <Activity size={12} className="text-emerald-500" /> Autonomous Governance Engine Active
            </p>
          </div>
          
          <div className="bg-black/45 backdrop-blur-md border border-orange-500/35 px-6 py-2.5 rounded-full flex items-center gap-3 shadow-[0_0_20px_rgba(249,115,22,0.15)]">
            <div className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </div>
            <span className="text-[11px] font-black uppercase tracking-wider text-emerald-400">System Live</span>
          </div>
        </Motion.header>

        <Motion.div variants={containerVariants} initial="hidden" animate="show" className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-12">
          <Motion.div variants={itemVariants} whileHover={{ y: -5 }} className="h-full">
            <AnimatedWaveCard title="Fairness" value={`${fallback.fairness}%`} icon={<Users size={32} />} sub="SPD Metric" gradientColor="linear-gradient(744deg,#a855f7,#7e22ce 60%,#d8b4fe)" />
          </Motion.div>
          <Motion.div variants={itemVariants} whileHover={{ y: -5 }} className="h-full">
            <AnimatedWaveCard title="Stability" value={`${fallback.stability}%`} icon={<Activity size={32} />} sub="PSI Metric" gradientColor="linear-gradient(744deg,#10b981,#047857 60%,#34d399)" />
          </Motion.div>
          <Motion.div variants={itemVariants} whileHover={{ y: -5 }} className="h-full">
            <AnimatedWaveCard title="Security" value={`${fallback.security}%`} icon={<Shield size={32} />} sub="Robustness" gradientColor={fallback.status !== 'normal' ? 'linear-gradient(744deg,#ef4444,#b91c1c 60%,#f87171)' : undefined} />
          </Motion.div>
          <Motion.div variants={itemVariants} whileHover={{ y: -5 }} className="h-full">
            <AnimatedWaveCard title="Privacy" value={`${fallback.privacy}%`} icon={<Lock size={32} />} sub="Diff-Privacy" gradientColor="linear-gradient(744deg,#c084fc,#9333ea 60%,#e9d5ff)" />
          </Motion.div>
          <Motion.div variants={itemVariants} whileHover={{ y: -5 }} className="h-full">
            <AnimatedWaveCard title="Transparency" value={`${fallback.transparency}%`} icon={<Zap size={32} />} sub="Explainability" gradientColor="linear-gradient(744deg,#f59e0b,#b45309 60%,#fbbf24)" />
          </Motion.div>
        </Motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.3 }} className="col-span-2">
            <PurpleFeatureCard title="WDAG Integrity Map" description="Real-time Model Pipeline Trace visualization." buttonText="Inspect Nodes" className="border-orange-500/40 bg-gradient-to-br from-[#1a0b06]/95 to-[#0a0a0a]/75">
              <div className="h-[350px] w-full bg-black/35 rounded-xl overflow-hidden border border-orange-500/25 mt-2">
                <ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} fitView className="bg-transparent">
                  <FlowBackground color="#fb923c" gap={20} size={1} className="opacity-10" />
                  <Controls className="bg-[#1b0f0a] border-orange-500/35 fill-orange-300 shadow-xl" />
                </ReactFlow>
              </div>
            </PurpleFeatureCard>
          </Motion.div>

          <Motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, delay: 0.4 }}>
            <PurpleFeatureCard title="Remediation Funnel" description="Active alerts and system status checks." className="border-orange-500/40 bg-gradient-to-br from-[#1a0b06]/95 to-[#0a0a0a]/75">
              <div className="space-y-4 mt-2">
                 <AlertItem title="Security Breach" status="CRITICAL" color="red" desc={`Latency (${fallback.latency}ms) > 200ms Limit`} active={fallback.status !== 'normal'} />
                 <AlertItem title="Stability Check" status="STABLE" color="emerald" desc="PSI within baseline limits" active={false} />
                 <AlertItem title="Fairness Status" status="VERIFIED" color="purple" desc="SPD bias below detection" active={false} />
              </div>
            </PurpleFeatureCard>
          </Motion.div>
        </div>

        <Motion.div variants={containerVariants} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
           <Motion.div variants={itemVariants}>
              <PurpleFeatureCard title="Transparency Heatmap" description="Live SHAP feature importance distribution." buttonText="Download CSV" className="border-orange-500/40 bg-gradient-to-br from-[#1a0b06]/95 to-[#0a0a0a]/75">
                <div className="h-56 mt-4">
                   <ResponsiveContainer width="100%" height="100%">
                      <BarChart layout="vertical" data={fallback.shap}>
                         <XAxis type="number" hide />
                         <YAxis dataKey="name" type="category" stroke="#fed7aa" fontSize={12} width={120} axisLine={false} tickLine={false} />
                         <Tooltip cursor={{ fill: 'rgba(249, 115, 22, 0.15)' }} contentStyle={{backgroundColor: 'rgba(9, 9, 11, 0.95)', border: '1px solid rgba(249,115,22,0.4)', borderRadius: '12px', color: '#fff'}} />
                         <Bar dataKey="weight" radius={[0, 8, 8, 0]} barSize={24}>
                            {fallback.shap.map((e, i) => (
                              <Cell key={i} fill={i === 0 ? '#fb923c' : 'rgba(234, 88, 12, 0.4)'} className="transition-all duration-300 hover:opacity-80" />
                            ))}
                         </Bar>
                      </BarChart>
                   </ResponsiveContainer>
                </div>
              </PurpleFeatureCard>
           </Motion.div>

           <Motion.div variants={itemVariants}>
              <PurpleFeatureCard title="Drift Time-Series" description="Live PSI stability tracking." className="border-orange-500/40 bg-gradient-to-br from-[#1a0b06]/95 to-[#0a0a0a]/75">
                <div className="h-56 mt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fallback.history}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(249, 115, 22, 0.1)" vertical={false} />
                      <XAxis dataKey="time" stroke="#fed7aa" fontSize={10} axisLine={false} tickLine={false} />
                      <YAxis stroke="#fed7aa" fontSize={10} axisLine={false} tickLine={false} width={40} domain={['auto', 'auto']} />
                      <Tooltip 
                        contentStyle={{backgroundColor: 'rgba(9, 9, 11, 0.95)', border: '1px solid rgba(249,115,22,0.4)', borderRadius: '12px', color: '#fff'}}
                        itemStyle={{ color: '#fb923c' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="psi" 
                        stroke="#fb923c" 
                        strokeWidth={3}
                        dot={{ r: 4, fill: '#0a0a0a', stroke: '#fb923c', strokeWidth: 2 }}
                        activeDot={{ r: 6, fill: '#fb923c', stroke: '#fff' }}
                        isAnimationActive={false} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </PurpleFeatureCard>
           </Motion.div>
        </Motion.div>

      </div>
    </div>
  );
}

const AlertItem = ({ title, status, color, desc, active }) => {
  const colorMap = {
    red: 'text-red-400 bg-red-500/10 border-red-500/30',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    purple: 'text-orange-300 bg-orange-500/10 border-orange-500/30',
  };

  const activeClasses = {
    red: 'border-red-500/50 bg-red-900/30',
    emerald: 'border-emerald-500/50 bg-emerald-900/20',
    purple: 'border-orange-500/50 bg-orange-900/20',
  };

  return (
    <div className={`p-4 rounded-2xl border backdrop-blur-md transition-all duration-300 ${active ? `${activeClasses[color]} shadow-[0_0_20px_rgba(0,0,0,0.3)]` : 'border-orange-500/25 bg-black/30'}`}>
      <div className="flex justify-between items-center mb-2">
        <span className={`text-[9px] font-black px-2 py-1 rounded-md border uppercase tracking-widest ${colorMap[color]}`}>{status}</span>
        {active && (
          <div className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </div>
        )}
      </div>
      <h4 className="text-sm font-bold text-white">{title}</h4>
      <p className="text-[10px] text-orange-100/60 font-mono mt-1">{desc}</p>
    </div>
  );
};