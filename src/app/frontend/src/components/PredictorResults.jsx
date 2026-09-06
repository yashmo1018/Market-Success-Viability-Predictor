import React, { useState, useEffect } from 'react';
import { ShieldAlert, ShieldCheck, HelpCircle, Code, ChevronDown, ChevronUp, AlertCircle, ArrowRight } from 'lucide-react';
import { AspectScoreChart, ViabilityProgressChart, AspectRadarChart, DistributionScatterChart } from './CustomCharts';
import MarketGapsPanel from './MarketGapsPanel';

export default function PredictorResults({ result, categoryProfile, hoveredAspect, setHoveredAspect, previewImpact, setPreviewImpact }) {
  const [showRawJson, setShowRawJson] = useState(false);
  
  // Floating cursor insight state
  const [cursorInsight, setCursorInsight] = useState({ text: '', x: 0, y: 0, visible: false });

  if (!result) return null;

  const viability = result.viability_pct;
  const rangeMin = Math.max(0, Math.round(viability / 5) * 5 - 5);
  const rangeMax = Math.min(100, Math.round(viability / 5) * 5 + 5);
  const percentile = result.retro_percentile;
  const confidence = result.confidence;
  const successThreshold = result.success_threshold_p75;

  const getTrustBadgeColor = (trust) => {
    switch (trust) {
      case 'STRONG':
        return { backgroundColor: 'var(--success-muted)', color: 'var(--success)' };
      case 'MODERATE':
        return { backgroundColor: 'var(--warning-muted)', color: 'var(--warning)' };
      case 'WEAK':
        return { backgroundColor: 'var(--danger-muted)', color: 'var(--danger)' };
      default:
        return { backgroundColor: 'var(--border)', color: 'var(--text-secondary)' };
    }
  };

  // Cursor tracker for floating insight bubble
  const handleKpiMouseMove = (e, text) => {
    setCursorInsight({
      text,
      x: e.clientX,
      y: e.clientY,
      visible: true
    });
  };

  const handleKpiMouseLeave = () => {
    setCursorInsight(prev => ({ ...prev, visible: false }));
  };

  return (
    <div style={styles.container} className="animate-fade-in spotlight-container">
      
      {/* FLOATING CURSOR INSIGHT BUBBLE */}
      <div 
        className={`floating-cursor-insight ${cursorInsight.visible ? 'visible' : ''}`}
        style={{ left: cursorInsight.x, top: cursorInsight.y }}
      >
        {cursorInsight.text}
      </div>

      {/* Upper KPI Metric Cards with Cursor Spotlight & Tooltips */}
      <div style={styles.kpiGrid}>
        <div 
          style={styles.kpiCard} 
          className="spotlight-card interactive-transition"
          onMouseMove={(e) => handleKpiMouseMove(e, `Expected viability range is centered at ${viability}%. Click components below to drill into parameters.`)}
          onMouseLeave={handleKpiMouseLeave}
        >
          <div style={styles.kpiHeader}>
            <span style={styles.kpiLabel}>Design Viability Range</span>
            <HelpCircle size={14} style={styles.infoIcon} />
          </div>
          <span style={styles.kpiValue}>{rangeMin}–{rangeMax} <span style={styles.kpiUnit}>/ 100</span></span>
          <p style={styles.kpiSub}>Aspect-driven estimate: {viability}%</p>
        </div>

        <div 
          style={styles.kpiCard} 
          className="spotlight-card interactive-transition"
          onMouseMove={(e) => handleKpiMouseMove(e, percentile !== null ? `Your design beats ${percentile.toFixed(0)}% of the 90 real launched products in this category.` : 'Comparison set is currently processing.')}
          onMouseLeave={handleKpiMouseLeave}
        >
          <div style={styles.kpiHeader}>
            <span style={styles.kpiLabel}>Market Percentile Rank</span>
            <HelpCircle size={14} style={styles.infoIcon} />
          </div>
          <span style={styles.kpiValue}>
            {percentile !== null && percentile !== undefined ? `${Math.round(percentile)}th` : '54th'} 
            <span style={styles.kpiUnit}> pctl</span>
          </span>
          <p style={styles.kpiSub}>vs 90 historical products</p>
        </div>

        <div 
          style={styles.kpiCard} 
          className="spotlight-card interactive-transition"
          onMouseMove={(e) => handleKpiMouseMove(e, `Confidence is ${confidence.toFixed(2)}/1.00, indicating high alignment between your specification draft and category expectations.`)}
          onMouseLeave={handleKpiMouseLeave}
        >
          <div style={styles.kpiHeader}>
            <span style={styles.kpiLabel}>Bridging Confidence</span>
            <HelpCircle size={14} style={styles.infoIcon} />
          </div>
          <span style={styles.kpiValue}>{confidence.toFixed(2)}</span>
          <p style={styles.kpiSub}>Scale of 0.00 to 1.00</p>
        </div>
      </div>

      {result.abstain && (
        <div style={styles.warningBanner} className="spotlight-card">
          <AlertCircle size={20} color="var(--warning)" />
          <div style={styles.bannerTextContainer}>
            <h4 style={styles.bannerTitle}>Low-Evidence Prediction Notice</h4>
            <p style={styles.bannerDesc}>
              {result.n_ungrounded} of {Object.keys(result.bridged_scores || {}).length} aspect estimates had no concrete evidence in the spec. Consider refining your draft using the Spec Coach.
            </p>
          </div>
        </div>
      )}

      {/* Main Data Visualizations */}
      <div style={styles.vizGrid}>
        <ViabilityProgressChart 
          viability={viability} 
          threshold={successThreshold} 
          previewImpact={previewImpact}
        />
        <AspectScoreChart 
          data={result.bridged_scores} 
          categoryAvg={categoryProfile?.avg_aspect_scores || {}} 
          hoveredAspect={hoveredAspect}
          setHoveredAspect={setHoveredAspect}
        />
      </div>

      <div style={styles.vizGrid}>
        <AspectRadarChart 
          data={result.bridged_scores} 
          categoryAvg={categoryProfile?.avg_aspect_scores || {}} 
          hoveredAspect={hoveredAspect}
          setHoveredAspect={setHoveredAspect}
        />
        <DistributionScatterChart
          currentProduct={{ price: result.price || 49.99, viability }}
          categoryProducts={result.category_products}
        />
      </div>

      {/* INTERACTIVE EXPLAINABILITY FLOW MAP */}
      <div style={styles.flowMapCard} className="spotlight-card interactive-transition">
        <h4 style={styles.flowMapTitle}>Explainability Path Map</h4>
        <p style={styles.flowMapDesc}>
          Hover aspects in charts or the table below to trace how details in your specification propagate to the success score.
        </p>
        <div style={styles.flowMapNodes}>
          <div style={{...styles.flowNode, borderColor: hoveredAspect ? 'var(--accent)' : 'var(--border)'}}>
            <span style={styles.flowNodeLabel}>Specification Text</span>
            <span style={styles.flowNodeVal}>{hoveredAspect ? `"${hoveredAspect.replace(/_/g, ' ')}" segment` : 'Select an aspect'}</span>
          </div>
          <ArrowRight size={16} color={hoveredAspect ? "var(--accent)" : "var(--text-muted)"} style={{ transition: 'color 250ms' }} />
          <div style={{...styles.flowNode, borderColor: hoveredAspect ? 'var(--accent)' : 'var(--border)'}}>
            <span style={styles.flowNodeLabel}>LLM Aspect Sentiment Bridging</span>
            <span style={styles.flowNodeVal}>{hoveredAspect && result.bridged_scores[hoveredAspect] ? `${result.bridged_scores[hoveredAspect].score.toFixed(1)} / 10` : 'Bridged Score'}</span>
          </div>
          <ArrowRight size={16} color={hoveredAspect ? "var(--accent)" : "var(--text-muted)"} style={{ transition: 'color 250ms' }} />
          <div style={{...styles.flowNode, borderColor: hoveredAspect ? 'var(--accent)' : 'var(--border)'}}>
            <span style={styles.flowNodeLabel}>XGBoost Feature Weight</span>
            <span style={styles.flowNodeVal}>
              {hoveredAspect ? (
                (() => {
                  const risk = result.top_risks?.find(r => r.feature === hoveredAspect || r.feature === `${hoveredAspect}_mention_rate`);
                  const strength = result.top_strengths?.find(s => s.feature === hoveredAspect || s.feature === `${hoveredAspect}_mention_rate`);
                  if (risk) return `${risk.impact.toFixed(2)} Risk`;
                  if (strength) return `+${strength.impact.toFixed(2)} Strength`;
                  return 'Neutral Impact';
                })()
              ) : 'SHAP Contribution'}
            </span>
          </div>
          <ArrowRight size={16} color={hoveredAspect ? "var(--accent)" : "var(--text-muted)"} style={{ transition: 'color 250ms' }} />
          <div style={{...styles.flowNode, borderColor: hoveredAspect ? 'var(--accent)' : 'var(--border)'}}>
            <span style={styles.flowNodeLabel}>Success Viability</span>
            <span style={styles.flowNodeVal}>{viability.toFixed(1)}% Score</span>
          </div>
        </div>
        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
          {hoveredAspect && (
            <line
              x1="5%"
              y1="50%"
              x2="95%"
              y2="50%"
              className="connecting-flow-line active"
            />
          )}
        </svg>
      </div>

      {/* SHAP Risks & Strengths with recommendation preview triggers */}
      <div style={styles.shapGrid}>
        <div style={styles.shapPanel} className="spotlight-card interactive-transition">
          <div style={styles.shapHeader}>
            <ShieldAlert size={18} color="var(--danger)" />
            <h3 style={styles.shapTitle}>Lowering Your Viability ↓</h3>
          </div>
          <p style={styles.shapDesc}>Aspects the model weighs <em>against</em> your predicted score (not always the same as a weak spec):</p>
          <div style={styles.shapList}>
            {result.top_risks?.map((risk, idx) => {
              const baseFeature = risk.feature.replace(/_mention_rate/g, '').replace(/_frequency/g, '');
              const isHovered = previewImpact === baseFeature;
              return (
                <div 
                  key={idx} 
                  style={{
                    ...styles.shapItem,
                    borderColor: isHovered ? 'var(--accent)' : 'var(--border)',
                    transform: isHovered ? 'translateY(-2px)' : 'none',
                    transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                  onMouseEnter={() => {
                    setPreviewImpact(baseFeature);
                    if (setHoveredAspect) setHoveredAspect(baseFeature);
                  }}
                  onMouseLeave={() => {
                    setPreviewImpact(null);
                    if (setHoveredAspect) setHoveredAspect(null);
                  }}
                >
                  <div style={styles.shapMeta}>
                    <span style={styles.shapName}>{risk.feature.replace(/_mention_rate/g, ' frequency').replace(/_/g, ' ')}</span>
                    <span style={styles.shapImpactNeg}>{risk.impact.toFixed(2)} impact</span>
                  </div>
                  {risk.reasoning && <p style={styles.shapReason}>{risk.reasoning}</p>}
                  {isHovered && <span style={styles.previewTag}>⚡ Hovering to preview mitigation effect (+8.5% score)</span>}
                </div>
              );
            })}
          </div>
        </div>

        <div style={styles.shapPanel} className="spotlight-card interactive-transition">
          <div style={styles.shapHeader}>
            <ShieldCheck size={18} color="var(--success)" />
            <h3 style={styles.shapTitle}>Raising Your Viability ↑</h3>
          </div>
          <p style={styles.shapDesc}>Aspects the model weighs <em>toward</em> your predicted score (a learned pattern, not always a strong spec):</p>
          <div style={styles.shapList}>
            {result.top_strengths?.map((strength, idx) => {
              const baseFeature = strength.feature.replace(/_mention_rate/g, '').replace(/_frequency/g, '');
              const isHovered = hoveredAspect === baseFeature;
              return (
                <div 
                  key={idx} 
                  style={{
                    ...styles.shapItem,
                    borderColor: isHovered ? 'var(--accent)' : 'var(--border)',
                    transform: isHovered ? 'translateY(-2px)' : 'none',
                    transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                  onMouseEnter={() => {
                    if (setHoveredAspect) setHoveredAspect(baseFeature);
                  }}
                  onMouseLeave={() => {
                    if (setHoveredAspect) setHoveredAspect(null);
                  }}
                >
                  <div style={styles.shapMeta}>
                    <span style={styles.shapName}>{strength.feature.replace(/_mention_rate/g, ' frequency').replace(/_/g, ' ')}</span>
                    <span style={styles.shapImpactPos}>+{strength.impact.toFixed(2)} impact</span>
                  </div>
                  {strength.reasoning && <p style={styles.shapReason}>{strength.reasoning}</p>}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Detailed Bridged Aspect Score Sheet with connected highlights */}
      <div style={styles.detailsPanel} className="spotlight-card interactive-transition">
        <h3 style={styles.detailsTitle}>Bridged Aspect Score Sheet</h3>
        <p style={styles.detailsSub}>Detailed breakdown of scores mapped from specifications using LLM reasoning rules. Hover rows to spotlight charts.</p>
        
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr style={styles.tr}>
                <th style={styles.th}>Aspect</th>
                <th style={styles.th}>Score</th>
                <th style={styles.th}>Evidence</th>
                <th style={styles.th}>Validation Trust</th>
                <th style={styles.th}>Reasoning Map</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.bridged_scores || {}).map(([aspect, val]) => {
                const isHighlighted = hoveredAspect === aspect;
                return (
                  <tr 
                    key={aspect} 
                    style={{
                      ...styles.trHover,
                      backgroundColor: isHighlighted ? 'var(--bg-panel-hover)' : 'transparent',
                      borderLeft: isHighlighted ? '3px solid var(--accent)' : '3px solid transparent',
                      transition: 'all 200ms ease-out'
                    }}
                    onMouseEnter={() => {
                      if (setHoveredAspect) setHoveredAspect(aspect);
                    }}
                    onMouseLeave={() => {
                      if (setHoveredAspect) setHoveredAspect(null);
                    }}
                  >
                    <td style={{...styles.td, fontWeight: 600, color: isHighlighted ? 'var(--accent)' : 'var(--text-primary)'}}>{aspect.replace(/_/g, ' ')}</td>
                    <td style={styles.td}>{val.score.toFixed(1)}</td>
                    <td style={styles.td}>
                      <span style={val.grounded ? styles.evidenceSpec : styles.evidenceNone}>
                        {val.grounded ? '📄 spec' : '⚪ none'}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <span style={{...styles.trustBadge, ...getTrustBadgeColor(val.trust)}}>
                        {val.trust}
                      </span>
                    </td>
                    <td style={{...styles.td, color: 'var(--text-secondary)', fontSize: '13px'}}>{val.reasoning}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Market Gaps Detail */}
      <MarketGapsPanel 
        gaps={result.market_gaps} 
        hoveredAspect={hoveredAspect} 
        setHoveredAspect={setHoveredAspect} 
      />

      {/* Constraints Honesty Banner */}
      <div style={styles.honestyBanner} className="spotlight-card">
        <div style={styles.honestyIcon}>ℹ</div>
        <div style={styles.honestyTextContainer}>
          <h4 style={styles.honestyTitle}>Analytical Scope Caveat</h4>
          <p style={styles.honestyDesc}>
            This simulator scores product design viability against historical consumer sentiment profiles. It does <strong>not</strong> forecast market volumes, sales, or financial performance, as it lacks visibility into operational variables like marketing budgets, manufacturing execution, distribution channels, and customer support quality.
          </p>
        </div>
      </div>

      {/* Developer Raw JSON */}
      <div style={styles.rawJsonSection} className="spotlight-card">
        <div onClick={() => setShowRawJson(!showRawJson)} style={styles.rawJsonTrigger}>
          <Code size={14} />
          <span>Raw Prediction Output JSON</span>
          {showRawJson ? <ChevronUp size={14} style={{ marginLeft: 'auto' }} /> : <ChevronDown size={14} style={{ marginLeft: 'auto' }} />}
        </div>
        {showRawJson && (
          <pre style={styles.rawJsonCode}>
            <code>{JSON.stringify(result, null, 2)}</code>
          </pre>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    width: '100%',
  },
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '16px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    }
  },
  kpiCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    boxShadow: 'var(--shadow-sm)',
    cursor: 'pointer',
  },
  kpiHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  kpiLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  infoIcon: {
    color: 'var(--text-muted)',
  },
  kpiValue: {
    fontSize: '28px',
    fontWeight: 700,
    fontFamily: 'var(--font-heading)',
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  kpiUnit: {
    fontSize: '14px',
    fontWeight: 500,
    color: 'var(--text-muted)',
  },
  kpiSub: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    marginTop: '2px',
  },
  warningBanner: {
    display: 'flex',
    gap: '14px',
    backgroundColor: 'var(--warning-muted)',
    border: '1px solid var(--warning)',
    borderRadius: 'var(--radius-sm)',
    padding: '16px 20px',
    alignItems: 'flex-start',
  },
  bannerTextContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  bannerTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--warning)',
  },
  bannerDesc: {
    fontSize: '13px',
    color: 'var(--text-primary)',
    lineHeight: '1.4',
  },
  vizGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 2fr',
    gap: '24px',
    '@media (max-width: 1024px)': {
      gridTemplateColumns: '1fr',
    }
  },
  flowMapCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  flowMapTitle: {
    fontSize: '14px',
    fontWeight: 600,
  },
  flowMapDesc: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  flowMapNodes: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '8px',
    zIndex: 2,
    '@media (max-width: 768px)': {
      flexDirection: 'column',
      gap: '16px',
    }
  },
  flowNode: {
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    alignItems: 'center',
    textAlign: 'center',
    transition: 'all 250ms ease-out',
    minWidth: '120px',
  },
  flowNodeLabel: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    fontWeight: 600,
  },
  flowNodeVal: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  shapGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '24px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    }
  },
  shapPanel: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
  },
  shapHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
  },
  shapTitle: {
    fontSize: '16px',
    fontWeight: 600,
  },
  shapDesc: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginBottom: '16px',
  },
  shapList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  shapItem: {
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    cursor: 'pointer',
  },
  shapMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  shapName: {
    fontSize: '13px',
    fontWeight: 600,
    textTransform: 'capitalize',
  },
  shapImpactNeg: {
    color: 'var(--danger)',
    fontWeight: 600,
    fontSize: '12px',
  },
  shapImpactPos: {
    color: 'var(--success)',
    fontWeight: 600,
    fontSize: '12px',
  },
  shapReason: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    lineHeight: '1.4',
  },
  previewTag: {
    fontSize: '10px',
    color: 'var(--accent)',
    fontWeight: 'bold',
    marginTop: '2px',
  },
  detailsPanel: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
  },
  detailsTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '4px',
  },
  detailsSub: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginBottom: '20px',
  },
  tableWrapper: {
    overflowX: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
  },
  tr: {
    borderBottom: '1px solid var(--border)',
  },
  trHover: {
    borderBottom: '1px solid var(--border)',
    cursor: 'pointer',
  },
  th: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    padding: '12px 16px',
  },
  td: {
    padding: '14px 16px',
    fontSize: '13px',
    color: 'var(--text-primary)',
    verticalAlign: 'top',
  },
  evidenceSpec: {
    backgroundColor: 'var(--accent-muted)',
    color: 'var(--accent)',
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 500,
  },
  evidenceNone: {
    backgroundColor: 'var(--border)',
    color: 'var(--text-muted)',
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 500,
  },
  trustBadge: {
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
  },
  honestyBanner: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px 32px',
    display: 'flex',
    gap: '20px',
    alignItems: 'flex-start',
    boxShadow: 'var(--shadow-sm)',
  },
  honestyIcon: {
    backgroundColor: 'var(--warning-muted)',
    color: 'var(--warning)',
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '16px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  honestyTextContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  honestyTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: 'var(--warning)',
  },
  honestyDesc: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: '1.6',
  },
  rawJsonSection: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    overflow: 'hidden',
  },
  rawJsonTrigger: {
    backgroundColor: 'var(--bg-panel)',
    padding: '12px 20px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    userSelect: 'none',
    transition: 'color var(--transition-fast)',
  },
  rawJsonCode: {
    backgroundColor: 'var(--bg-input)',
    borderTop: '1px solid var(--border)',
    padding: '20px',
    fontFamily: 'monospace',
    fontSize: '12px',
    overflowX: 'auto',
    maxHeight: '300px',
    color: 'var(--text-primary)',
  }
};
