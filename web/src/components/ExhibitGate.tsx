import { useState } from "react";
import { useI18n, type Key } from "../i18n";
import { retryExhibit, type ExhibitStatus } from "../api";
import { Icon } from "./Icon";
import { ErrorNote, Missing } from "./Bits";

/**
 * Exhibits land after the verdict. Each says honestly whether it is still computing, could not be
 * made, or does not apply. Older records carry no status, and those render their content directly.
 */
export function ExhibitGate({ name, status, caseId, sealed, onRetried, children }: {
  name: string;
  status: ExhibitStatus | undefined;
  caseId: string;
  sealed: boolean;
  onRetried: () => void;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const what = t(`exhibit.${name}` as Key);

  if (!status || status.status === "done") return <>{children}</>;

  if (status.status === "pending") {
    return (
      <div className="computing" role="status">
        <span className="spinner" aria-hidden="true" />
        <div>
          <p className="computing-what">{what}: {t("exhibit.pending")}</p>
          <p className="small faint">{t("exhibit.pending_why")}</p>
        </div>
      </div>
    );
  }

  const retry = async () => {
    setBusy(true);
    setErr(null);
    try {
      await retryExhibit(caseId, name);
      onRetried();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const why = status.status === "failed" ? t("exhibit.failed_why") : t("exhibit.not_applicable_why");
  return (
    <Missing what={what} why={why}>
      {status.reason && (
        <details className="fine">
          <summary>{t("exhibit.technical")}</summary>
          <p className="small" lang="en">{status.reason}</p>
        </details>
      )}
      {status.status === "failed" && (
        sealed
          ? <button className="btn" onClick={retry} disabled={busy}><Icon name="retry" /> {t("act.retry")}</button>
          : <p className="small faint">{t("exhibit.retry_after_seal")}</p>
      )}
      {err !== null && <ErrorNote error={err} />}
    </Missing>
  );
}
