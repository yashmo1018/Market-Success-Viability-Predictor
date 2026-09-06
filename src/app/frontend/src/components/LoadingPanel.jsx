import { useState, useEffect } from 'react';

/**
 * Animated loading panel: dual counter-rotating rings, a cycling stage message,
 * bouncing dots, and an indeterminate progress bar. Cycles through `messages`
 * so long-running calls (LLM bridging, model + SHAP) feel alive.
 */
export default function LoadingPanel({ messages }) {
  const list = messages && messages.length ? messages : ['Working…'];
  const [i, setI] = useState(0);

  useEffect(() => {
    if (list.length < 2) return undefined;
    const id = setInterval(() => setI((p) => (p + 1) % list.length), 1900);
    return () => clearInterval(id);
  }, [list.length]);

  return (
    <div style={S.wrap}>
      <div style={S.rings}>
        <div style={S.ringOuter} />
        <div style={S.ringInner} />
        <div style={S.core} />
      </div>

      {/* key on i so the message re-triggers the fade animation each change */}
      <p key={i} style={S.msg}>{list[i]}</p>

      <div style={S.dots}>
        <span style={{ ...S.dot, animationDelay: '0s' }} />
        <span style={{ ...S.dot, animationDelay: '0.15s' }} />
        <span style={{ ...S.dot, animationDelay: '0.3s' }} />
      </div>

      <div style={S.track}>
        <div style={S.bar} />
      </div>
    </div>
  );
}

const S = {
  wrap: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '300px', gap: '18px',
  },
  rings: { position: 'relative', width: '52px', height: '52px' },
  ringOuter: {
    position: 'absolute', inset: 0, borderRadius: '50%',
    border: '2px solid var(--border)', borderTopColor: 'var(--accent)',
    borderRightColor: 'var(--accent)', animation: 'spin 0.9s linear infinite',
  },
  ringInner: {
    position: 'absolute', inset: '9px', borderRadius: '50%',
    border: '2px solid transparent', borderBottomColor: 'var(--accent)',
    borderLeftColor: 'var(--accent)', opacity: 0.7,
    animation: 'spinRev 1.3s linear infinite',
  },
  core: {
    position: 'absolute', inset: '21px', borderRadius: '50%',
    background: 'var(--accent)', opacity: 0.85,
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  msg: {
    fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 500,
    textAlign: 'center', minHeight: '18px', margin: 0,
    animation: 'msgFade 0.4s ease',
  },
  dots: { display: 'flex', gap: '6px' },
  dot: {
    width: '6px', height: '6px', borderRadius: '50%',
    background: 'var(--accent)', display: 'inline-block',
    animation: 'dotBounce 1.2s ease-in-out infinite',
  },
  track: {
    position: 'relative', width: '200px', height: '3px',
    borderRadius: '3px', background: 'var(--border)', overflow: 'hidden',
  },
  bar: {
    position: 'absolute', top: 0, height: '100%', borderRadius: '3px',
    background: 'var(--accent)', animation: 'indeterminate 1.4s ease-in-out infinite',
  },
};
