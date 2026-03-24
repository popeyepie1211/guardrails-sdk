import React, { useState, useEffect } from 'react';
import { motion as Motion } from 'framer-motion';
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import { 
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer 
} from 'recharts';
import { Shield, Activity, Users, Lock, Zap, AlertCircle, ChevronRight, CheckCircle, Database, Cpu } from 'lucide-react';
import 'reactflow/dist/style.css';

// --- ANIMATION VARIANTS ---
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

// --- CUSTOM WDAG NODES ---
// Creating custom nodes allows us to use standard HTML/Tailwind inside the graph
const GlassNode = ({ data }) => (
  <div className={`px-5 py-3 rounded-xl border backdrop-blur-md shadow-2xl flex items-center gap-3 ${data.alert ? 'bg-red-900/20 border-red-500/50' : 'bg-slate-900/60 border-blue-500/30'}`}>
    <div className={`p-2 rounded-lg ${data.alert ? 'bg-red-500/20 text-red-400 animate-pulse' : 'bg-blue-500/20 text-blue-400'}`}>
      {data.icon}
    </div>
    <div>
      <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">{data.subtitle}</div>
      <div className="text-lg font-black text-white">{data.label}</div>
    </div>
    {data.alert && (
      <div className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 rounded-full animate-ping" />
    )}
  </div>
);

const nodeTypes = { glass: GlassNode };

const WDAG_NODES = [
  { id: '1', type: 'glass', data: { label: 'Data Stream', subtitle: 'Input', icon: <Database size={18} /> }, position: { x: 50, y: 150 } },
  { id: '2', type: 'glass', data: { label: 'SDK Intercept', subtitle: 'Middleware', icon: <Shield size={18} /> }, position: { x: 350, y: 150 } },
  { id: '3', type: 'glass', data: { label: 'Vitals Engine', subtitle: 'Analysis', icon: <Cpu size={18} />, alert: true }, position: { x: 650, y: 150 } },
];

const WDAG_EDGES = [
  { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#3b82f6', strokeWidth: 2 } },
  { id: 'e2-3', source: '2', target: '3', animated: true, style: { stroke: '#ef4444', strokeWidth: 2 }, markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' } }
];

export default function ExecutiveDashboard() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    // Simulated fetch for demonstration
    const timer = setTimeout(() => setMetrics({ status: 'critical' }), 1000);
    return () => clearTimeout(timer);
  }, []);

  const fallback = {
    fairness: metrics?.fairness || 88,
    stability: metrics?.stability || 92,
    security: metrics?.security || 75,
    latency: metrics?.latency || 410,
    status: metrics?.status || 'critical',
    shap: [
      { name: 'Income', weight: 0.45 }, { name: 'Credit_History', weight: 0.35 },
      { name: 'Zip_Code', weight: 0.12 }, { name: 'Employment', weight: 0.08 }
    ]
  };

  return (
    <div className="min-h-screen bg-[#050914] text-slate-200 p-8 font-sans selection:bg-blue-500/30 overflow-hidden relative">
      
      {/* Background Glow Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-blue-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-emerald-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* 1. ANIMATED HEADER */}
      <Motion.header 
        initial={{ opacity: 0, y: -30 }} 
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="flex justify-between items-end mb-12 border-b border-slate-800/50 pb-8 relative z-10"
      >
        <div>
          <div className="flex items-center gap-4 mb-2">
            <Motion.div 
              whileHover={{ rotate: 15 }}
              className="bg-gradient-to-br from-blue-500 to-indigo-600 p-3 rounded-xl shadow-[0_0_30px_rgba(59,130,246,0.3)]"
            >
              <Shield size={32} className="text-white" />
            </Motion.div>
            <h1 className="text-5xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">
              GUARDRAIL <span className="text-blue-500 font-light italic">Executive</span>
            </h1>
          </div>
          <p className="text-slate-500 text-xs font-bold uppercase tracking-[0.3em] ml-1 flex items-center gap-2">
            <Activity size={12} className="text-emerald-500" /> Live Python Governance Engine Sync
          </p>
        </div>
        
        <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800/50 px-6 py-2.5 rounded-full flex items-center gap-3 shadow-lg">
          <div className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </div>
          <span className="text-[11px] font-black uppercase tracking-wider text-emerald-400">System Live</span>
        </div>
      </Motion.header>

      {/* 2. THE FIVE VITALS GAUGES */}
      <Motion.div 
        variants={containerVariants} 
        initial="hidden" 
        animate="show" 
        className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-12 relative z-10"
      >
        <VitalCard label="Fairness" val={fallback.fairness} icon={<Users/>} color="from-blue-400 to-blue-600" sub="SPD Metric" />
        <VitalCard label="Stability" val={fallback.stability} icon={<Activity/>} color="from-emerald-400 to-emerald-600" sub="PSI Metric" />
        <VitalCard label="Security" val={fallback.security} icon={<Shield/>} color="from-red-400 to-red-600" sub="Robustness" alert={fallback.status !== 'normal'} />
        <VitalCard label="Privacy" val={95} icon={<Lock/>} color="from-purple-400 to-purple-600" sub="Diff-Privacy" />
        <VitalCard label="Transparency" val={81} icon={<Zap/>} color="from-amber-400 to-amber-600" sub="Explainability" />
      </Motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
        
        {/* 3. WDAG INTERACTIVE MAP */}
        <Motion.div 
          initial={{ opacity: 0, scale: 0.95 }} 
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="col-span-2 bg-slate-900/30 backdrop-blur-xl border border-slate-800/50 rounded-3xl h-[500px] relative overflow-hidden shadow-2xl"
        >
          <div className="absolute top-6 left-8 z-10 bg-slate-950/50 p-4 rounded-2xl backdrop-blur-md border border-slate-800/50">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              WDAG Integrity Map <ChevronRight size={20} className="text-blue-500" />
            </h2>
            <p className="text-xs text-slate-400 mt-1">Real-time Model Pipeline Trace</p>
          </div>
          <ReactFlow 
            nodes={WDAG_NODES} 
            edges={WDAG_EDGES} 
            nodeTypes={nodeTypes}
            fitView 
            className="bg-transparent"
          >
            <Background color="#1e293b" gap={20} size={2} className="opacity-40" />
            <Controls className="bg-slate-900 border-slate-800 fill-white" />
          </ReactFlow>
        </Motion.div>

        {/* 4. ALERT & REMEDIATION FUNNEL */}
        <Motion.div 
          initial={{ opacity: 0, x: 20 }} 
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="bg-slate-900/30 backdrop-blur-xl border border-slate-800/50 rounded-3xl p-8 flex flex-col"
        >
          <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-6 flex items-center gap-2">
            <AlertCircle className="text-red-500" size={18} /> Remediation Funnel
          </h2>
          <div className="space-y-4 flex-grow">
             <AlertItem title="Security Breach" status="CRITICAL" color="red" desc={`Latency (${fallback.latency}ms) > 200ms Limit`} active={fallback.status !== 'normal'} />
             <AlertItem title="Stability Check" status="STABLE" color="emerald" desc="PSI within baseline (0.02)" active={false} />
             <AlertItem title="Fairness Status" status="VERIFIED" color="blue" desc="SPD bias below detection" active={false} />
          </div>
        </Motion.div>
      </div>

      <Motion.div 
        variants={containerVariants}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true }}
        className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8 relative z-10"
      >
         {/* 5. TRANSPARENCY (SHAP) HEATMAP */}
         <Motion.div variants={itemVariants} className="bg-slate-900/30 backdrop-blur-xl border border-slate-800/50 rounded-3xl p-8 shadow-xl">
            <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-8">Transparency Heatmap (SHAP)</h2>
            <div className="h-64">
               <ResponsiveContainer width="100%" height="100%">
                  <BarChart layout="vertical" data={fallback.shap}>
                     <XAxis type="number" hide />
                     <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={12} width={120} axisLine={false} tickLine={false} />
                     <Tooltip 
                        cursor={{ fill: 'rgba(30, 41, 59, 0.5)' }} 
                        contentStyle={{backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155', borderRadius: '12px', color: '#fff'}} 
                     />
                     <Bar dataKey="weight" radius={[0, 8, 8, 0]} barSize={24}>
                        {fallback.shap.map((e, i) => (
                          <Cell key={i} fill={i === 0 ? '#3b82f6' : '#334155'} className="transition-all duration-300 hover:opacity-80" />
                        ))}
                     </Bar>
                  </BarChart>
               </ResponsiveContainer>
            </div>
         </Motion.div>

         {/* 6. DISTRIBUTION OVERLAY */}
         <Motion.div variants={itemVariants} className="bg-slate-900/30 backdrop-blur-xl border border-slate-800/50 rounded-3xl p-8 shadow-xl">
            <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-8">Vitals Time-Series</h2>
            <div className="h-64 flex flex-col justify-center items-center border border-dashed border-slate-700/50 rounded-2xl bg-slate-950/30 group hover:border-slate-500 transition-colors duration-300">
               <Motion.div 
                  animate={{ rotate: 360 }} 
                  transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
               >
                 <Zap className="text-slate-600 group-hover:text-blue-500 transition-colors duration-300 mb-3" size={40} />
               </Motion.div>
               <p className="text-slate-500 font-mono text-xs uppercase tracking-widest group-hover:text-slate-300 transition-colors">Awaiting Live Drift Stream</p>
            </div>
         </Motion.div>
      </Motion.div>
    </div>
  );
}

// --- SUB-COMPONENTS ---

const VitalCard = ({ label, val, icon, color, sub, alert }) => (
  <Motion.div
    variants={itemVariants}
    whileHover={{ y: -5, scale: 1.02 }}
    className={`relative bg-slate-900/40 backdrop-blur-xl p-6 rounded-3xl border overflow-hidden transition-all duration-300 ${alert ? 'border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.15)]' : 'border-slate-800/50 hover:border-slate-700'}`}
  >
    {alert && <div className="absolute inset-0 bg-red-500/5 animate-pulse pointer-events-none" />}
    
    <div className="flex justify-between items-start mb-6 relative z-10">
      <div className={`p-3 rounded-2xl bg-slate-800/50 border border-slate-700/50 ${alert ? 'text-red-400' : 'text-slate-300'}`}>
        {icon}
      </div>
      <span className={`text-4xl font-black tracking-tighter ${alert ? 'text-red-400' : 'text-white'}`}>
        {val}<span className="text-lg text-slate-500">%</span>
      </span>
    </div>
    
    <div className="relative z-10">
      <h3 className="text-[11px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1">{label}</h3>
      <p className="text-[10px] text-slate-500 font-mono">{sub}</p>
    </div>

    <div className="h-1.5 w-full bg-slate-800/50 rounded-full mt-5 overflow-hidden relative z-10">
      <Motion.div 
        initial={{ width: 0 }} 
        animate={{ width: `${val}%` }} 
        transition={{ duration: 1.5, ease: "easeOut", delay: 0.5 }} 
        className={`h-full bg-gradient-to-r ${color} rounded-full`} 
      />
    </div>
  </Motion.div>
);

const AlertItem = ({ title, status, color, desc, active }) => {
  const colorMap = {
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  };

  return (
    <Motion.div 
      whileHover={{ scale: 1.02 }}
      className={`p-5 rounded-2xl border backdrop-blur-sm transition-all duration-300 ${active ? `border-${color}-500/40 bg-${color}-900/20 shadow-[0_0_15px_rgba(0,0,0,0.2)]` : 'border-slate-800/50 bg-slate-800/20'}`}
    >
      <div className="flex justify-between items-center mb-3">
        <span className={`text-[10px] font-black px-2.5 py-1 rounded-md border uppercase tracking-widest ${colorMap[color]}`}>
          {status}
        </span>
        {active && (
          <div className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-${color}-400 opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 bg-${color}-500`}></span>
          </div>
        )}
      </div>
      <h4 className="text-sm font-bold text-slate-200">{title}</h4>
      <p className="text-[11px] text-slate-500 font-mono mt-1.5">{desc}</p>
    </Motion.div>
  );
};