export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-box" role="status">
      {label}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      <div className="banner" style={{ marginTop: 6 }}>
        {detail}
      </div>
    </div>
  );
}

export function ErrorState({ message, requestId }: { message: string; requestId?: string }) {
  return (
    <div className="error-box" role="alert">
      {message}
      {requestId ? <div className="mono">request {requestId}</div> : null}
    </div>
  );
}
