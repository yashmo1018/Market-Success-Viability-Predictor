import React, { useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, MessageSquare } from 'lucide-react';

export default function MarketGapsPanel({ gaps, hoveredAspect, setHoveredAspect }) {
  const [expandedGap, setExpandedGap] = useState(null);

  if (!gaps || gaps.length === 0) {
    return (
      <div style={styles.successState} className="spotlight-card interactive-transition">
        <div style={styles.successIcon}>✓</div>
        <div style={styles.successMeta}>
          <h4 style={styles.successTitle}>No Market Gaps Detected</h4>
          <p style={styles.successDesc}>Your product design beats or aligns well with category averages on all major consumer pain points!</p>
        </div>
      </div>
    );
  }

  const toggleGap = (index) => {
    if (expandedGap === index) {
      setExpandedGap(null);
    } else {
      setExpandedGap(index);
    }
  };

  return (
    <div style={styles.container} className="animate-fade-in spotlight-card interactive-transition">
      <div style={styles.header}>
        <AlertCircle size={20} color="var(--warning)" />
        <h3 style={styles.title}>Market Gaps Identified</h3>
      </div>
      <p style={styles.subtitle}>Aspects where your spec does not outperform the category averages. Hover a card to spotlight matching charts.</p>

      <div style={styles.gapsList}>
        {gaps.map((gap, idx) => {
          const isExpanded = expandedGap === idx;
          const isHighlighted = hoveredAspect === gap.aspect;
          
          return (
            <div 
              key={idx} 
              style={{
                ...styles.gapCard,
                borderColor: isHighlighted ? 'var(--accent)' : 'var(--border)',
                backgroundColor: isHighlighted ? 'var(--bg-panel-hover)' : 'var(--bg-input)',
                transform: isHighlighted ? 'translateY(-1px)' : 'none',
              }}
              onMouseEnter={() => {
                if (setHoveredAspect) setHoveredAspect(gap.aspect);
              }}
              onMouseLeave={() => {
                if (setHoveredAspect) setHoveredAspect(null);
              }}
            >
              <div onClick={() => toggleGap(idx)} style={styles.gapTrigger}>
                <div style={styles.gapMainInfo}>
                  <span style={{
                    ...styles.gapName,
                    color: isHighlighted ? 'var(--accent)' : 'var(--text-primary)'
                  }}>{gap.aspect.replace(/_/g, ' ')}</span>
                  <div style={styles.gapScores}>
                    <span style={styles.yourScore}>Your design: <strong>{gap.your_estimate.toFixed(1)}</strong></span>
                    <span style={styles.divider}>|</span>
                    <span style={styles.avgScore}>Category avg: <strong>{gap.category_avg.toFixed(1)}</strong></span>
                  </div>
                </div>
                <button style={styles.expandBtn}>
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              </div>

              {/* Accordion container with height and opacity transition */}
              <div style={{
                maxHeight: isExpanded ? '350px' : '0px',
                opacity: isExpanded ? 1 : 0,
                overflow: 'hidden',
                transition: 'all 300ms cubic-bezier(0.16, 1, 0.3, 1)',
                backgroundColor: 'var(--bg-panel)',
                borderTop: isExpanded ? '1px solid var(--border)' : '1px solid transparent',
              }}>
                <div style={styles.gapDetails}>
                  <div style={styles.complaintsHeader}>
                    <MessageSquare size={14} style={{ marginTop: '2px' }} />
                    <span>Real consumer complaints in this category:</span>
                  </div>
                  <div style={styles.complaintsList}>
                    {gap.sample_complaints?.map((complaint, cIdx) => (
                      <blockquote key={cIdx} style={styles.complaintQuote}>
                        "{complaint}"
                      </blockquote>
                    ))}
                  </div>
                  <p style={styles.tipText}>
                    💡 *Action item: Refine your product description to explicitly address these pain points. Solving these details could unlock top-quartile viability.*
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles = {
  container: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: 'var(--shadow-md)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  title: {
    fontSize: '18px',
    fontWeight: 600,
  },
  subtitle: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    lineHeight: '1.5',
  },
  gapsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginTop: '8px',
  },
  gapCard: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    backgroundColor: 'var(--bg-input)',
    overflow: 'hidden',
    transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
  },
  gapTrigger: {
    padding: '16px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
    userSelect: 'none',
  },
  gapMainInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  gapName: {
    fontSize: '14px',
    fontWeight: 600,
    textTransform: 'capitalize',
    transition: 'color 200ms',
  },
  gapScores: {
    display: 'flex',
    gap: '10px',
    fontSize: '12px',
    alignItems: 'center',
  },
  yourScore: {
    color: 'var(--danger)',
  },
  avgScore: {
    color: 'var(--text-muted)',
  },
  divider: {
    color: 'var(--border)',
  },
  expandBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    padding: 0,
  },
  gapDetails: {
    padding: '20px',
  },
  complaintsHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    margin: '0 0 12px 0',
  },
  complaintsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  complaintQuote: {
    fontSize: '13px',
    fontStyle: 'italic',
    color: 'var(--text-primary)',
    paddingLeft: '12px',
    borderLeft: '2px solid var(--border-focus)',
    lineHeight: '1.5',
  },
  tipText: {
    fontSize: '12px',
    color: 'var(--accent)',
    marginTop: '16px',
    lineHeight: '1.5',
  },
  successState: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px 32px',
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    boxShadow: 'var(--shadow-sm)',
  },
  successIcon: {
    backgroundColor: 'var(--success-muted)',
    color: 'var(--success)',
    width: '36px',
    height: '36px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  successMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  successTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  successDesc: {
    fontSize: '13px',
    color: 'var(--text-muted)',
  }
};
