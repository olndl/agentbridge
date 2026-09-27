import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  Bot,
  Braces,
  CheckCircle2,
  GitBranch,
  Play,
  RefreshCw,
  ServerCog,
  Sparkles,
  Webhook,
} from "lucide-react";
import "./styles.css";

type Integration = {
  id: string;
  name: string;
  source: string;
  target: string;
  target_schema: Record<string, string>;
  mapping: Record<string, string>;
  enabled: boolean;
  created_at: string;
};

type Run = {
  id: string;
  integration_id: string;
  source: string;
  target: string;
  status: "received" | "mapped" | "delivered" | "failed";
  raw_payload: Record<string, unknown>;
  mapped_payload?: Record<string, unknown>;
  delivery_response?: Record<string, unknown>;
  error?: string;
  created_at: string;
  updated_at: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const githubPayload = {
  issue: {
    id: 4812,
    title: "Sync HubSpot company lifecycle stage",
    html_url: "https://github.com/acme/revops/issues/4812",
    labels: [{ name: "high" }],
  },
  repository: {
    full_name: "acme/revops",
  },
};

function App() {
  const [integrations, setIntegrations] = React.useState<Integration[]>([]);
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = React.useState<string>("");
  const [samplePayload, setSamplePayload] = React.useState(
    JSON.stringify(githubPayload, null, 2),
  );
  const [isLoading, setIsLoading] = React.useState(false);

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0];

  async function refresh() {
    const [integrationsResponse, runsResponse] = await Promise.all([
      fetch(`${API_URL}/integrations`),
      fetch(`${API_URL}/runs`),
    ]);
    setIntegrations(await integrationsResponse.json());
    const nextRuns = await runsResponse.json();
    setRuns(nextRuns);
    if (!selectedRunId && nextRuns.length > 0) {
      setSelectedRunId(nextRuns[0].id);
    }
  }

  async function sendWebhook() {
    setIsLoading(true);
    try {
      await fetch(`${API_URL}/webhooks/github`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Idempotency-Key": `demo-${Date.now()}`,
        },
        body: samplePayload,
      });
      await refresh();
    } finally {
      setIsLoading(false);
    }
  }

  React.useEffect(() => {
    refresh();
  }, []);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Bot size={24} />
          </div>
          <div>
            <strong>AgentBridge</strong>
            <span>AI integration runtime</span>
          </div>
        </div>
        <nav className="nav">
          <a className="active">
            <Activity size={18} />
            Operations
          </a>
          <a>
            <Webhook size={18} />
            Webhooks
          </a>
          <a>
            <GitBranch size={18} />
            Mappings
          </a>
          <a>
            <ServerCog size={18} />
            Adapters
          </a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Production-style integrations</p>
            <h1>Agentic workflows from webhook to delivered record</h1>
          </div>
          <button className="icon-button" onClick={refresh} aria-label="Refresh">
            <RefreshCw size={18} />
          </button>
        </header>

        <section className="metrics">
          <Metric
            label="Active integrations"
            value={String(integrations.filter((item) => item.enabled).length)}
          />
          <Metric
            label="Delivered runs"
            value={String(runs.filter((run) => run.status === "delivered").length)}
          />
          <Metric
            label="Failure rate"
            value={`${failureRate(runs)}%`}
          />
        </section>

        <section className="main-grid">
          <div className="panel integration-panel">
            <PanelTitle icon={<Sparkles size={18} />} title="Integration flows" />
            <div className="flow-list">
              {integrations.map((integration) => (
                <article className="flow-card" key={integration.id}>
                  <div>
                    <strong>{integration.name}</strong>
                    <span>{integration.id}</span>
                  </div>
                  <div className="flow-route">
                    <code>{integration.source}</code>
                    <span />
                    <code>{integration.target}</code>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="panel simulate-panel">
            <PanelTitle icon={<Webhook size={18} />} title="Webhook simulator" />
            <textarea
              value={samplePayload}
              onChange={(event) => setSamplePayload(event.target.value)}
              spellCheck={false}
            />
            <button className="primary-button" onClick={sendWebhook} disabled={isLoading}>
              <Play size={16} />
              {isLoading ? "Sending..." : "Send GitHub event"}
            </button>
          </div>

          <div className="panel runs-panel">
            <PanelTitle icon={<Activity size={18} />} title="Recent runs" />
            <div className="run-list">
              {runs.map((run) => (
                <button
                  className={run.id === selectedRun?.id ? "run-row selected" : "run-row"}
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                >
                  <StatusIcon status={run.status} />
                  <span>
                    <strong>{run.id}</strong>
                    <small>{new Date(run.created_at).toLocaleString()}</small>
                  </span>
                  <Badge status={run.status} />
                </button>
              ))}
              {runs.length === 0 && <p className="empty">No runs yet.</p>}
            </div>
          </div>

          <div className="panel detail-panel">
            <PanelTitle icon={<Braces size={18} />} title="Run payload" />
            {selectedRun ? (
              <div className="payload-grid">
                <JsonBlock label="Raw event" value={selectedRun.raw_payload} />
                <JsonBlock label="Mapped record" value={selectedRun.mapped_payload ?? {}} />
                <JsonBlock
                  label="Delivery response"
                  value={selectedRun.delivery_response ?? { error: selectedRun.error }}
                />
              </div>
            ) : (
              <p className="empty">Send a webhook to inspect the pipeline.</p>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function PanelTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="panel-title">
      {icon}
      <h2>{title}</h2>
    </div>
  );
}

function StatusIcon({ status }: { status: Run["status"] }) {
  if (status === "delivered") {
    return <CheckCircle2 className="ok" size={18} />;
  }
  return <Activity className={status} size={18} />;
}

function Badge({ status }: { status: Run["status"] }) {
  return <em className={`badge ${status}`}>{status}</em>;
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <section className="json-block">
      <span>{label}</span>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

function failureRate(runs: Run[]) {
  if (runs.length === 0) {
    return 0;
  }
  return Math.round((runs.filter((run) => run.status === "failed").length / runs.length) * 100);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
