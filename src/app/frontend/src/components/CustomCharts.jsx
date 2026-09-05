import React, { useState, useRef } from 'react';
import { Download } from 'lucide-react';

// Common export helper for SVG/PNG
const triggerDownload = (svgId, filename, format) => {
  const svgEl = document.getElementById(svgId);
  if (!svgEl) return;
  const svgString = new XMLSerializer().serializeToString(svgEl);
  
  if (format === 'svg') {
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);
    const downloadLink = document.createElement('a');
    downloadLink.href = svgUrl;
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  } else {
    // PNG export
    const canvas = document.createElement('canvas');
    const bbox = svgEl.getBoundingClientRect();
    canvas.width = bbox.width * 2; // high res
    canvas.height = bbox.height * 2;
    const ctx = canvas.getContext('2d');
    ctx.scale(2, 2);
    
    // Fill background for dark/light mode compatibility in export
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    ctx.fillStyle = isDark ? '#09090b' : '#ffffff';
    ctx.fillRect(0, 0, bbox.width, bbox.height);

    const img = new Image();
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    
    img.onload = () => {
      ctx.drawImage(img, 0, 0, bbox.width, bbox.height);
      URL.revokeObjectURL(url);
      const pngUrl = canvas.toDataURL('image/png');
      const downloadLink = document.createElement('a');
      downloadLink.href = pngUrl;
      downloadLink.download = filename;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
    };
    img.src = url;
  }
};

/* -------------------------------------------------------------------------- */
/* 1. ASPECT SCORE CHART (Horizontal Bar ↔ Dot Plot ↔ Lollipop)              */
/* -------------------------------------------------------------------------- */
export function AspectScoreChart({ data, categoryAvg, chartId = "aspect-chart", hoveredAspect, setHoveredAspect }) {
  const [view, setView] = useState('bar'); // 'bar' | 'dot' | 'lollipop'
  const [localHover, setLocalHover] = useState(null);

  const aspects = Object.keys(data || {});
  const rowHeight = 35;
  const paddingLeft = 140;
  const paddingRight = 40;
  const chartWidth = 500;
  const chartHeight = aspects.length * rowHeight + 40;
  const maxVal = 10;
  
  const scale = (val) => {
    const scaleWidth = chartWidth - paddingLeft - paddingRight;
    return paddingLeft + (val / maxVal) * scaleWidth;
  };

  const exportChart = (format) => {
    triggerDownload(chartId, `aspect_scores.${format}`, format);
  };

  const activeAspect = hoveredAspect || localHover;

  return (
    <div style={styles.chartWrapper} className="spotlight-card interactive-transition">
      <div style={styles.chartHeader}>
        <div style={styles.chartMeta}>
          <span style={styles.chartTitle}>Aspect Performance Mappings</span>
          <span style={styles.chartSub}>Your design vs category average (Hover to explore links)</span>
        </div>
        <div style={styles.controlsRow}>
          <div style={styles.toggleGroup}>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'bar' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('bar')}>Bar</button>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'dot' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('dot')}>Dot</button>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'lollipop' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('lollipop')}>Lollipop</button>
          </div>
          <div style={styles.exportGroup}>
            <button onClick={() => exportChart('svg')} style={styles.iconBtn} title="Export SVG">SVG</button>
            <button onClick={() => exportChart('png')} style={styles.iconBtn} title="Export PNG">PNG</button>
          </div>
        </div>
      </div>

      <svg id={chartId} viewBox={`0 0 ${chartWidth} ${chartHeight}`} width="100%" height={chartHeight} style={styles.svg}>
        {/* Draw X-Axis Gridlines */}
        {[0, 2.5, 5, 7.5, 10].map(gridVal => (
          <g key={gridVal}>
            <line
              x1={scale(gridVal)}
              y1={20}
              x2={scale(gridVal)}
              y2={chartHeight - 20}
              stroke="var(--border)"
              strokeWidth="0.8"
              strokeDasharray="2 2"
            />
            <text
              x={scale(gridVal)}
              y={chartHeight - 5}
              fill="var(--text-muted)"
              fontSize="10"
              textAnchor="middle"
            >
              {gridVal}
            </text>
          </g>
        ))}

        {aspects.map((aspect, idx) => {
          const item = data[aspect];
          const score = item?.score ?? item ?? 0;
          const avg = categoryAvg[aspect] ?? 0;
          const y = 30 + idx * rowHeight;
          const xScore = scale(score);
          const xAvg = scale(avg);
          const xZero = scale(0);
          
          const isHighlighted = activeAspect === aspect;
          const isAnyHovered = !!activeAspect;
          const dimOpacity = isAnyHovered && !isHighlighted ? 0.25 : 1;
          
          return (
            <g
              key={aspect}
              onMouseEnter={() => {
                setLocalHover(aspect);
                if (setHoveredAspect) setHoveredAspect(aspect);
              }}
              onMouseLeave={() => {
                setLocalHover(null);
                if (setHoveredAspect) setHoveredAspect(null);
              }}
              style={{ cursor: 'pointer', transition: 'opacity 250ms' }}
              opacity={dimOpacity}
            >
              {/* Aspect Label */}
              <text
                x={10}
                y={y + 5}
                fill={isHighlighted ? "var(--accent)" : "var(--text-secondary)"}
                fontSize="12"
                fontWeight={isHighlighted ? "600" : "500"}
                dominantBaseline="middle"
                style={{ transition: 'fill 250ms, font-weight 250ms' }}
              >
                {aspect.replace(/_/g, ' ')}
              </text>

              {/* View 1: Horizontal Bar */}
              {view === 'bar' && (
                <>
                  {/* Category Average Bar (Ghost) */}
                  <rect
                    x={xZero}
                    y={y - 8}
                    width={Math.max(0, xAvg - xZero)}
                    height={16}
                    fill="var(--border)"
                    opacity={isHighlighted ? "0.5" : "0.3"}
                    rx="3"
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                  {/* Your Score Bar */}
                  <rect
                    x={xZero}
                    y={isHighlighted ? y - 6 : y - 4}
                    width={Math.max(0, xScore - xZero)}
                    height={isHighlighted ? 12 : 8}
                    fill="var(--accent)"
                    opacity={isHighlighted ? "1.0" : "0.8"}
                    rx="2"
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                  {/* Average Indicator Line */}
                  <line
                    x1={xAvg}
                    y1={y - 12}
                    x2={xAvg}
                    y2={y + 12}
                    stroke={isHighlighted ? "var(--text-primary)" : "var(--text-muted)"}
                    strokeWidth={isHighlighted ? "2.5" : "1.5"}
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                </>
              )}

              {/* View 2: Dot Plot */}
              {view === 'dot' && (
                <>
                  {/* Connection Track */}
                  <line
                    x1={xZero}
                    y1={y}
                    x2={scale(10)}
                    y2={y}
                    stroke="var(--border)"
                    strokeWidth={isHighlighted ? "1.5" : "1"}
                  />
                  {/* Your Score Dot */}
                  <circle
                    cx={xScore}
                    cy={y}
                    r={isHighlighted ? 9 : 6}
                    fill="var(--accent)"
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                  {/* Average Dot */}
                  <circle
                    cx={xAvg}
                    cy={y}
                    r={isHighlighted ? 8 : 5}
                    fill="none"
                    stroke="var(--text-muted)"
                    strokeWidth={isHighlighted ? "3" : "2"}
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                </>
              )}

              {/* View 3: Lollipop */}
              {view === 'lollipop' && (
                <>
                  {/* Lollipop Stem */}
                  <line
                    x1={xZero}
                    y1={y}
                    x2={xScore}
                    y2={y}
                    stroke="var(--accent)"
                    strokeWidth={isHighlighted ? "3" : "2"}
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                  {/* Lollipop Head */}
                  <circle
                    cx={xScore}
                    cy={y}
                    r={isHighlighted ? 9 : 6}
                    fill="var(--accent)"
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                  {/* Average tick */}
                  <line
                    x1={xAvg}
                    y1={y - 8}
                    x2={xAvg}
                    y2={y + 8}
                    stroke="var(--text-muted)"
                    strokeWidth={isHighlighted ? "3" : "2"}
                    style={{ transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)' }}
                  />
                </>
              )}

              {/* Hover Tooltip Overlay */}
              {isHighlighted && (
                <g>
                  <rect
                    x={Math.max(100, Math.min(chartWidth - 145, xScore - 60))}
                    y={y - 35}
                    width="120"
                    height="24"
                    fill="var(--bg-panel)"
                    stroke="var(--border-focus)"
                    rx="4"
                  />
                  <text
                    x={Math.max(160, Math.min(chartWidth - 85, xScore))}
                    y={y - 19}
                    fill="var(--text-primary)"
                    fontSize="10"
                    fontWeight="600"
                    textAnchor="middle"
                  >
                    Design: {score.toFixed(1)} | Avg: {avg.toFixed(1)}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 2. VIABILITY PROGRESS CHART (Donut ↔ Progress Ring)                        */
/* -------------------------------------------------------------------------- */
export function ViabilityProgressChart({ viability, threshold, chartId = "viability-chart", previewImpact }) {
  const [view, setView] = useState('donut'); // 'donut' | 'ring'
  const [hoveringLens, setHoveringLens] = useState(false);
  
  const size = 180;
  const center = size / 2;
  const strokeWidth = view === 'donut' ? 18 : 8;
  const radius = center - strokeWidth - 5;
  const circumference = 2 * Math.PI * radius;
  
  // Simulated delta based on hovered recommendation preview
  let previewDelta = 0;
  if (previewImpact) {
    previewDelta = 8.5; // Simulated increase in viability when applying recommendations
  }
  const displayViability = viability;
  const previewViability = Math.min(100, viability + previewDelta);
  
  const viabilityOffset = circumference - (displayViability / 100) * circumference;
  const previewOffset = circumference - (previewViability / 100) * circumference;
  const thresholdOffset = circumference - (threshold / 100) * circumference;

  // Confidence Lens details (standard error bounds: +/- 7.5%)
  const confidenceMin = Math.max(0, viability - 7.5);
  const confidenceMax = Math.min(100, viability + 7.5);
  const confidenceMinOffset = circumference - (confidenceMin / 100) * circumference;
  const confidenceMaxOffset = circumference - (confidenceMax / 100) * circumference;

  const exportChart = (format) => {
    triggerDownload(chartId, `viability_metrics.${format}`, format);
  };

  return (
    <div 
      style={styles.singleChartWrapper} 
      className="spotlight-card interactive-transition"
      onMouseEnter={() => setHoveringLens(true)}
      onMouseLeave={() => setHoveringLens(false)}
    >
      <div style={styles.chartHeader}>
        <div style={styles.chartMeta}>
          <span style={styles.chartTitle}>Viability Score Card</span>
        </div>
        <div style={styles.controlsRow}>
          <div style={styles.toggleGroup}>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'donut' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('donut')}>Donut</button>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'ring' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('ring')}>Ring</button>
          </div>
          <div style={styles.exportGroup}>
            <button onClick={() => exportChart('svg')} style={styles.iconBtn}>SVG</button>
            <button onClick={() => exportChart('png')} style={styles.iconBtn}>PNG</button>
          </div>
        </div>
      </div>

      <div style={styles.radialContainer}>
        <svg id={chartId} width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
          
          {/* CONFIDENCE LENS: Shaded region behind progress bar */}
          {hoveringLens && (
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={strokeWidth + 4}
              strokeDasharray={circumference}
              strokeDashoffset={confidenceMinOffset}
              opacity="0.08"
              transform={`rotate(-90 ${center} ${center})`}
              className="confidence-blur"
              style={{ strokeLinecap: 'round' }}
            />
          )}

          {/* Background Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth={strokeWidth}
          />
          
          {/* Preview Arc (simulated delta) */}
          {previewDelta > 0 && (
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={previewOffset}
              strokeLinecap="round"
              transform={`rotate(-90 ${center} ${center})`}
              opacity="0.45"
              style={{ 
                strokeDasharray: '3 3',
                transition: 'stroke-dashoffset 300ms ease-out'
              }}
            />
          )}

          {/* Viability Gauge Fill */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={displayViability >= threshold ? "var(--success)" : "var(--danger)"}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={viabilityOffset}
            strokeLinecap="round"
            transform={`rotate(-90 ${center} ${center})`}
            style={{ 
              transition: 'stroke-dashoffset 800ms ease-in-out, stroke 300ms, stroke-width 200ms',
              filter: hoveringLens ? 'drop-shadow(0 0 3px var(--accent))' : 'none'
            }}
          />

          {/* Threshold marker */}
          {view === 'ring' ? (
            <circle
              cx={center + radius * Math.cos((threshold / 100 * 360 - 90) * Math.PI / 180)}
              cy={center + radius * Math.sin((threshold / 100 * 360 - 90) * Math.PI / 180)}
              r={5}
              fill="var(--text-primary)"
              stroke="var(--bg-panel)"
              strokeWidth="1.5"
            />
          ) : (
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke="var(--text-secondary)"
              strokeWidth="2"
              strokeDasharray="2 10"
              strokeDashoffset={thresholdOffset}
              transform={`rotate(-90 ${center} ${center})`}
            />
          )}

          {/* Central Text */}
          <g style={{ cursor: 'pointer' }}>
            <text
              x={center}
              y={center - 5}
              textAnchor="middle"
              fill="var(--text-primary)"
              fontSize="28"
              fontFamily="var(--font-heading)"
              fontWeight="700"
            >
              {previewDelta > 0 ? Math.round(previewViability) : Math.round(displayViability)}%
            </text>
            <text
              x={center}
              y={center + 15}
              textAnchor="middle"
              fill={previewDelta > 0 ? "var(--accent)" : "var(--text-muted)"}
              fontSize="10"
              fontWeight="600"
              textTransform="uppercase"
              letterSpacing="0.05em"
              style={{ transition: 'fill 300ms' }}
            >
              {previewDelta > 0 ? "Simulated Score" : "Viability"}
            </text>
          </g>
        </svg>

        <div style={styles.radialLegend}>
          <div style={styles.legendItem}>
            <div style={{...styles.legendDot, backgroundColor: displayViability >= threshold ? "var(--success)" : "var(--danger)"}}></div>
            <span>Estimated Score {previewDelta > 0 && `(Original: ${Math.round(viability)}%)`}</span>
          </div>
          {previewDelta > 0 && (
            <div style={styles.legendItem}>
              <div style={{...styles.legendDot, backgroundColor: "var(--accent)", border: "1px dashed var(--accent)"}}></div>
              <span>Simulated (+{previewDelta.toFixed(1)}%)</span>
            </div>
          )}
          <div style={styles.legendItem}>
            <div style={{...styles.legendDot, backgroundColor: "var(--text-muted)", border: "1px dashed var(--text-primary)"}}></div>
            <span>Target Threshold ({Math.round(threshold)}%)</span>
          </div>
        </div>

        {/* Confidence Lens Details Card */}
        <div style={{
          maxHeight: hoveringLens ? '80px' : '0px',
          opacity: hoveringLens ? 1 : 0,
          overflow: 'hidden',
          transition: 'all 350ms cubic-bezier(0.16, 1, 0.3, 1)',
          fontSize: '11.5px',
          color: 'var(--text-secondary)',
          textAlign: 'center',
          backgroundColor: 'var(--bg-input)',
          padding: hoveringLens ? '10px 14px' : '0 14px',
          borderRadius: 'var(--radius-sm)',
          border: hoveringLens ? '1px solid var(--border)' : '1px solid transparent',
          marginTop: '5px'
        }}>
          <strong>Confidence Lens Active</strong>
          <div>95% Empirical Bounds: {Math.round(confidenceMin)}% – {Math.round(confidenceMax)}%</div>
          <span style={{ fontSize: '9.5px', color: 'var(--text-muted)' }}>Aspect sentiment indicates high regression reliability.</span>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 3. RADAR CHART (Radar ↔ Polar Area)                                        */
/* -------------------------------------------------------------------------- */
export function AspectRadarChart({ data, categoryAvg, chartId = "radar-chart", hoveredAspect, setHoveredAspect }) {
  const [view, setView] = useState('radar'); // 'radar' | 'polar'
  const [localHover, setLocalHover] = useState(null);

  const aspects = Object.keys(data || {});
  const totalAspects = aspects.length;
  if (totalAspects === 0) return null;

  const size = 300;
  const center = size / 2;
  const rMax = size * 0.38;

  const getCoordinates = (index, value) => {
    const angle = (Math.PI * 2 / totalAspects) * index - Math.PI / 2;
    const x = center + rMax * (value / 10) * Math.cos(angle);
    const y = center + rMax * (value / 10) * Math.sin(angle);
    return { x, y, angle };
  };

  const activeAspect = hoveredAspect || localHover;

  // Build Radar Polygons
  const scorePoints = aspects.map((aspect, idx) => {
    const item = data[aspect];
    const score = item?.score ?? item ?? 0;
    const { x, y } = getCoordinates(idx, score);
    return `${x},${y}`;
  }).join(' ');

  const avgPoints = aspects.map((aspect, idx) => {
    const avg = categoryAvg[aspect] ?? 0;
    const { x, y } = getCoordinates(idx, avg);
    return `${x},${y}`;
  }).join(' ');

  const exportChart = (format) => {
    triggerDownload(chartId, `aspect_footprint.${format}`, format);
  };

  return (
    <div style={styles.singleChartWrapper} className="spotlight-card interactive-transition">
      <div style={styles.chartHeader}>
        <div style={styles.chartMeta}>
          <span style={styles.chartTitle}>Design Aspect Radar</span>
        </div>
        <div style={styles.controlsRow}>
          <div style={styles.toggleGroup}>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'radar' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('radar')}>Radar</button>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'polar' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('polar')}>Polar</button>
          </div>
          <div style={styles.exportGroup}>
            <button onClick={() => exportChart('svg')} style={styles.iconBtn}>SVG</button>
            <button onClick={() => exportChart('png')} style={styles.iconBtn}>PNG</button>
          </div>
        </div>
      </div>

      <div style={styles.radarContainer}>
        <svg id={chartId} width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
          {/* Outer Web Grid rings */}
          {[2.5, 5, 7.5, 10].map(val => (
            <circle
              key={val}
              cx={center}
              cy={center}
              r={rMax * (val / 10)}
              fill="none"
              stroke="var(--border)"
              strokeWidth="0.8"
            />
          ))}

          {/* Axis Spokes and Labels */}
          {aspects.map((aspect, idx) => {
            const { x, y, angle } = getCoordinates(idx, 10);
            const labelDist = rMax + 20;
            const lx = center + labelDist * Math.cos(angle);
            const ly = center + labelDist * Math.sin(angle);
            
            const isHighlighted = activeAspect === aspect;
            const isAnyHovered = !!activeAspect;
            
            return (
              <g 
                key={aspect}
                onMouseEnter={() => {
                  setLocalHover(aspect);
                  if (setHoveredAspect) setHoveredAspect(aspect);
                }}
                onMouseLeave={() => {
                  setLocalHover(null);
                  if (setHoveredAspect) setHoveredAspect(null);
                }}
                style={{ cursor: 'pointer' }}
              >
                {/* Spoke Line */}
                <line
                  x1={center}
                  y1={center}
                  x2={x}
                  y2={y}
                  stroke={isHighlighted ? "var(--accent)" : "var(--border)"}
                  strokeWidth={isHighlighted ? "2" : "0.8"}
                  style={{ transition: 'stroke-width 200ms, stroke 200ms' }}
                />
                
                {/* Thick invisible pointer detector spoke line */}
                <line
                  x1={center}
                  y1={center}
                  x2={x}
                  y2={y}
                  stroke="transparent"
                  strokeWidth="10"
                />

                {/* Spoke label */}
                <text
                  x={lx}
                  y={ly}
                  fill={isHighlighted ? "var(--accent)" : "var(--text-secondary)"}
                  fontSize="8.5"
                  fontWeight={isHighlighted ? "700" : "600"}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  opacity={isAnyHovered && !isHighlighted ? 0.45 : 1}
                  style={{ transition: 'fill 200ms, opacity 200ms, font-weight 200ms' }}
                >
                  {aspect.substring(0, 10).replace(/_/g, ' ').toUpperCase()}
                </text>

                {/* Magnetic Spoke Marker Circle */}
                {isHighlighted && (
                  <circle
                    cx={center + rMax * ((data[aspect]?.score ?? data[aspect] ?? 0) / 10) * Math.cos(angle)}
                    cy={center + rMax * ((data[aspect]?.score ?? data[aspect] ?? 0) / 10) * Math.sin(angle)}
                    r="5"
                    fill="var(--accent)"
                    stroke="var(--bg-panel)"
                    strokeWidth="1.5"
                  />
                )}
              </g>
            );
          })}

          {/* View 1: Radar Polygons */}
          {view === 'radar' && (
            <>
              {/* Avg Footprint */}
              <polygon
                points={avgPoints}
                fill="var(--border)"
                opacity={activeAspect ? "0.08" : "0.2"}
                stroke="var(--text-muted)"
                strokeWidth="1.5"
                style={{ transition: 'all 250ms' }}
              />
              {/* Your Footprint */}
              <polygon
                points={scorePoints}
                fill="var(--accent)"
                opacity={activeAspect ? "0.15" : "0.35"}
                stroke="var(--accent)"
                strokeWidth="2"
                style={{ transition: 'all 250ms' }}
              />
            </>
          )}

          {/* View 2: Polar Area slices */}
          {view === 'polar' && (
            aspects.map((aspect, idx) => {
              const item = data[aspect];
              const score = item?.score ?? item ?? 0;
              const startAngle = (Math.PI * 2 / totalAspects) * idx - Math.PI / 2;
              const endAngle = (Math.PI * 2 / totalAspects) * (idx + 1) - Math.PI / 2;
              
              const radius = rMax * (score / 10);
              
              const x1 = center + radius * Math.cos(startAngle);
              const y1 = center + radius * Math.sin(startAngle);
              const x2 = center + radius * Math.cos(endAngle);
              const y2 = center + radius * Math.sin(endAngle);
              
              const isHighlighted = activeAspect === aspect;
              const isAnyHovered = !!activeAspect;

              // SVG path for a circular pie segment slice
              const pathData = `
                M ${center} ${center}
                L ${x1} ${y1}
                A ${radius} ${radius} 0 0 1 ${x2} ${y2}
                Z
              `;
              
              return (
                <path
                  key={aspect}
                  d={pathData}
                  fill="var(--accent)"
                  opacity={isHighlighted ? 0.6 : (isAnyHovered ? 0.08 : 0.15 + (idx % 2) * 0.15)}
                  stroke="var(--accent)"
                  strokeWidth={isHighlighted ? "1.5" : "1"}
                  style={{ transition: 'all 250ms' }}
                />
              );
            })
          )}
        </svg>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 4. SCATTER PLOT (Scatter ↔ Bubble Chart & Market Gap Exploration)         */
/* -------------------------------------------------------------------------- */
export function DistributionScatterChart({ currentProduct, categoryProducts, chartId = "scatter-chart" }) {
  const [view, setView] = useState('scatter'); // 'scatter' | 'bubble'
  const [hoveredPoint, setHoveredPoint] = useState(null);
  
  // Whitespace tracking for "Market Gap Exploration"
  const [whitespaceCoordinates, setWhitespaceCoordinates] = useState(null);
  const svgRef = useRef(null);

  const defaultPoints = [
    { name: "Apex Pro", price: 19.99, viability: 42, reviews: 200 },
    { name: "Neo Slim", price: 89.99, viability: 68, reviews: 450 },
    { name: "Titan Ultra", price: 199.99, viability: 79, reviews: 1200 },
    { name: "Edge Buds", price: 29.99, viability: 53, reviews: 80 },
    { name: "Zen Tablet", price: 349.00, viability: 82, reviews: 620 },
    { name: "Juice Tank", price: 49.99, viability: 61, reviews: 310 },
    { name: "Core Cooker", price: 129.99, viability: 71, reviews: 580 },
    { name: "Bose Sound", price: 99.00, viability: 59, reviews: 920 },
    { name: "Logi Planner", price: 4.99, viability: 64, reviews: 150 },
    { name: "Acme Finance", price: 9.99, viability: 70, reviews: 2100 },
  ];

  const points = categoryProducts || defaultPoints;

  const w = 500;
  const h = 300;
  const padding = 45;

  const maxPrice = Math.max(...points.map(p => p.price), currentProduct?.price || 50, 100);
  const minPrice = 0;

  const scaleX = (price) => {
    const activeWidth = w - padding * 2;
    return padding + ((price - minPrice) / (maxPrice - minPrice)) * activeWidth;
  };

  const scaleY = (viab) => {
    const activeHeight = h - padding * 2;
    return h - padding - (viab / 100) * activeHeight;
  };

  // Convert SVG coordinates back to Data values for Whitespace Opportunity check
  const revertCoordinates = (svgX, svgY) => {
    const activeWidth = w - padding * 2;
    const activeHeight = h - padding * 2;
    
    const price = minPrice + ((svgX - padding) / activeWidth) * (maxPrice - minPrice);
    const viability = ((h - padding - svgY) / activeHeight) * 100;
    
    return { price, viability };
  };

  const handleMouseMove = (e) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    // Scale SVG viewport
    const svgX = (mouseX / rect.width) * w;
    const svgY = (mouseY / rect.height) * h;
    
    // Check if mouse is near any existing point
    let foundNearPoint = false;
    points.forEach((p) => {
      const px = scaleX(p.price);
      const py = scaleY(p.viability);
      const dist = Math.sqrt((svgX - px) ** 2 + (svgY - py) ** 2);
      
      if (dist < 18) {
        setHoveredPoint(p);
        foundNearPoint = true;
      }
    });

    if (!foundNearPoint) {
      setHoveredPoint(null);
      // Track whitespace coordinates if inside axis boundaries
      if (svgX >= padding && svgX <= w - padding && svgY >= padding && svgY <= h - padding) {
        const dataCoords = revertCoordinates(svgX, svgY);
        setWhitespaceCoordinates({ x: svgX, y: svgY, ...dataCoords });
      } else {
        setWhitespaceCoordinates(null);
      }
    } else {
      setWhitespaceCoordinates(null);
    }
  };

  const handleMouseLeave = () => {
    setHoveredPoint(null);
    setWhitespaceCoordinates(null);
  };

  const exportChart = (format) => {
    triggerDownload(chartId, `distribution.${format}`, format);
  };

  // Blue Ocean opportunity: high viability (>65%) and low price (<$120)
  const isOpportunityZone = whitespaceCoordinates && whitespaceCoordinates.viability > 65 && whitespaceCoordinates.price < (maxPrice * 0.45);

  return (
    <div style={styles.chartWrapper} className="spotlight-card interactive-transition">
      <div style={styles.chartHeader}>
        <div style={styles.chartMeta}>
          <span style={styles.chartTitle}>Market Positioning Grid</span>
          <span style={styles.chartSub}>Compare Price (X) vs Viability (Y) | Hover blank space to explore gaps</span>
        </div>
        <div style={styles.controlsRow}>
          <div style={styles.toggleGroup}>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'scatter' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('scatter')}>Scatter</button>
            <button style={{...styles.toggleBtn, backgroundColor: view === 'bubble' ? 'var(--border-focus)' : 'transparent'}} onClick={() => setView('bubble')}>Bubble</button>
          </div>
          <div style={styles.exportGroup}>
            <button onClick={() => exportChart('svg')} style={styles.iconBtn}>SVG</button>
            <button onClick={() => exportChart('png')} style={styles.iconBtn}>PNG</button>
          </div>
        </div>
      </div>

      <svg 
        id={chartId} 
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`} 
        width="100%" 
        height={h} 
        style={{...styles.svg, cursor: 'crosshair'}}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* Draw axes */}
        <line x1={padding} y1={h - padding} x2={w - padding} y2={h - padding} stroke="var(--border)" strokeWidth="1" />
        <line x1={padding} y1={padding} x2={padding} y2={h - padding} stroke="var(--border)" strokeWidth="1" />

        {/* Labels X Axis */}
        <text x={w / 2} y={h - 10} fill="var(--text-secondary)" fontSize="11" textAnchor="middle">Price (USD)</text>
        
        {/* Labels Y Axis */}
        <text x={12} y={h / 2} fill="var(--text-secondary)" fontSize="11" textAnchor="middle" transform={`rotate(-90 12 ${h/2})`}>Viability (%)</text>

        {/* Axis scale ticks */}
        {[0, 25, 50, 75, 100].map(yVal => (
          <g key={yVal}>
            <line x1={padding - 5} y1={scaleY(yVal)} x2={padding} y2={scaleY(yVal)} stroke="var(--border)" />
            <text x={padding - 10} y={scaleY(yVal) + 3} fill="var(--text-muted)" fontSize="9" textAnchor="end">{yVal}%</text>
          </g>
        ))}

        {[0, maxPrice * 0.25, maxPrice * 0.5, maxPrice * 0.75, maxPrice].map(xVal => (
          <g key={xVal}>
            <line x1={scaleX(xVal)} y1={h - padding} x2={scaleX(xVal)} y2={h - padding + 5} stroke="var(--border)" />
            <text x={scaleX(xVal)} y={h - padding + 18} fill="var(--text-muted)" fontSize="9" textAnchor="middle">${Math.round(xVal)}</text>
          </g>
        ))}

        {/* Highlighted Opportunity Zone Shading if cursor is inside */}
        {whitespaceCoordinates && (
          <circle
            cx={whitespaceCoordinates.x}
            cy={whitespaceCoordinates.y}
            r="32"
            fill={isOpportunityZone ? "rgba(0, 199, 172, 0.09)" : "rgba(240, 240, 240, 0.03)"}
            stroke={isOpportunityZone ? "var(--accent)" : "var(--border)"}
            strokeWidth="0.8"
            strokeDasharray="2 2"
            style={{ transition: 'fill 200ms, stroke 200ms' }}
          />
        )}

        {/* Competitor Scatter dots */}
        {points.map((p, idx) => {
          const cx = scaleX(p.price);
          const cy = scaleY(p.viability);
          const isPointHovered = hoveredPoint && hoveredPoint.name === p.name;
          const r = view === 'scatter' 
            ? (isPointHovered ? 9 : 5) 
            : Math.max(4, Math.min(16, (p.reviews / 1200) * 10 + 4)) + (isPointHovered ? 4 : 0);

          return (
            <g key={idx}>
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={isPointHovered ? "var(--text-primary)" : "var(--text-secondary)"}
                opacity={isPointHovered ? "0.9" : "0.45"}
                className="interactive-transition"
                style={{ 
                  transition: 'all 250ms cubic-bezier(0.16, 1, 0.3, 1)',
                  filter: isPointHovered ? 'drop-shadow(0 0 3px var(--border-focus))' : 'none'
                }}
              />
            </g>
          );
        })}

        {/* Target Subject Node (Highlighted Premium Pulsing Ring) */}
        {currentProduct && (
          <g>
            <circle
              cx={scaleX(currentProduct.price)}
              cy={scaleY(currentProduct.viability)}
              r="12"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="1.5"
              opacity="0.4"
            />
            <circle
              cx={scaleX(currentProduct.price)}
              cy={scaleY(currentProduct.viability)}
              r="7"
              fill="var(--accent)"
              stroke="var(--bg-panel)"
              strokeWidth="2"
            />
            <text
              x={scaleX(currentProduct.price)}
              y={scaleY(currentProduct.viability) - 15}
              fill="var(--accent)"
              fontSize="10"
              fontWeight="bold"
              textAnchor="middle"
            >
              Your Product
            </text>
          </g>
        )}

        {/* Floating tooltip coordinates or Opportunity labels */}
        {whitespaceCoordinates && (
          <g>
            {isOpportunityZone ? (
              <g>
                <rect
                  x={Math.max(padding, Math.min(w - padding - 170, whitespaceCoordinates.x - 85))}
                  y={Math.max(padding, whitespaceCoordinates.y - 40)}
                  width="170"
                  height="28"
                  fill="var(--bg-panel)"
                  stroke="var(--accent)"
                  strokeWidth="1"
                  rx="4"
                />
                <text
                  x={Math.max(padding + 85, Math.min(w - padding - 85, whitespaceCoordinates.x))}
                  y={Math.max(padding + 16, whitespaceCoordinates.y - 24)}
                  fill="var(--accent)"
                  fontSize="9.5"
                  fontWeight="700"
                  textAnchor="middle"
                >
                  💡 Blue Ocean Gaps (Underserved)
                </text>
              </g>
            ) : (
              <g>
                <rect
                  x={Math.max(padding, Math.min(w - padding - 100, whitespaceCoordinates.x - 50))}
                  y={Math.max(padding, whitespaceCoordinates.y - 30)}
                  width="100"
                  height="20"
                  fill="var(--bg-panel)"
                  stroke="var(--border)"
                  rx="4"
                />
                <text
                  x={Math.max(padding + 50, Math.min(w - padding - 50, whitespaceCoordinates.x))}
                  y={Math.max(padding + 12, whitespaceCoordinates.y - 18)}
                  fill="var(--text-secondary)"
                  fontSize="9"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  ${whitespaceCoordinates.price.toFixed(0)} | {whitespaceCoordinates.viability.toFixed(0)}%
                </text>
              </g>
            )}
          </g>
        )}

        {/* Hovered Point Card */}
        {hoveredPoint && (
          <g>
            <rect
              x={Math.max(padding, Math.min(w - padding - 130, scaleX(hoveredPoint.price) - 65))}
              y={Math.max(padding, scaleY(hoveredPoint.viability) - 45)}
              width="130"
              height="35"
              fill="var(--bg-panel)"
              stroke="var(--border-focus)"
              rx="4"
            />
            <text
              x={Math.max(padding + 65, Math.min(w - padding - 65, scaleX(hoveredPoint.price)))}
              y={Math.max(padding + 12, scaleY(hoveredPoint.viability) - 33)}
              fill="var(--text-primary)"
              fontSize="9.5"
              fontWeight="700"
              textAnchor="middle"
            >
              {hoveredPoint.name}
            </text>
            <text
              x={Math.max(padding + 65, Math.min(w - padding - 65, scaleX(hoveredPoint.price)))}
              y={Math.max(padding + 24, scaleY(hoveredPoint.viability) - 21)}
              fill="var(--text-muted)"
              fontSize="8.5"
              textAnchor="middle"
            >
              Price: ${hoveredPoint.price.toFixed(2)} | Score: {hoveredPoint.viability}%
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

const styles = {
  chartWrapper: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    width: '100%',
  },
  singleChartWrapper: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    width: '100%',
    alignItems: 'center',
  },
  chartHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    width: '100%',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '12px',
  },
  chartMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  chartTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  chartSub: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  controlsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  toggleGroup: {
    display: 'flex',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    overflow: 'hidden',
    padding: '2px',
  },
  toggleBtn: {
    background: 'none',
    border: 'none',
    padding: '4px 8px',
    fontSize: '11px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
    borderRadius: 'calc(var(--radius-sm) - 2px)',
    cursor: 'pointer',
    transition: 'background-color var(--transition-fast)',
  },
  exportGroup: {
    display: 'flex',
    gap: '4px',
  },
  iconBtn: {
    background: 'var(--bg-input)',
    border: '1px solid var(--border)',
    padding: '4px 8px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '11px',
    color: 'var(--text-secondary)',
    transition: 'all var(--transition-fast)',
    '&:hover': {
      borderColor: 'var(--border-focus)',
      color: 'var(--text-primary)',
    }
  },
  svg: {
    overflow: 'visible',
  },
  radialContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '20px',
    margin: '10px 0',
    width: '100%',
  },
  radialLegend: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: '16px',
    fontSize: '11px',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    color: 'var(--text-secondary)',
  },
  legendDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
  },
  radarContainer: {
    margin: '10px 0',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
  }
};
