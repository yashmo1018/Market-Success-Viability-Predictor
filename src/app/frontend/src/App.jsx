import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import SimulatorForm from './components/SimulatorForm';
import SpecCoachPanel from './components/SpecCoachPanel';
import PredictorResults from './components/PredictorResults';
import LoadingPanel from './components/LoadingPanel';
import { Cpu, AlertTriangle, AlertCircle, Info, Database } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('simulator');
  const [mockMode, setMockMode] = useState(false);
  const [theme, setTheme] = useState('dark');
  const [hoveredAspect, setHoveredAspect] = useState(null);
  const [previewImpact, setPreviewImpact] = useState(null);


  // Categories and profiles loaded from API
  const [categories, setCategories] = useState({ physical: [], app: [] });
  const [categoryProfiles, setCategoryProfiles] = useState({});
  const [analyzerReport, setAnalyzerReport] = useState(null);

  // Active form state
  const [selectedCategory, setSelectedCategory] = useState('');
  const [productType, setProductType] = useState('physical');
  const [productName, setProductName] = useState('My New Product');
  const [price, setPrice] = useState(49.99);
  const [description, setDescription] = useState('');

  // Execution states
  const [isLoadingCoach, setIsLoadingCoach] = useState(false);
  const [isLoadingPredict, setIsLoadingPredict] = useState(false);
  const [coachResult, setCoachResult] = useState(null);
  const [predictResult, setPredictResult] = useState(null);
  
  // Right-hand sub-tab on Simulator results panel
  const [simulatorRightTab, setSimulatorRightTab] = useState('critique'); // 'critique' | 'prediction'

  // Fetch categories on mount
  useEffect(() => {
    fetch('/api/categories')
      .then(res => {
        if (!res.ok) throw new Error("Failed to load categories");
        return res.json();
      })
      .then(data => {
        setCategories(data);
        if (data.physical.length > 0) {
          setSelectedCategory(data.physical[0]);
        }
      })
      .catch(err => console.error("Error loading categories:", err));
  }, []);

  // Fetch category profile on selection change
  useEffect(() => {
    if (!selectedCategory) return;
    
    // Only fetch if not already loaded in local memory
    if (categoryProfiles[selectedCategory]) return;

    fetch(`/api/profile/${selectedCategory}`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to load category profile");
        return res.json();
      })
      .then(data => {
        setCategoryProfiles(prev => ({ ...prev, [selectedCategory]: data }));
      })
      .catch(err => console.error(`Error loading profile for ${selectedCategory}:`, err));
  }, [selectedCategory, categoryProfiles]);

  // Fetch Analyzer report on mount
  useEffect(() => {
    fetch('/api/analyzer')
      .then(res => {
        if (res.ok) return res.json();
        return null;
      })
      .then(data => setAnalyzerReport(data))
      .catch(err => console.error("Error loading training report:", err));
  }, []);

  const handleCoach = async () => {
    setIsLoadingCoach(true);
    setCoachResult(null);
    setSimulatorRightTab('critique');
    try {
      const res = await fetch('/api/coach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          price: price,
          description: description,
          category: selectedCategory,
          mock: mockMode
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Coaching analysis failed");
      }
      const data = await res.json();
      setCoachResult(data);
    } catch (err) {
      alert(`Error coaching: ${err.message}`);
    } finally {
      setIsLoadingCoach(false);
    }
  };

  const handlePredict = async () => {
    setIsLoadingPredict(true);
    setPredictResult(null);
    setSimulatorRightTab('prediction');
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: productName,
          price: price,
          description: description,
          category: selectedCategory,
          mock: mockMode
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Prediction analysis failed");
      }
      const data = await res.json();
      setPredictResult(data);
    } catch (err) {
      alert(`Error predicting success: ${err.message}`);
    } finally {
      setIsLoadingPredict(false);
    }
  };

  const applyImprovedSpec = (improvedText) => {
    setDescription(improvedText);
  };

  return (
    <div style={styles.app}>
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        mockMode={mockMode}
        setMockMode={setMockMode}
        theme={theme}
        setTheme={setTheme}
      />

      <main style={styles.main}>
        {/* VIEW 1: SIMULATOR */}
        {activeTab === 'simulator' && (
          <div style={styles.simulatorGrid}>
            <div style={styles.simulatorLeft}>
              <SimulatorForm
                categories={categories}
                categoryProfiles={categoryProfiles}
                selectedCategory={selectedCategory}
                setSelectedCategory={setSelectedCategory}
                productType={productType}
                setProductType={setProductType}
                name={productName}
                setName={setProductName}
                price={price}
                setPrice={setPrice}
                description={description}
                setDescription={setDescription}
                onCoach={handleCoach}
                onPredict={handlePredict}
                isLoadingCoach={isLoadingCoach}
                isLoadingPredict={isLoadingPredict}
                hoveredAspect={hoveredAspect}
                setHoveredAspect={setHoveredAspect}
                previewImpact={previewImpact}
                setPreviewImpact={setPreviewImpact}
              />
            </div>

            <div style={styles.simulatorRight}>
              <div style={styles.resultsTabBar}>
                <button
                   onClick={() => setSimulatorRightTab('critique')}
                   style={{
                     ...styles.resultsTabBtn,
                     color: simulatorRightTab === 'critique' ? 'var(--text-primary)' : 'var(--text-muted)',
                     borderBottomColor: simulatorRightTab === 'critique' ? 'var(--accent)' : 'transparent',
                   }}
                >
                  Spec Critique
                </button>
                <button
                   onClick={() => setSimulatorRightTab('prediction')}
                   style={{
                     ...styles.resultsTabBtn,
                     color: simulatorRightTab === 'prediction' ? 'var(--text-primary)' : 'var(--text-muted)',
                     borderBottomColor: simulatorRightTab === 'prediction' ? 'var(--accent)' : 'transparent',
                   }}
                >
                  Success Prediction
                </button>
              </div>

              <div style={styles.rightContentArea}>
                {simulatorRightTab === 'critique' && (
                  <>
                    {isLoadingCoach ? (
                      <LoadingPanel messages={[
                        'Reading your specification…',
                        'Retrieving category intelligence…',
                        'Surfacing consumer pain points…',
                        'Scoring aspect coverage…',
                        'Drafting sharpening questions…',
                      ]} />
                    ) : (
                      <SpecCoachPanel
                        coachResult={coachResult}
                        onApplyImprovedSpec={applyImprovedSpec}
                      />
                    )}
                  </>
                )}

                {simulatorRightTab === 'prediction' && (
                  <>
                    {isLoadingPredict ? (
                      <LoadingPanel messages={[
                        'Bridging specs to consumer aspects…',
                        'Grounding scores in category data…',
                        'Running XGBoost viability models…',
                        'Computing SHAP explanations…',
                        'Benchmarking against category leaders…',
                      ]} />
                    ) : predictResult ? (
                      <PredictorResults
                        result={predictResult}
                        categoryProfile={categoryProfiles[selectedCategory]}
                        hoveredAspect={hoveredAspect}
                        setHoveredAspect={setHoveredAspect}
                        previewImpact={previewImpact}
                        setPreviewImpact={setPreviewImpact}
                      />
                    ) : (
                      <div style={styles.emptyState}>
                        <Cpu size={32} color="var(--text-muted)" />
                        <p style={styles.emptyText}>Run "Predict success" to generate your viability score and metrics checklist.</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: EXPLORER */}
        {activeTab === 'explorer' && (
          <div style={styles.paddedView} className="animate-fade-in">
            <div style={styles.viewHeader}>
              <h2 style={styles.viewTitle}>Category Explorer</h2>
              <p style={styles.viewSubtitle}>Inspect aggregated market intelligence and historical consumer concerns.</p>
            </div>

            <div style={styles.explorerLayout}>
              <div style={styles.explorerLeft}>
                <label style={styles.label}>Select Category to Explore</label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  style={styles.select}
                >
                  {Object.keys(categoryProfiles).map(cat => (
                    <option key={cat} value={cat}>
                      {cat.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
                
                {categoryProfiles[selectedCategory] && (
                  <div style={styles.explorerMetrics}>
                    <div style={styles.explorerMetricCard}>
                      <span style={styles.explorerMetricLabel}>Historical Products</span>
                      <span style={styles.explorerMetricVal}>{categoryProfiles[selectedCategory].n_products}</span>
                    </div>
                    <div style={styles.explorerMetricCard}>
                      <span style={styles.explorerMetricLabel}>Median Price</span>
                      <span style={styles.explorerMetricVal}>${categoryProfiles[selectedCategory].price?.median}</span>
                    </div>
                    <div style={styles.explorerMetricCard}>
                      <span style={styles.explorerMetricLabel}>Success Threshold (p75)</span>
                      <span style={styles.explorerMetricVal}>{categoryProfiles[selectedCategory].success_score?.p75_threshold?.toFixed(1)}</span>
                    </div>
                  </div>
                )}
              </div>

              <div style={styles.explorerRight}>
                {categoryProfiles[selectedCategory] ? (
                  <div style={styles.explorerDetailsContainer}>
                    {/* Pain Points */}
                    <div style={styles.explorerSection}>
                      <h3 style={styles.explorerSectionTitle}>Top Customer Pain Points</h3>
                      <div style={styles.verbatimsContainer}>
                        {categoryProfiles[selectedCategory].pain_points?.aspects.map(aspect => (
                          <div key={aspect} style={styles.verbatimCard}>
                            <span style={styles.verbatimAspectBadge}>{aspect.replace(/_/g, ' ')}</span>
                            <div style={styles.quotesList}>
                              {categoryProfiles[selectedCategory].pain_points.evidence[aspect]?.slice(0, 2).map((q, qIdx) => (
                                <blockquote key={qIdx} style={styles.quote}>"{q}"</blockquote>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Strengths */}
                    <div style={styles.explorerSection}>
                      <h3 style={styles.explorerSectionTitle}>Top Customer Strengths</h3>
                      <div style={styles.verbatimsContainer}>
                        {categoryProfiles[selectedCategory].strengths?.aspects.map(aspect => (
                          <div key={aspect} style={{...styles.verbatimCard, borderLeftColor: 'var(--success)'}}>
                            <span style={{...styles.verbatimAspectBadge, backgroundColor: 'var(--success-muted)', color: 'var(--success)'}}>{aspect.replace(/_/g, ' ')}</span>
                            <div style={styles.quotesList}>
                              {categoryProfiles[selectedCategory].strengths.evidence[aspect]?.slice(0, 2).map((q, qIdx) => (
                                <blockquote key={qIdx} style={styles.quote}>"{q}"</blockquote>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Reddit Priority Summary */}
                    {categoryProfiles[selectedCategory].reddit_summary && (
                      <div style={{...styles.explorerSection, gridColumn: 'span 2'}}>
                        <h3 style={styles.explorerSectionTitle}>Reddit Priority Summary</h3>
                        <div style={styles.redditCard}>
                          <p style={styles.redditText}>{categoryProfiles[selectedCategory].reddit_summary}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <LoadingPanel messages={[
                    'Fetching category intelligence…',
                    'Loading price & aspect benchmarks…',
                  ]} />
                )}
              </div>
            </div>
          </div>
        )}

        {/* VIEW 3: ANALYZER */}
        {activeTab === 'analyzer' && (
          <div style={styles.paddedView} className="animate-fade-in">
            <div style={styles.viewHeader}>
              <h2 style={styles.viewTitle}>Model Performance Analyzer</h2>
              <p style={styles.viewSubtitle}>Verify cross-validation benchmarks and feature influence charts.</p>
            </div>

            {analyzerReport ? (
              <div style={styles.analyzerGrid}>
                {/* Performance Metrics Table */}
                <div style={styles.analyzerCard}>
                  <h3 style={styles.analyzerCardTitle}>XGBoost Validation Benchmarks</h3>
                  <div style={styles.tableWrapper}>
                    <table style={styles.table}>
                      <thead>
                        <tr style={styles.tr}>
                          <th style={styles.th}>Model Type</th>
                          <th style={styles.th}>CV R² Score</th>
                          <th style={styles.th}>MAE (Error)</th>
                          <th style={styles.th}>RMSE</th>
                          <th style={styles.th}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ['Physical Product (Full)', analyzerReport.physical?.full],
                          ['Physical Product (Aspects-Only)', analyzerReport.physical?.aspects_only],
                        ].map(([label, m]) => {
                          const gate = (m?.gate || '').split(' ')[0] || 'N/A';
                          const badge = gate === 'PASS' ? styles.passBadge
                            : {...styles.passBadge,
                               background: gate === 'FAIL' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                               color: gate === 'FAIL' ? '#EF4444' : '#F59E0B'};
                          return (
                            <tr style={styles.tr} key={label}>
                              <td style={{...styles.td, fontWeight: 600}}>{label}</td>
                              <td style={styles.td}>{m?.mean_r2 != null ? m.mean_r2.toFixed(3) : '—'}</td>
                              <td style={styles.td}>{m?.mean_mae != null ? m.mean_mae.toFixed(2) : '—'}</td>
                              <td style={styles.td}>{m?.mean_rmse != null ? m.mean_rmse.toFixed(2) : '—'}</td>
                              <td style={styles.td}><span style={badge} title={m?.gate || ''}>{gate}</span></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Honesty context box */}
                <div style={styles.infoPanel}>
                  <h3 style={styles.infoPanelTitle}>Understanding "Aspects-Only" vs "Full Model"</h3>
                  <div style={styles.infoPanelBody}>
                    <p style={styles.infoText}>
                      To prevent structural leakage during training, we maintain two parallel configurations of our XGBoost success models:
                    </p>
                    <ul style={styles.infoList}>
                      <li>
                        <strong>Full Model:</strong> Includes market priors (review velocity, rating volume, average rating). This achieves higher R² because historical ratings are part of the target formula, representing a baseline evaluation.
                      </li>
                      <li>
                        <strong>Aspects-Only Model:</strong> Excludes volume data, learning solely on the sentiment scores bridged from specifications. <strong>This is the headline indicator.</strong> It reflects only the levers founders can actually control pre-launch.
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            ) : (
              <LoadingPanel messages={[
                'Loading model training report…',
                'Reading cross-validation metrics…',
              ]} />
            )}
          </div>
        )}

        {/* VIEW 4: ABOUT THE MODEL */}
        {activeTab === 'about' && (
          <div style={styles.paddedView} className="animate-fade-in">
            <div style={styles.viewHeader}>
              <h2 style={styles.viewTitle}>About the Predictive Model</h2>
              <p style={styles.viewSubtitle}>Review design parameters, training pipelines, and data constraints.</p>
            </div>

            <div style={styles.aboutGrid}>
              <div style={styles.aboutCard}>
                <h3 style={styles.aboutCardTitle}>Data & Methodology</h3>
                <p style={styles.aboutText}>
                  The Hybrid AI Success Predictor works by bridging qualitative product specifications to quantitative consumer sentiment records. 
                  We analyze reviews across 10 categories, extracting aspect-based sentiment scores (0–10) and mapping them to a normalized regression target.
                </p>
                <p style={styles.aboutText}>
                  This approach allows us to simulate launch viabilityblind: mapping design concepts to historical reviews of similar products, bypassing the need for active sales history.
                </p>
              </div>

              <div style={styles.aboutCard}>
                <h3 style={styles.aboutCardTitle}>Methodological Constraints</h3>
                <div style={styles.constraintsList}>
                  <div style={styles.constraintItem}>
                    <strong style={styles.constraintTitle}>Proxy Labels Limit</strong>
                    <p style={styles.aboutText}>Success labels are engineered from volume and ratings. They capture overall consumer reception, not actual financial returns or unit sales.</p>
                  </div>
                  <div style={styles.constraintItem}>
                    <strong style={styles.constraintTitle}>US Market Bias</strong>
                    <p style={styles.aboutText}>Training data is sourced primarily from Amazon US and US Google Play stores. Predictions may not generalize to Eastern European, Asian, or Latin American markets.</p>
                  </div>
                  <div style={styles.constraintItem}>
                    <strong style={styles.constraintTitle}>Robustness Filtering</strong>
                    <p style={styles.aboutText}>Products with suspicious reviews (e.g. review velocity bursts, duplicate texts, unnatural ratings distribution) are filtered out of the training matrix to protect the algorithm from review manipulation.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

const styles = {
  app: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: 'var(--bg-app)',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  simulatorGrid: {
    display: 'grid',
    gridTemplateColumns: '400px 1fr',
    flex: 1,
    '@media (max-width: 1024px)': {
      gridTemplateColumns: '1fr',
    }
  },
  simulatorLeft: {
    borderRight: '1px solid var(--border)',
    padding: '32px',
    height: 'calc(100vh - 64px)',
    overflowY: 'auto',
    backgroundColor: 'var(--bg-app)',
    '@media (max-width: 1024px)': {
      height: 'auto',
      borderRight: 'none',
      borderBottom: '1px solid var(--border)',
    }
  },
  simulatorRight: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 64px)',
    backgroundColor: 'var(--bg-app)',
    overflow: 'hidden',
    '@media (max-width: 1024px)': {
      height: 'auto',
    }
  },
  resultsTabBar: {
    display: 'flex',
    height: '48px',
    borderBottom: '1px solid var(--border)',
    backgroundColor: 'var(--bg-panel)',
    padding: '0 32px',
    gap: '24px',
  },
  resultsTabBtn: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    borderRadius: 0,
    height: '100%',
    padding: '0 4px',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'color var(--transition-fast), border-color var(--transition-fast)',
  },
  rightContentArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '32px',
  },
  paddedView: {
    padding: '40px 64px',
    maxWidth: '1200px',
    width: '100%',
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '32px',
  },
  viewHeader: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '20px',
  },
  viewTitle: {
    fontSize: '26px',
    fontWeight: 700,
  },
  viewSubtitle: {
    fontSize: '14px',
    color: 'var(--text-muted)',
  },
  loadingArea: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '300px',
    gap: '16px',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '2px solid var(--border)',
    borderTopColor: 'var(--accent)',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  loadingText: {
    fontSize: '14px',
    color: 'var(--text-secondary)',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 0',
    gap: '16px',
    textAlign: 'center',
  },
  emptyText: {
    color: 'var(--text-muted)',
    fontSize: '14px',
    maxWidth: '280px',
    lineHeight: '1.5',
  },
  explorerLayout: {
    display: 'grid',
    gridTemplateColumns: '300px 1fr',
    gap: '32px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    }
  },
  explorerLeft: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  explorerMetrics: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginTop: '12px',
  },
  explorerMetricCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  explorerMetricLabel: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
  },
  explorerMetricVal: {
    fontSize: '20px',
    fontWeight: 700,
    fontFamily: 'var(--font-heading)',
  },
  explorerRight: {
    display: 'flex',
    flexDirection: 'column',
  },
  explorerDetailsContainer: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '24px',
    '@media (max-width: 1024px)': {
      gridTemplateColumns: '1fr',
    }
  },
  explorerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  explorerSectionTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    borderBottom: '1px solid var(--border)',
    paddingBottom: '8px',
  },
  verbatimsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  verbatimCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderLeft: '4px solid var(--danger)',
    borderRadius: 'var(--radius-sm)',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  verbatimAspectBadge: {
    alignSelf: 'flex-start',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    backgroundColor: 'var(--danger-muted)',
    color: 'var(--danger)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  quotesList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  quote: {
    fontSize: '12.5px',
    fontStyle: 'italic',
    color: 'var(--text-primary)',
    lineHeight: '1.4',
  },
  redditCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px',
  },
  redditText: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: 'var(--text-primary)',
  },
  analyzerGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  analyzerCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '28px',
    boxShadow: 'var(--shadow-sm)',
  },
  analyzerCardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '16px',
  },
  infoPanel: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '28px',
  },
  infoPanelTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '12px',
  },
  infoPanelBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  infoText: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: 'var(--text-secondary)',
  },
  infoList: {
    paddingLeft: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    fontSize: '13.5px',
    color: 'var(--text-secondary)',
  },
  passBadge: {
    backgroundColor: 'var(--success-muted)',
    color: 'var(--success)',
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.05em',
  },
  aboutGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '32px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    }
  },
  aboutCard: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: 'var(--shadow-sm)',
  },
  aboutCardTitle: {
    fontSize: '18px',
    fontWeight: 600,
    borderBottom: '1px solid var(--border)',
    paddingBottom: '12px',
  },
  aboutText: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: 'var(--text-secondary)',
  },
  constraintsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  constraintItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  constraintTitle: {
    fontSize: '13.5px',
    color: 'var(--text-primary)',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
  },
  select: {
    height: '42px',
    cursor: 'pointer',
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
  th: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textAnchor: 'start',
    padding: '12px 16px',
    textTransform: 'uppercase',
  },
  td: {
    padding: '14px 16px',
    fontSize: '13.5px',
    color: 'var(--text-primary)',
  }
};
