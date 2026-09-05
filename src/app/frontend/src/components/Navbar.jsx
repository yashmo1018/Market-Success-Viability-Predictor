import React from 'react';
import { Sun, Moon, Cpu, Layers, Activity, HelpCircle } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, mockMode, setMockMode, theme, setTheme }) {
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const navItems = [
    { id: 'simulator', label: 'Simulator', icon: Cpu },
    { id: 'explorer', label: 'Explorer', icon: Layers },
    { id: 'analyzer', label: 'Analyzer', icon: Activity },
    { id: 'about', label: 'About the Model', icon: HelpCircle }
  ];

  return (
    <header style={styles.header}>
      <div style={styles.logoContainer}>
        <div style={styles.logoBadge}>AI</div>
        <span style={styles.logoText}>Success Predictor</span>
      </div>
      
      <nav style={styles.nav}>
        {navItems.map(item => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                ...styles.navButton,
                color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                borderBottomColor: isActive ? 'var(--accent)' : 'transparent',
              }}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      
      <div style={styles.controls}>
        <label style={styles.toggleContainer}>
          <input
            type="checkbox"
            checked={mockMode}
            onChange={(e) => setMockMode(e.target.checked)}
            style={styles.checkbox}
          />
          <span style={styles.toggleLabel}>Mock LLM Mode</span>
        </label>
        
        <button onClick={toggleTheme} style={styles.themeBtn} title="Toggle theme">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </header>
  );
}

const styles = {
  header: {
    position: 'sticky',
    top: 0,
    zIndex: 100,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    height: '64px',
    backgroundColor: 'var(--bg-app)',
    borderBottom: '1px solid var(--border)',
    transition: 'background-color var(--transition-normal), border-color var(--transition-normal)',
  },
  logoContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  logoBadge: {
    backgroundColor: 'var(--text-primary)',
    color: 'var(--bg-app)',
    fontFamily: 'var(--font-heading)',
    fontWeight: 800,
    fontSize: '12px',
    padding: '2px 6px',
    borderRadius: '4px',
    letterSpacing: '0.05em',
  },
  logoText: {
    fontFamily: 'var(--font-heading)',
    fontSize: '16px',
    fontWeight: 600,
    letterSpacing: '-0.01em',
    color: 'var(--text-primary)',
  },
  nav: {
    display: 'flex',
    height: '100%',
    gap: '24px',
  },
  navButton: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    borderRadius: 0,
    padding: '0 4px',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    fontWeight: 500,
    transition: 'color var(--transition-fast), border-color var(--transition-fast)',
  },
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
  },
  toggleContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
    fontSize: '13px',
    color: 'var(--text-secondary)',
  },
  checkbox: {
    width: '16px',
    height: '16px',
    cursor: 'pointer',
  },
  toggleLabel: {
    userSelect: 'none',
  },
  themeBtn: {
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '8px',
    color: 'var(--text-secondary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color var(--transition-fast), border-color var(--transition-fast), background-color var(--transition-fast)',
  }
};
