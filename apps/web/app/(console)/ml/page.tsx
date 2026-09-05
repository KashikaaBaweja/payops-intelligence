"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { getMerchantRegression, getMerchantRisk } from "../../../lib/api";
import { formatPercent } from "../../../lib/format";
import type { MerchantRiskScore, RegressionScore } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

export default function MlPage() {
  const [tab, setTab] = useState<"classification" | "regression">("classification");
  const [risk, setRisk] = useState<MerchantRiskScore | null>(null);
  const [reg, setReg] = useState<RegressionScore | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getMerchantRisk("M102").catch(() => null),
      getMerchantRegression("M102").catch(() => null),
    ])
      .then(([classified, latency]) => {
        setRisk(classified);
        setReg(latency);
        if (!classified && !latency) {
          setError("Neither ML endpoint returned a score for Harbor Retail M102.");
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "ML endpoints failed."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">ML intelligence</h1>
      <p className="page-lead">
        Harbor Retail M102 holdout models. Classification predicts payment failure
        probability. Regression predicts capture latency. Metrics stay on their own tab.
      </p>
      <div className="cta-row" role="tablist" aria-label="ML task">
        <button
          className={`btn ${tab === "classification" ? "btn-primary" : ""}`}
          style={{ width: "auto" }}
          type="button"
          role="tab"
          aria-selected={tab === "classification"}
          onClick={() => setTab("classification")}
        >
          Classification
        </button>
        <button
          className={`btn ${tab === "regression" ? "btn-primary" : ""}`}
          style={{ width: "auto" }}
          type="button"
          role="tab"
          aria-selected={tab === "regression"}
          onClick={() => setTab("regression")}
        >
          Regression
        </button>
      </div>
      {loading ? <LoadingState label="Fitting holdout views…" /> : null}
      {error && !risk && !reg ? <ErrorState message={error} /> : null}
      {tab === "classification" ? (
        <section className="panel" role="tabpanel">
          <div className="panel-hd">Failure classifier</div>
          <div className="panel-bd">
            {!risk ? (
              <EmptyState
                title="No classifier payload"
                detail="The risk endpoint did not return a score. Confirm the API and seed."
              />
            ) : (
              <>
                <dl className="kv">
                  <dt>Prediction</dt>
                  <dd>
                    {risk.prediction} · {risk.risk_class}
                  </dd>
                  <dt>Confidence</dt>
                  <dd className="mono">{formatPercent(risk.risk_probability)}</dd>
                  <dt>Precision</dt>
                  <dd className="mono">{risk.quality.precision.toFixed(3)}</dd>
                  <dt>Recall</dt>
                  <dd className="mono">{risk.quality.recall.toFixed(3)}</dd>
                  <dt>F1</dt>
                  <dd className="mono">{risk.quality.f1.toFixed(3)}</dd>
                </dl>
                <div className="matrix" aria-label="Confusion matrix">
                  <div className="matrix-cell faint"> </div>
                  <div className="matrix-cell faint">Predicted ok</div>
                  <div className="matrix-cell faint">Predicted fail</div>
                  <div className="matrix-cell faint">Actual ok</div>
                  <div className="matrix-cell">
                    TN {risk.quality.confusion_matrix.true_negative}
                  </div>
                  <div className="matrix-cell">
                    FP {risk.quality.confusion_matrix.false_positive}
                  </div>
                  <div className="matrix-cell faint">Actual fail</div>
                  <div className="matrix-cell">
                    FN {risk.quality.confusion_matrix.false_negative}
                  </div>
                  <div className="matrix-cell">
                    TP {risk.quality.confusion_matrix.true_positive}
                  </div>
                </div>
                <p className="banner">{risk.notes}</p>
              </>
            )}
          </div>
        </section>
      ) : (
        <section className="panel" role="tabpanel">
          <div className="panel-hd">Capture-latency regressor</div>
          <div className="panel-bd">
            {!reg ? (
              <EmptyState
                title="No regressor payload"
                detail="The capture-latency endpoint did not return a score."
              />
            ) : (
              <dl className="kv">
                <dt>Prediction</dt>
                <dd className="mono">
                  {reg.prediction.toFixed(2)} {reg.unit}
                </dd>
                <dt>MAE</dt>
                <dd className="mono">{reg.quality.mae.toFixed(2)}</dd>
                <dt>RMSE</dt>
                <dd className="mono">{reg.quality.rmse.toFixed(2)}</dd>
                <dt>R²</dt>
                <dd className="mono">{reg.quality.r2.toFixed(2)}</dd>
              </dl>
            )}
          </div>
        </section>
      )}
    </>
  );
}
