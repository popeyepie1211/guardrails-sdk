import React, { useState, useEffect, Fragment } from 'react';
import { motion as Motion, AnimatePresence } from 'framer-motion';
import {
  Shield, AlertTriangle, Activity, ChevronDown, ChevronRight,
  Clock, GitBranch, Users, Zap, FileText, ArrowRight
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const MODEL_ID = import.meta.env.VITE_MODEL_ID || 'hf_distilbert_burst_demo';

// ── Health → color mapping (reuses existing palette: red, orange, amber, yellow, emerald) ──
const HEALTH_CONFIG = {
  CRITICAL:  { bg: 'bg-red-500/15',    border: 'border-red-500/50',    text: 'text-red-400',     dot: 'bg-red-500',     glow: 'shadow-[0_0_12px_rgba(239,68,68,0.3)]' },
  UNHEALTHY: { bg: 'bg-orange-500/15',  border: 'border-orange-500/50',  text: 'text-orange-400',  dot: 'bg-orange-500',  glow: 'shadow-[0_0_12px_rgba(249,115,22,0.3)]' },
  DEGRADED:  { bg: 'bg-amber-500/15',   border: 'border-amber-500/50',   text: 'text-amber-400',   dot: 'bg-amber-500',   glow: 'shadow-[0_0_12px_rgba(245,158,11,0.3)]' },
  WATCH:     { bg: 'bg-yellow-500/15',  border: 'border-yellow-500/50',  text: 'text-yellow-400',  dot: 'bg-yellow-500',  glow: 'shadow-[0_0_12px_rgba(234,179,8,0.3)]' },
  HEALTHY:   { bg: 'bg-emerald-500/15', border: 'border-emerald-500/50', text: 'text-emerald-400', dot: 'bg-emerald-500', glow: 'shadow-[0_0_12px_rgba(16,185,129,0.3)]' },
};

const STATUS_COLORS = {
  CRITICAL: 'text-red-400 bg-red-500/10 border-red-500/30',
  WARNING:  'text-amber-400 bg-amber-500/10 border-amber-500/30',
  NORMAL:   'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  UNKNOWN:  'text-slate-400 bg-slate-500/10 border-slate-500/30',
};

// ── Animation variants (matches Dashboard.jsx pattern) ──
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } },
};

// ── Reusable glass card wrapper (matches existing dashboard aesthetic) ──
const GlassCard = ({ title, icon, children, className = '' }) => (
  <Motion.div
    variants={itemVariants}
    className={`rounded-2xl border border-orange-500/25 bg-black/40 backdrop-blur-md p-6 ${className}`}
  >
    {title && (
      <div className="flex items-center gap-3 mb-4">
        {icon && <div className="text-orange-400">{icon}</div>}
        <h3 className="text-sm font-black uppercase tracking-wider text-orange-200/70">{title}</h3>
      </div>
    )}
    {children}
  </Motion.div>
);

// ── Skeleton loader ──
const SkeletonLine = ({ width = 'w-full' }) => (
  <div className={`h-4 ${width} bg-orange-500/10 rounded animate-pulse`} />
);

const SkeletonCard = () => (
  <div className="rounded-2xl border border-orange-500/15 bg-black/30 p-6 space-y-3">
    <SkeletonLine width="w-1/3" />
    <SkeletonLine />
    <SkeletonLine width="w-2/3" />
    <SkeletonLine width="w-1/2" />
  </div>
);

// ══════════════════════════════════════════════
// SUB-COMPONENTS
// ══════════════════════════════════════════════

const GovernanceHealth = ({ health, diagnosis, severity, time }) => {
  const config = HEALTH_CONFIG[health] || HEALTH_CONFIG.HEALTHY;
  return (
    <GlassCard className={`${config.glow}`}>
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <div className={`relative flex h-4 w-4`}>
            {(health === 'CRITICAL' || health === 'UNHEALTHY') && (
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.dot} opacity-75`} />
            )}
            <span className={`relative inline-flex rounded-full h-4 w-4 ${config.dot}`} />
          </div>
          <div>
            <span className={`text-[10px] font-black px-3 py-1 rounded-md border uppercase tracking-widest ${config.bg} ${config.border} ${config.text}`}>
              {health}
            </span>
          </div>
          <div className="text-white">
            <span className="text-lg font-bold">{(diagnosis || '').replace(/_/g, ' ')}</span>
            <span className="text-orange-200/50 text-xs ml-3">Severity: {severity}</span>
          </div>
        </div>
        {time && (
          <div className="flex items-center gap-2 text-xs text-orange-200/40">
            <Clock size={12} />
            {new Date(time).toLocaleString()}
          </div>
        )}
      </div>
    </GlassCard>
  );
};

const DiagnosisSummary = ({ diagnosis, severity, confidence, verdict }) => (
  <GlassCard title="Diagnosis Summary" icon={<FileText size={16} />}>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
      <div>
        <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Diagnosis</div>
        <div className="text-white font-bold text-sm">{(diagnosis || '').replace(/_/g, ' ')}</div>
      </div>
      <div>
        <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Severity</div>
        <div className={`text-sm font-bold ${severity === 'CRITICAL' ? 'text-red-400' : severity === 'HIGH' ? 'text-orange-400' : severity === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'}`}>
          {severity}
        </div>
      </div>
      <div>
        <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Confidence</div>
        <div className="text-white font-bold text-sm">{confidence != null ? `${(confidence * 100).toFixed(0)}%` : '—'}</div>
      </div>
    </div>
    {verdict && (
      <div className="mt-3 text-xs text-orange-100/60 leading-relaxed border-t border-orange-500/15 pt-3">
        {verdict}
      </div>
    )}
  </GlassCard>
);

const MetricEvidenceTable = ({ evidence }) => {
  if (!evidence || evidence.length === 0) return null;
  return (
    <GlassCard title="Decision Evidence" icon={<Activity size={16} />}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-orange-500/20">
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Signal</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Source</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Status</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Strength</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Detail</th>
            </tr>
          </thead>
          <tbody>
            {evidence.map((item, idx) => (
              <tr key={idx} className="border-b border-orange-500/10 hover:bg-orange-500/5 transition-colors">
                <td className="py-2.5 px-3 text-white font-mono">{item.signal}</td>
                <td className="py-2.5 px-3 text-orange-100/70">{item.source}</td>
                <td className="py-2.5 px-3">
                  <span className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase tracking-widest ${STATUS_COLORS[item.status?.toUpperCase()] || STATUS_COLORS.UNKNOWN}`}>
                    {item.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-white font-mono">{item.strength != null ? item.strength.toFixed(2) : '—'}</td>
                <td className="py-2.5 px-3 text-orange-100/60 max-w-[250px] truncate">{item.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
};

const WdagGraph = ({ wdagContribution }) => {
  if (!wdagContribution) return null;
  const { summary, critical_nodes = [], warning_nodes = [], propagation_edges = [] } = wdagContribution;

  return (
    <GlassCard title="WDAG Contribution" icon={<GitBranch size={16} />}>
      {summary && (
        <p className="text-xs text-orange-100/60 leading-relaxed mb-4">{summary}</p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {critical_nodes.length > 0 && (
          <div>
            <div className="text-[10px] font-bold text-red-400/80 uppercase tracking-wider mb-2">Critical Nodes</div>
            <div className="space-y-1.5">
              {critical_nodes.map((node, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-xs text-red-300 font-mono">{node.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {warning_nodes.length > 0 && (
          <div>
            <div className="text-[10px] font-bold text-amber-400/80 uppercase tracking-wider mb-2">Warning Nodes</div>
            <div className="space-y-1.5">
              {warning_nodes.map((node, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-xs text-amber-300 font-mono">{node.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {propagation_edges.length > 0 && (
        <div className="mt-4">
          <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-2">Propagation Path</div>
          <div className="flex flex-wrap items-center gap-2">
            {propagation_edges.map((edge, i) => (
              <Fragment key={i}>
                {i === 0 && (
                  <span className="text-xs text-white font-mono px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20">
                    {edge.source.replace(/_/g, ' ')}
                  </span>
                )}
                <ArrowRight size={14} className="text-orange-500/60" />
                <span className="text-xs text-white font-mono px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20">
                  {edge.target.replace(/_/g, ' ')}
                </span>
              </Fragment>
            ))}
          </div>
        </div>
      )}
      {critical_nodes.length === 0 && warning_nodes.length === 0 && propagation_edges.length === 0 && (
        <p className="text-xs text-orange-100/40 italic">No affected nodes detected in the WDAG for this decision.</p>
      )}
    </GlassCard>
  );
};

const AffectedComponents = ({ components }) => {
  if (!components || components.length === 0) return null;
  return (
    <GlassCard title="Affected Components" icon={<Users size={16} />}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-orange-500/20">
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Name</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Status</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Owner</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Upstream</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Downstream</th>
            </tr>
          </thead>
          <tbody>
            {components.map((comp, idx) => (
              <tr key={idx} className="border-b border-orange-500/10 hover:bg-orange-500/5 transition-colors">
                <td className="py-2.5 px-3 text-white font-mono">{(comp.name || '').replace(/_/g, ' ')}</td>
                <td className="py-2.5 px-3">
                  <span className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase tracking-widest ${STATUS_COLORS[comp.status?.toUpperCase()] || STATUS_COLORS.UNKNOWN}`}>
                    {comp.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-orange-100/70">{comp.owner}</td>
                <td className="py-2.5 px-3 text-orange-100/50 font-mono text-[10px]">
                  {(comp.upstream || []).length > 0 ? comp.upstream.map(u => u.replace(/_/g, ' ')).join(', ') : '—'}
                </td>
                <td className="py-2.5 px-3 text-orange-100/50 font-mono text-[10px]">
                  {(comp.downstream || []).length > 0 ? comp.downstream.map(d => d.replace(/_/g, ' ')).join(', ') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
};

const RecommendedAction = ({ recommendedAction, governanceAction }) => {
  const actionPlan = governanceAction?.action_plan;

  return (
    <GlassCard title="Recommended Action" icon={<Zap size={16} />}>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-[10px] font-black px-3 py-1 rounded-md border uppercase tracking-widest bg-orange-500/15 border-orange-500/40 text-orange-300">
          {(recommendedAction || '').replace(/_/g, ' ')}
        </span>
        {actionPlan?.urgency && (
          <span className={`text-[10px] font-black px-3 py-1 rounded-md border uppercase tracking-widest ${
            actionPlan.urgency === 'IMMEDIATE' ? 'bg-red-500/15 border-red-500/40 text-red-300' : 'bg-amber-500/15 border-amber-500/40 text-amber-300'
          }`}>
            {actionPlan.urgency}
          </span>
        )}
      </div>

      {actionPlan && (
        <div className="space-y-3">
          {actionPlan.owner_hint && (
            <div>
              <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Owner</div>
              <div className="text-xs text-white">{actionPlan.owner_hint}</div>
            </div>
          )}
          {actionPlan.rationale && actionPlan.rationale.length > 0 && (
            <div>
              <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Rationale</div>
              <ul className="space-y-1">
                {actionPlan.rationale.map((r, i) => (
                  <li key={i} className="text-xs text-orange-100/60 flex items-start gap-2">
                    <span className="text-orange-500 mt-0.5">•</span> {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {actionPlan.supporting_actions && actionPlan.supporting_actions.length > 0 && (
            <div>
              <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Supporting Actions</div>
              <div className="flex flex-wrap gap-2">
                {actionPlan.supporting_actions.map((action, i) => (
                  <span key={i} className="text-[10px] font-mono px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20 text-orange-200/70">
                    {action.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </GlassCard>
  );
};

const ReportHistoryRow = ({ record }) => {
  const [expanded, setExpanded] = useState(false);
  const healthCfg = HEALTH_CONFIG[record.governance_health] || HEALTH_CONFIG.HEALTHY;

  return (
    <>
      <tr
        className="border-b border-orange-500/10 hover:bg-orange-500/5 transition-colors cursor-pointer"
        onClick={() => setExpanded(prev => !prev)}
      >
        <td className="py-2.5 px-3 text-orange-100/70">
          <div className="flex items-center gap-2">
            {expanded ? <ChevronDown size={12} className="text-orange-500" /> : <ChevronRight size={12} className="text-orange-500/50" />}
            {new Date(record.time).toLocaleString()}
          </div>
        </td>
        <td className="py-2.5 px-3 text-white font-mono text-[10px]">{record.batch_id}</td>
        <td className="py-2.5 px-3 text-white text-xs">{(record.diagnosis || '').replace(/_/g, ' ')}</td>
        <td className="py-2.5 px-3">
          <span className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase tracking-widest ${
            record.severity === 'CRITICAL' ? STATUS_COLORS.CRITICAL : record.severity === 'HIGH' ? STATUS_COLORS.WARNING : STATUS_COLORS.NORMAL
          }`}>
            {record.severity}
          </span>
        </td>
        <td className="py-2.5 px-3">
          <span className={`text-[9px] font-black px-2 py-0.5 rounded border uppercase tracking-widest ${healthCfg.bg} ${healthCfg.border} ${healthCfg.text}`}>
            {record.governance_health}
          </span>
        </td>
      </tr>
      <AnimatePresence>
        {expanded && record.report_json && (
          <tr>
            <td colSpan={5} className="p-0">
              <Motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden"
              >
                <div className="px-6 py-4 bg-black/20 border-b border-orange-500/15 space-y-3">
                  {record.report_json.executive_summary && (
                    <div>
                      <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Executive Summary</div>
                      <p className="text-xs text-orange-100/60 leading-relaxed">{record.report_json.executive_summary}</p>
                    </div>
                  )}
                  {record.report_json.governance_impact && record.report_json.governance_impact.length > 0 && (
                    <div>
                      <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Governance Impact</div>
                      <ul className="space-y-1">
                        {record.report_json.governance_impact.map((impact, i) => (
                          <li key={i} className="text-xs text-orange-100/60 flex items-start gap-2">
                            <span className="text-orange-500 mt-0.5">•</span> {impact}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {record.report_json.metric_evidence && record.report_json.metric_evidence.length > 0 && (
                    <div>
                      <div className="text-[10px] font-bold text-orange-200/50 uppercase tracking-wider mb-1">Metric Evidence</div>
                      <div className="flex flex-wrap gap-2">
                        {record.report_json.metric_evidence.map((m, i) => (
                          <span key={i} className={`text-[10px] font-mono px-2 py-1 rounded border ${STATUS_COLORS[m.status] || STATUS_COLORS.UNKNOWN}`}>
                            {m.label}: {m.value != null ? m.value : '—'} ({m.status})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Motion.div>
            </td>
          </tr>
        )}
      </AnimatePresence>
    </>
  );
};

const ReportHistory = ({ modelId }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!modelId) return;
    setLoading(true);
    setError(null);

    fetch(`${API_BASE_URL}/api/governance/history?model_id=${encodeURIComponent(modelId)}&limit=20`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setHistory(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [modelId]);

  if (loading) {
    return (
      <GlassCard title="Report History" icon={<Clock size={16} />}>
        <div className="space-y-2">
          <SkeletonLine />
          <SkeletonLine width="w-3/4" />
          <SkeletonLine width="w-1/2" />
        </div>
      </GlassCard>
    );
  }

  if (error) {
    return (
      <GlassCard title="Report History" icon={<Clock size={16} />}>
        <div className="flex items-center gap-2 text-red-400 text-xs">
          <AlertTriangle size={14} />
          Failed to load governance history: {error}
        </div>
      </GlassCard>
    );
  }

  if (history.length === 0) {
    return (
      <GlassCard title="Report History" icon={<Clock size={16} />}>
        <p className="text-xs text-orange-100/40 italic">No governance history available for this model.</p>
      </GlassCard>
    );
  }

  return (
    <GlassCard title="Report History" icon={<Clock size={16} />}>
      <p className="text-[10px] text-orange-200/40 mb-3">Click a row to expand the full report details.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-orange-500/20">
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Time</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Batch ID</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Diagnosis</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Severity</th>
              <th className="text-left py-2 px-3 text-orange-200/50 font-bold uppercase tracking-wider">Health</th>
            </tr>
          </thead>
          <tbody>
            {history.map((record, idx) => (
              <ReportHistoryRow key={`${record.batch_id}-${idx}`} record={record} />
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
};

// ══════════════════════════════════════════════
// MAIN GOVERNANCE PANEL
// ══════════════════════════════════════════════

export default function GovernancePanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEmpty, setIsEmpty] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setIsEmpty(false);

    fetch(`${API_BASE_URL}/api/governance/latest?model_id=${encodeURIComponent(MODEL_ID)}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(result => {
        if (result.data === null || result.status === 'no_data') {
          setIsEmpty(true);
          setData(null);
        } else {
          setData(result);
        }
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // ── Loading state ──
  if (loading) {
    return (
      <div className="space-y-6 p-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-orange-500 border-t-transparent" />
          <span className="text-sm text-orange-200/60 font-bold uppercase tracking-wider">Loading Governance Data…</span>
        </div>
        <SkeletonCard />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <SkeletonCard />
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-2xl border border-red-500/30 bg-red-500/5 backdrop-blur-md p-8 flex items-center gap-4">
          <AlertTriangle size={24} className="text-red-400 flex-shrink-0" />
          <div>
            <h3 className="text-white font-bold text-sm mb-1">Failed to Load Governance Data</h3>
            <p className="text-red-300/70 text-xs">Could not reach the governance API. Please check that the backend is running.</p>
            <p className="text-red-400/50 text-[10px] font-mono mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Empty state ──
  if (isEmpty) {
    return (
      <div className="p-8">
        <div className="rounded-2xl border border-orange-500/20 bg-black/30 backdrop-blur-md p-12 text-center">
          <Shield size={40} className="text-orange-500/30 mx-auto mb-4" />
          <h3 className="text-white font-bold text-lg mb-2">No Governance Data Available</h3>
          <p className="text-orange-200/50 text-sm">
            No governance decisions have been recorded yet for model <span className="font-mono text-orange-300">{MODEL_ID}</span>.
          </p>
          <p className="text-orange-200/30 text-xs mt-2">
            Governance data will appear here once the Digital Judge has processed at least one batch for this model.
          </p>
        </div>
      </div>
    );
  }

  // ── Data state ──
  const evidence = data.decision_json?.evidence || [];
  const affectedComponents = data.report_json?.affected_components || [];
  const wdagContribution = data.report_json?.wdag_contribution || null;
  const governanceAction = data.report_json?.recommended_governance_action || null;

  return (
    <Motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-6 p-8"
    >
      {/* Health Banner */}
      <Motion.div variants={itemVariants}>
        <GovernanceHealth
          health={data.governance_health}
          diagnosis={data.diagnosis}
          severity={data.severity}
          time={data.time}
        />
      </Motion.div>

      {/* Diagnosis + Evidence */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Motion.div variants={itemVariants}>
          <DiagnosisSummary
            diagnosis={data.diagnosis}
            severity={data.severity}
            confidence={data.confidence}
            verdict={data.verdict}
          />
        </Motion.div>
        <Motion.div variants={itemVariants}>
          <RecommendedAction
            recommendedAction={data.recommended_action}
            governanceAction={governanceAction}
          />
        </Motion.div>
      </div>

      {/* Evidence Table */}
      <Motion.div variants={itemVariants}>
        <MetricEvidenceTable evidence={evidence} />
      </Motion.div>

      {/* WDAG + Affected Components */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Motion.div variants={itemVariants}>
          <WdagGraph wdagContribution={wdagContribution} />
        </Motion.div>
        <Motion.div variants={itemVariants}>
          <AffectedComponents components={affectedComponents} />
        </Motion.div>
      </div>

      {/* History */}
      <Motion.div variants={itemVariants}>
        <ReportHistory modelId={MODEL_ID} />
      </Motion.div>
    </Motion.div>
  );
}
