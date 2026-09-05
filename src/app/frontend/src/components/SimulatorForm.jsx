import React, { useEffect, useState } from 'react';
import { HelpCircle, Sparkles, TrendingUp } from 'lucide-react';

export default function SimulatorForm({
  categories,
  categoryProfiles,
  selectedCategory,
  setSelectedCategory,
  productType,
  setProductType,
  name,
  setName,
  price,
  setPrice,
  description,
  setDescription,
  onCoach,
  onPredict,
  isLoadingCoach,
  isLoadingPredict,
  hoveredAspect,
  setHoveredAspect,
  previewImpact,
  setPreviewImpact
}) {
  const [showCategoryTips, setShowCategoryTips] = useState(true);

  // Sync category lists and type
  const availableCategories = productType === 'physical' ? categories.physical : categories.app;

  useEffect(() => {
    if (availableCategories && availableCategories.length > 0) {
      if (!availableCategories.includes(selectedCategory)) {
        setSelectedCategory(availableCategories[0]);
      }
    }
  }, [productType, availableCategories, selectedCategory, setSelectedCategory]);

  // Adjust default price based on type
  const handleTypeChange = (type) => {
    setProductType(type);
    if (type === 'app') {
      setPrice(0.00);
    } else {
      setPrice(49.99);
    }
  };

  const selectedProfile = categoryProfiles[selectedCategory] || {};
  const medianPrice = selectedProfile?.price?.median || '...';
  const painPoints = selectedProfile?.pain_points?.aspects || [];
  
  // Aspect descriptions (from system prompt metadata)
  const physicalAspects = {
    value_for_money: "Is the product worth its price?",
    utility: "Core function performance (e.g. sound quality)",
    ease_of_use: "Setup, controls, comfort",
    reliability: "Consistent performance, no drops",
    design_appeal: "Aesthetics, look and feel",
    after_sales: "Customer service, warranty",
    build_quality: "Materials, solidity, fit & finish",
    durability: "Longevity, wear/breakage resistance",
    repairability: "Ease of repair, spare parts"
  };

  const appAspects = {
    value_for_money: "Worth its price / fair IAPs/subs",
    utility: "Core purpose accomplishment",
    ease_of_use: "UI clarity, navigation curve",
    reliability: "Works consistently, uptime, sync",
    design_appeal: "Visual design, UI aesthetics",
    after_sales: "Developer support responsiveness",
    performance: "Speed, smoothness, memory efficiency",
    stability: "Crash-free, bug-free operations",
    ad_experience: "Intrusiveness (higher = less intrusive)",
    update_support: "Active fixes, updates",
    privacy_trust: "Permissions, data trust"
  };

  const aspectDescriptions = productType === 'physical' ? physicalAspects : appAspects;

  return (
    <div style={styles.container}>
      <div style={styles.formSection}>
        <div style={styles.header}>
          <h2 style={styles.title}>Simulate Product Launch</h2>
          <p style={styles.subtitle}>Enter specs below to predict market reception.</p>
        </div>

        {/* Product Type selector removed: the system is physical-only
            (apps scoped out). productType stays 'physical' by default. */}

        <div style={styles.row}>
          <div style={{ ...styles.inputGroup, flex: 2 }}>
            <label style={styles.label}>Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={styles.select}
            >
              {availableCategories?.map(cat => (
                <option key={cat} value={cat}>
                  {cat.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          <div style={{ ...styles.inputGroup, flex: 1 }}>
            <label style={styles.label}>Price (USD)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
              style={styles.input}
            />
          </div>
        </div>

        <div style={styles.inputGroup}>
          <label style={styles.label}>Product Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={styles.input}
            placeholder="e.g. SoundWave Pro Max"
          />
        </div>

        <div style={styles.inputGroup}>
          <div style={styles.labelRow}>
            <label style={styles.label}>Product Specifications & Description</label>
            <span style={styles.charCount}>{description.length} chars</span>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={styles.textarea}
            placeholder={
              productType === 'physical'
                ? "Describe build materials, unique hardware features, battery life, design philosophy, warranty details, and what makes it stand out..."
                : "Describe user experience, onboarding, active syncing, performance metrics, subscription structures, privacy assurances, and update frequency..."
            }
          />
        </div>

        <div style={styles.btnRow}>
          <button
            type="button"
            onClick={onCoach}
            disabled={isLoadingCoach || isLoadingPredict || !description.trim()}
            style={styles.coachBtn}
          >
            <Sparkles size={16} />
            {isLoadingCoach ? 'Reviewing spec...' : 'Review my spec'}
          </button>
          
          <button
            type="button"
            onClick={onPredict}
            disabled={isLoadingCoach || isLoadingPredict || !description.trim()}
            style={styles.predictBtn}
          >
            <TrendingUp size={16} />
            {isLoadingPredict ? 'Predicting...' : 'Predict success'}
          </button>
        </div>
      </div>

      {showCategoryTips && selectedCategory && (
        <div style={styles.tipsSection}>
          <div style={styles.tipsHeader}>
            <span style={styles.tipsTitle}>Category Intelligence: {selectedCategory.replace(/_/g, ' ')}</span>
            <button style={styles.hideTipsBtn} onClick={() => setShowCategoryTips(false)}>Hide</button>
          </div>
          <div style={styles.tipsBody}>
            <div style={styles.tipMetric}>
              <span style={styles.tipMetricLabel}>Category Median Price:</span>
              <span style={styles.tipMetricValue}>${medianPrice}</span>
            </div>
            
            <div style={styles.tipAspectsList}>
              <span style={styles.tipSectionLabel}>Scored Aspects Checklist:</span>
              <div style={styles.aspectsGrid}>
                 {Object.entries(aspectDescriptions).map(([key, val]) => {
                  const isPain = painPoints.includes(key);
                  const isHovered = hoveredAspect === key;
                  return (
                    <div
                      key={key}
                      onMouseEnter={() => setHoveredAspect(key)}
                      onMouseLeave={() => setHoveredAspect(null)}
                      style={{
                        ...styles.aspectItem,
                        borderColor: isHovered ? 'var(--accent)' : (isPain ? 'var(--danger)' : 'var(--border)'),
                        backgroundColor: isHovered ? 'var(--accent-muted)' : (isPain ? 'var(--danger-muted)' : 'transparent'),
                        transform: isHovered ? 'scale(1.02)' : 'none',
                        boxShadow: isHovered ? 'var(--shadow-md)' : 'none',
                        cursor: 'pointer',
                        transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                      }}
                    >
                      <div style={styles.aspectItemHeader}>
                        <span style={{
                          ...styles.aspectItemName,
                          color: isHovered ? 'var(--accent)' : (isPain ? 'var(--danger)' : 'var(--text-primary)')
                        }}>
                          {key.replace(/_/g, ' ')}
                        </span>
                        {isPain && !isHovered && <span style={styles.painBadge}>⚠️ Critical Pain Point</span>}
                        {isPain && isHovered && <span style={{ ...styles.painBadge, color: 'var(--accent)' }}>⚠️ Critical Pain Point</span>}
                      </div>
                      <span style={styles.aspectItemDesc}>{val}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    height: '100%',
  },
  formSection: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    boxShadow: 'var(--shadow-md)',
  },
  header: {
    marginBottom: '8px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 600,
    letterSpacing: '-0.02em',
  },
  subtitle: {
    color: 'var(--text-muted)',
    fontSize: '13px',
    marginTop: '4px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  row: {
    display: 'flex',
    gap: '16px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
  },
  labelRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  charCount: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  typeSelector: {
    display: 'flex',
    gap: '12px',
  },
  typeBtn: {
    flex: 1,
    padding: '12px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
    background: 'none',
    fontSize: '14px',
    fontWeight: 500,
    transition: 'all var(--transition-fast)',
  },
  select: {
    height: '42px',
    cursor: 'pointer',
  },
  input: {
    height: '42px',
  },
  textarea: {
    height: '180px',
    resize: 'none',
    lineHeight: '1.6',
  },
  btnRow: {
    display: 'flex',
    gap: '16px',
    marginTop: '8px',
  },
  coachBtn: {
    flex: 1,
    height: '46px',
    backgroundColor: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-primary)',
    fontWeight: 600,
    '&:hover': {
      backgroundColor: 'var(--bg-panel-hover)',
    }
  },
  predictBtn: {
    flex: 1,
    height: '46px',
    backgroundColor: 'var(--accent)',
    color: 'var(--bg-app)',
    fontWeight: 600,
    '&:hover': {
      backgroundColor: 'var(--accent-hover)',
    }
  },
  tipsSection: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '24px',
    boxShadow: 'var(--shadow-sm)',
  },
  tipsHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '12px',
    marginBottom: '16px',
  },
  tipsTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  hideTipsBtn: {
    background: 'none',
    color: 'var(--text-muted)',
    fontSize: '12px',
    padding: 0,
    border: 'none',
  },
  tipsBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  tipMetric: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '13px',
  },
  tipMetricLabel: {
    color: 'var(--text-secondary)',
  },
  tipMetricValue: {
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  tipAspectsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  tipSectionLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  aspectsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '10px',
  },
  aspectItem: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '10px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  aspectItemHeader: {
    display: 'flex',
    flexDirection: 'column',
  },
  aspectItemName: {
    fontSize: '12px',
    fontWeight: 600,
  },
  painBadge: {
    fontSize: '9px',
    fontWeight: 600,
    color: 'var(--danger)',
    marginTop: '2px',
  },
  aspectItemDesc: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    lineHeight: '1.4',
  }
};
