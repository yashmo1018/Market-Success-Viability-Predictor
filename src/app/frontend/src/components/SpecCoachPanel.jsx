import React, { useState } from 'react';
import { Copy, Check, Info, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';

export default function SpecCoachPanel({ coachResult, onApplyImprovedSpec }) {
  const [copied, setCopied] = useState(false);

  if (!coachResult) {
    return (
      <div style={styles.emptyState}>
        <Info size={32} color="var(--text-muted)" />
        <p style={styles.emptyText}>Run "Review my spec" to analyze your draft and see recommendations here.</p>
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(coachResult.improved_spec);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getCoverageIcon = (status) => {
    switch (status) {
      case 'covered':
        return <CheckCircle size={14} color="var(--success)" />;
      case 'vague':
        return <AlertTriangle size={14} color="var(--warning)" />;
      case 'missing':
        return <AlertCircle size={14} color="var(--danger)" />;
      default:
        return null;
    }
  };

  const getCoverageBadgeStyle = (status) => {
    switch (status) {
      case 'covered':
        return { backgroundColor: 'var(--success-muted)', color: 'var(--success)', border: '1px solid var(--success)' };
      case 'vague':
        return { backgroundColor: 'var(--warning-muted)', color: 'var(--warning)', border: '1px solid var(--warning)' };
      case 'missing':
        return { backgroundColor: 'var(--danger-muted)', color: 'var(--danger)', border: '1px solid var(--danger)' };
      default:
        return {};
    }
  };

  return (
    <div style={styles.container} className="animate-fade-in">
      <div style={styles.panelHeader}>
        <h3 style={styles.panelTitle}>Specification Critique</h3>
        <span style={styles.panelBadge}>AI Coach Analysis</span>
      </div>

      {coachResult.summary && (
        <div style={styles.summaryBox}>
          <h4 style={styles.sectionTitle}>Summary</h4>
          <p style={styles.summaryText}>{coachResult.summary}</p>
        </div>
      )}

      <div style={styles.coverageSection}>
        <h4 style={styles.sectionTitle}>Aspect Coverage</h4>
        <div style={styles.coverageGrid}>
          {Object.entries(coachResult.coverage || {}).map(([aspect, status]) => (
            <div key={aspect} style={{ ...styles.aspectCard, ...getCoverageBadgeStyle(status) }}>
              <div style={styles.aspectCardHeader}>
                {getCoverageIcon(status)}
                <span style={styles.aspectName}>{aspect.replace(/_/g, ' ')}</span>
              </div>
              <span style={styles.aspectStatusText}>{status}</span>
            </div>
          ))}
        </div>
      </div>

      {coachResult.questions && coachResult.questions.length > 0 && (
        <div style={styles.questionsSection}>
          <h4 style={styles.sectionTitle}>Questions to Sharpen Your Prediction</h4>
          <ul style={styles.questionsList}>
            {coachResult.questions.map((q, idx) => (
              <li key={idx} style={styles.questionItem}>
                <div style={styles.questionIndex}>{idx + 1}</div>
                <span style={styles.questionText}>{q}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {coachResult.improved_spec && (
        <div style={styles.improvedSection}>
          <div style={styles.improvedHeader}>
            <h4 style={styles.sectionTitle}>Improved Spec Blueprint</h4>
            <div style={styles.codeActions}>
              <button onClick={handleCopy} style={styles.actionBtn}>
                {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button onClick={() => onApplyImprovedSpec(coachResult.improved_spec)} style={styles.applyBtn}>
                Apply to Draft
              </button>
            </div>
          </div>
          <p style={styles.improvedSub}>Copy and fill in the missing <code>[ADD: ...]</code> placeholders.</p>
          <pre style={styles.codeBlock}>
            <code>{coachResult.improved_spec}</code>
          </pre>
        </div>
      )}
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
    gap: '24px',
    boxShadow: 'var(--shadow-md)',
  },
  panelHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '16px',
  },
  panelTitle: {
    fontSize: '18px',
    fontWeight: 600,
  },
  panelBadge: {
    fontSize: '11px',
    fontWeight: 600,
    backgroundColor: 'var(--accent-muted)',
    color: 'var(--accent)',
    padding: '4px 8px',
    borderRadius: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  emptyState: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '64px 32px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    textAlign: 'center',
    minHeight: '400px',
  },
  emptyText: {
    color: 'var(--text-secondary)',
    fontSize: '14px',
    maxWidth: '320px',
  },
  sectionTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '12px',
  },
  summaryBox: {
    backgroundColor: 'var(--bg-input)',
    padding: '16px',
    borderRadius: 'var(--radius-sm)',
    borderLeft: '3px solid var(--accent)',
  },
  summaryText: {
    fontSize: '14px',
    color: 'var(--text-primary)',
    lineHeight: '1.6',
  },
  coverageSection: {
    display: 'flex',
    flexDirection: 'column',
  },
  coverageGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
    gap: '8px',
  },
  aspectCard: {
    padding: '10px',
    borderRadius: 'var(--radius-sm)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: '4px',
  },
  aspectCardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  aspectName: {
    fontSize: '12px',
    fontWeight: 600,
  },
  aspectStatusText: {
    fontSize: '10px',
    opacity: 0.8,
    textTransform: 'capitalize',
    paddingLeft: '20px',
  },
  questionsSection: {
    display: 'flex',
    flexDirection: 'column',
  },
  questionsList: {
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  questionItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    backgroundColor: 'var(--bg-input)',
    padding: '12px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
  },
  questionIndex: {
    backgroundColor: 'var(--border)',
    color: 'var(--text-primary)',
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    fontWeight: 600,
    flexShrink: 0,
  },
  questionText: {
    fontSize: '13px',
    color: 'var(--text-primary)',
    lineHeight: '1.5',
  },
  improvedSection: {
    display: 'flex',
    flexDirection: 'column',
  },
  improvedHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '4px',
  },
  improvedSub: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginBottom: '12px',
  },
  codeActions: {
    display: 'flex',
    gap: '8px',
  },
  actionBtn: {
    background: 'none',
    border: '1px solid var(--border)',
    padding: '6px 12px',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-secondary)',
    fontSize: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    '&:hover': {
      backgroundColor: 'var(--bg-panel-hover)',
      color: 'var(--text-primary)',
    }
  },
  applyBtn: {
    backgroundColor: 'var(--accent)',
    color: 'var(--bg-app)',
    border: 'none',
    padding: '6px 12px',
    borderRadius: 'var(--radius-sm)',
    fontSize: '12px',
    fontWeight: 600,
    '&:hover': {
      backgroundColor: 'var(--accent-hover)',
    }
  },
  codeBlock: {
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '16px',
    overflowX: 'auto',
    fontFamily: 'Courier New, Courier, monospace',
    fontSize: '13px',
    color: 'var(--text-primary)',
    whiteSpace: 'pre-wrap',
    lineHeight: '1.6',
    maxHeight: '240px',
  }
};
