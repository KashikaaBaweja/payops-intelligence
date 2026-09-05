const NODES = ["USER", "AI AGENTS", "RAG", "ML", "TRANSACTION INTELLIGENCE"];

export function ArchitectureFlow() {
  return (
    <div className="auth-flow" aria-hidden>
      <svg className="auth-flow-svg" viewBox="0 0 280 360" role="presentation">
        <defs>
          <linearGradient id="auth-line" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4c8dff" stopOpacity="0.15" />
            <stop offset="50%" stopColor="#4c8dff" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#4c8dff" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <line className="auth-flow-line" x1="140" y1="36" x2="140" y2="324" />
        {NODES.map((label, index) => {
          const y = 36 + index * 72;
          return (
            <g key={label}>
              <circle className="auth-flow-node" cx="140" cy={y} r="8" />
              <text className="auth-flow-label" x="164" y={y + 4}>
                {label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
