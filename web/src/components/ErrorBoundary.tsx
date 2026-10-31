import { Component, type ReactNode } from "react";
import { Icon } from "./Icon";
import { useI18n } from "../i18n";

interface State { err: Error | null; key: number }

function Fallback({ onRetry, err }: { onRetry: () => void; err: Error }) {
  const { t } = useI18n();
  const chunk = /dynamically imported|Importing a module|Failed to fetch|ChunkLoad/i.test(err.message);
  return (
    <section className="notice notice-block" role="alert">
      <h2>{chunk ? t("err.chunk") : t("err.boundary")}</h2>
      <p>{chunk ? t("err.chunk_help") : t("err.boundary_help")}</p>
      <button className="btn btn-primary" onClick={chunk ? () => location.reload() : onRetry}>
        <Icon name="retry" /> {t("act.retry")}
      </button>
      <p className="mono small faint">{err.message.slice(0, 160)}</p>
    </section>
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, State> {
  state: State = { err: null, key: 0 };
  static getDerivedStateFromError(err: Error) {
    return { err };
  }
  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.err) this.setState({ err: null });
  }
  componentDidCatch(err: Error) {
    console.error(err);
  }
  render() {
    if (this.state.err) {
      return <Fallback err={this.state.err} onRetry={() => this.setState((s) => ({ err: null, key: s.key + 1 }))} />;
    }
    return <div key={this.state.key} className="boundary">{this.props.children}</div>;
  }
}
