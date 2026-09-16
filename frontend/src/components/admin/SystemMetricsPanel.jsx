import React, { useState, useEffect } from "react";
import { API_BASE_URL, apiClient } from "../../apiClient";
import { closureFeedCounts } from "../../utils/closureAccess";

/** One read of GET /api/road-closures for the feed row. Module scope, so the panel's effect
 *  depends on nothing but state setters. On failure both setters record "unknown": the row
 *  shows "--", not the previous figures as if they were current. */
async function fetchClosureFeed(setClosureFeed, setClosureFeedOk) {
  try {
    const payload = await apiClient.roadClosures.fetchAll();
    // An api container older than 2026-09-16 sent the bare array and no sync status.
    const closures = Array.isArray(payload) ? payload : payload?.closures;
    const sync = Array.isArray(payload) ? null : (payload?.sync ?? null);
    setClosureFeed({ closures: Array.isArray(closures) ? closures : null, sync });
    setClosureFeedOk(true);
  } catch (err) {
    setClosureFeed(null);
    setClosureFeedOk(false);
    console.warn("Could not fetch road closure feed:", err);
  }
}

export default function SystemMetricsPanel({ dispatches = [], evaluations = [] }) {
  const [metricsSummary, setMetricsSummary] = useState(null);
  const [apiOk, setApiOk] = useState(null); // null until the first fetch answers
  const [, setLoading] = useState(true);
  // A value the system did not measure renders as "--", never as a plausible number (CLAUDE.md 6.1).
  const fmt = (v, unit = "") => (v == null ? "--" : `${v}${unit}`);
  const [selectedCall, setSelectedCall] = useState(null);
  // Road closure feed row. { closures, sync } from GET /api/road-closures, null until the
  // first answer, and null again when a fetch fails -- a failed read shows "--", not the
  // previous numbers as if they were current.
  const [closureFeed, setClosureFeed] = useState(null);
  const [closureFeedOk, setClosureFeedOk] = useState(null);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (dispatches && dispatches.length > 0 && !selectedCall) {
      setSelectedCall(dispatches[0]);
    }
    // Intentional: seeds a default selection when the list first arrives. selectedCall is
    // read only as the "nothing chosen yet" guard, never as an input. Listing it is a
    // no-op today -- setSelectedCall is called nowhere else, so the value never returns to
    // null -- but it would turn a later "clear selection" control into an immediate
    // re-seed back to dispatches[0]. Verified 2026-09-08.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatches]);

  const fetchMetrics = async () => {
    // Fetched on this panel's own 10 s tick, not a second poll loop. useRoadClosures holds the
    // same data but lives in MapBoard and polls every 5 min; reaching it here would mean
    // threading props through MapBoard and DispatchReview, and a watch panel five minutes
    // behind a forced sync is the wrong tool. The API caches the response for 60 s.
    fetchClosureFeed(setClosureFeed, setClosureFeedOk);
    try {
      const res = await fetch(`${API_BASE_URL}/api/metrics/summary`);
      setApiOk(res.ok);
      if (res.ok) {
        const data = await res.json();
        setMetricsSummary(data);
      }
    } catch (err) {
      setApiOk(false);
      console.warn("Could not fetch metrics summary:", err);
    } finally {
      setLoading(false);
    }
  };

  const feedSync = closureFeed?.sync ?? null;
  const feedCounts = closureFeedCounts(closureFeed?.closures);
  const feedSources = feedSync?.sources && typeof feedSync.sources === "object"
    ? Object.entries(feedSync.sources) : [];
  const feedSkipped = feedSync?.skipped ?? null;
  const feedAttemptAt = (() => {
    if (!feedSync?.lastAttemptAt) return null;
    const at = new Date(feedSync.lastAttemptAt);
    return Number.isNaN(at.getTime()) ? null
      : at.toLocaleString("en-CA", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" });
  })();
  const outcomeColor = { SUCCEEDED: "#4ade80", FAILED: "#f43f5e", NOT_ATTEMPTED: "#94a3b8" }[feedSync?.outcome] || "#94a3b8";

  const latestEval = evaluations && evaluations.length > 0
    // The most recent run that measured STT; parser and geocoder runs carry no WER (2026-09-05).
    ? ([...evaluations].reverse().find((e) => e.wer != null) || evaluations[evaluations.length - 1])
    : metricsSummary?.latest_evaluation;

  return (
    <div style={{ padding: "24px", color: "#f1f5f9", fontFamily: "sans-serif" }}>
      {/* Header Title */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.75rem", fontWeight: "700", background: "linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            📊 System Metrics & Performance Dashboard
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "#94a3b8", fontSize: "0.9rem" }}>
            STT evaluation history. Pipeline timings and container health are not measured here yet.
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", px: "12px", py: "6px", backgroundColor: "rgba(34,197,94,0.15)", border: "1px solid rgba(34,197,94,0.4)", borderRadius: "20px", color: "#4ade80", fontSize: "0.85rem", fontWeight: "600" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: apiOk ? "#22c55e" : apiOk === false ? "#f43f5e" : "#94a3b8" }}></span>
            {apiOk ? "Station Local API Online" : apiOk === false ? "Station Local API Unreachable" : "Checking API"}
          </span>
        </div>
      </div>

      {/* Top 4 Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginBottom: "28px" }}>
        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "18px" }}>
          <div style={{ color: "#94a3b8", fontSize: "0.8rem", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            ⚡ Phase 1 Phone Latency
          </div>
          <div style={{ fontSize: "2rem", fontWeight: "800", color: "#38bdf8", marginTop: "8px" }}>
            {fmt(metricsSummary?.telemetry?.phase1_alert_latency_s, "s")}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "4px" }}>
            Tone to phone alert. Not recorded yet.
          </div>
        </div>

        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "18px" }}>
          <div style={{ color: "#94a3b8", fontSize: "0.8rem", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🎙️ Phase 2 Broadcast Total
          </div>
          <div style={{ fontSize: "2rem", fontWeight: "800", color: "#a855f7", marginTop: "8px" }}>
            {fmt(metricsSummary?.telemetry?.phase2_total_latency_s, "s")}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "4px" }}>
            Tone to full dispatch. Not recorded yet.
          </div>
        </div>

        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "18px" }}>
          <div style={{ color: "#94a3b8", fontSize: "0.8rem", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🤖 Whisper STT Speed
          </div>
          <div style={{ fontSize: "2rem", fontWeight: "800", color: "#f43f5e", marginTop: "8px" }}>
            {fmt(metricsSummary?.telemetry?.stt_inference_time_s, "s")}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "4px" }}>
            {fmt(metricsSummary?.telemetry?.stt_speed_ratio, "x")} of real time. Not recorded yet.
          </div>
        </div>

        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "18px" }}>
          <div style={{ color: "#94a3b8", fontSize: "0.8rem", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            📍 GIS Parcel Lookup
          </div>
          <div style={{ fontSize: "2rem", fontWeight: "800", color: "#22c55e", marginTop: "8px" }}>
            {fmt(metricsSummary?.telemetry?.gis_lookup_time_ms, "ms")}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "4px" }}>
            Geocoder round trip. Not recorded yet.
          </div>
        </div>
      </div>

      {/* Waterfall Section */}
      <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "16px", padding: "24px", marginBottom: "28px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "700", color: "#f8fafc" }}>
            ⏱️ Pipeline Stages, In Order
          </h3>
          {selectedCall && (
            <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
              Call ID: <strong style={{ color: "#38bdf8" }}>{selectedCall.dispatch_id}</strong>
            </span>
          )}
        </div>

        {/* Visual Waterfall Bar */}
        <div style={{ marginTop: "16px" }}>
          <div style={{ fontSize: "0.85rem", color: "#94a3b8", marginBottom: "8px" }}>
            The agent times each stage per call but does not store the numbers, so this shows the order only.
          </div>

          <div style={{ display: "flex", height: "42px", borderRadius: "10px", overflow: "hidden", border: "1px solid rgba(255,255,255,0.15)", backgroundColor: "#020617" }}>
            {/* Tone Burst Phase */}
            <div style={{ flex: 1, backgroundColor: "#eab308", display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontWeight: "700", fontSize: "0.75rem", title: "Tone Burst Sequence (9.5s)" }}>
              🔔 Tones
            </div>
            {/* Speech Start Anchor */}
            <div style={{ flex: 1, backgroundColor: "#06b6d4", display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontWeight: "700", fontSize: "0.75rem" }}>
              "Coquitlam"
            </div>
            {/* Round 1 Broadcast */}
            <div style={{ flex: 1, backgroundColor: "#3b82f6", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "700", fontSize: "0.75rem" }}>
              Round 1 Speech
            </div>
            {/* Map Grid Boundary */}
            <div style={{ flex: 1, backgroundColor: "#10b981", display: "flex", alignItems: "center", justifyContent: "center", color: "#000", fontWeight: "700", fontSize: "0.75rem" }}>
              Map Grid [N]
            </div>
            {/* Whisper STT */}
            <div style={{ flex: 1, backgroundColor: "#a855f7", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "700", fontSize: "0.75rem" }}>
              Whisper STT
            </div>
            {/* Ntfy Push */}
            <div style={{ flex: 1, backgroundColor: "#f43f5e", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: "700", fontSize: "0.75rem" }}>
              📲 Ntfy
            </div>
          </div>

          {/* Timeline legend */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", marginTop: "14px", fontSize: "0.8rem", color: "#cbd5e1" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#eab308" }}></span>
              <span>Tone Bursts</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#06b6d4" }}></span>
              <span>"Coquitlam" Anchor</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#3b82f6" }}></span>
              <span>Spoken Round 1</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#10b981" }}></span>
              <span>Map Grid Boundary (1..134)</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#a855f7" }}></span>
              <span>Whisper STT</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "3px", backgroundColor: "#f43f5e" }}></span>
              <span>Ntfy Phone Alert</span>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Section: STT Regression & Container Infrastructure Health */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "24px" }}>
        {/* Left Column: STT Accuracy & MLOps Regression */}
        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "16px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: "1.1rem", fontWeight: "700", color: "#f8fafc" }}>
            📈 STT Model WER & CER Quality Metrics
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
            <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: "600" }}>WORD ERROR RATE (WER)</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "800", color: "#4ade80" }}>
                {latestEval?.wer != null ? `${latestEval.wer}%` : "--"}
              </div>
            </div>
            <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: "600" }}>CHARACTER ERROR RATE (CER)</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "800", color: "#38bdf8" }}>
                {latestEval?.cer != null ? `${latestEval.cer}%` : "--"}
              </div>
            </div>
          </div>

          <div style={{ fontSize: "0.85rem", color: "#cbd5e1" }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              <span>Perfect Matches (0% WER)</span>
              <strong style={{ color: "#4ade80" }}>{latestEval?.perfect_percent != null ? `${latestEval.perfect_percent}%` : "--"}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              <span>Operational Matches (&lt; 15% WER)</span>
              <strong style={{ color: "#38bdf8" }}>{latestEval?.operational_percent != null ? `${latestEval.operational_percent}%` : "--"}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0" }}>
              <span>Mismatches / Verification Needed</span>
              <strong style={{ color: "#f43f5e" }}>{latestEval?.failed_percent != null ? `${latestEval.failed_percent}%` : "--"}</strong>
            </div>
          </div>
        </div>

        {/* Right Column: Server & Container Infrastructure Health */}
        <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "16px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: "1.1rem", fontWeight: "700", color: "#f8fafc" }}>
            🖥️ Container Infrastructure & Host Telemetry
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {!Array.isArray(metricsSummary?.containers) && (
              <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
                Not visible from the API: its container has no Docker socket. On the kiosk, <code>docker ps</code> is the record.
              </div>
            )}
            {(metricsSummary?.containers || []).map((c) => (
              <div key={c.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(2, 6, 23, 0.6)", padding: "10px 14px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: c.status === "running" ? "#22c55e" : "#f43f5e" }}></span>
                  <span style={{ fontWeight: "600", fontFamily: "monospace", fontSize: "0.9rem" }}>{c.name}</span>
                </div>
                <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                  Status: <strong style={{ color: "#4ade80" }}>{c.status}</strong> ({fmt(c.uptime)})
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Road Closure Feed -- operator ruling 2026-09-16: watch the feed on the console, to
          spot patterns worth a rule later. Console only; nothing here reaches the hall display
          or the #89 banner. Every figure is read from GET /api/road-closures as served. */}
      <div style={{ background: "rgba(15, 23, 42, 0.75)", backdropFilter: "blur(12px)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "16px", padding: "20px", marginTop: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "8px", marginBottom: "14px" }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: "700", color: "#f8fafc" }}>
            🚧 Road Closure Feed
          </h3>
          {closureFeedOk === false && (
            <span style={{ fontSize: "0.85rem", color: "#f43f5e", fontWeight: "600" }}>
              Could not read GET /api/road-closures. Figures below are unknown.
            </span>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "12px" }}>
          {/* Last sync attempt */}
          <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: "600" }}>LAST SYNC ATTEMPT</div>
            <div style={{ fontSize: "1.25rem", fontWeight: "800", color: outcomeColor, marginTop: "4px" }}>
              {fmt(feedSync?.outcome)}
            </div>
            <div style={{ fontSize: "0.85rem", color: "#cbd5e1", marginTop: "4px" }}>
              At {fmt(feedAttemptAt)}
            </div>
            {feedSync?.error && (
              <div style={{ fontSize: "0.85rem", color: "#fda4af", marginTop: "6px", wordBreak: "break-word" }}>
                {feedSync.error}
              </div>
            )}
          </div>

          {/* Per source: reached, and records skipped for no feed id */}
          <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: "600" }}>SOURCES · SKIPPED, NO FEED ID</div>
            {feedSources.length === 0 ? (
              <div style={{ fontSize: "0.85rem", color: "#cbd5e1", marginTop: "6px" }}>--</div>
            ) : feedSources.map(([name, r]) => (
              <div key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.85rem" }}>
                <span style={{ color: "#e2e8f0" }}>{name}</span>
                <span style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <strong style={{ color: r?.reached === true ? "#4ade80" : r?.reached === false ? "#f43f5e" : "#94a3b8" }}>
                    {r?.reached === true ? "Reached" : r?.reached === false ? "Not reached" : "--"}
                  </strong>
                  <span style={{ color: "#cbd5e1", fontFamily: "monospace" }}>
                    skipped {feedSkipped ? fmt(feedSkipped.bySource?.[name]) : "--"}
                  </span>
                </span>
              </div>
            ))}
            <div style={{ fontSize: "0.85rem", color: "#cbd5e1", marginTop: "6px" }}>
              Skipped total: <strong style={{ color: feedSkipped?.count > 0 ? "#fbbf24" : "#e2e8f0" }}>{feedSkipped ? fmt(feedSkipped.count) : "--"}</strong>
            </div>
            {feedSkipped?.count > 0 && (
              <div style={{ fontSize: "0.8rem", color: "#fbbf24", marginTop: "4px" }}>
                Raw records in <code>journalctl -u</code> / <code>docker logs cfr_api</code>, ERROR.
              </div>
            )}
          </div>

          {/* Pattern counts over the served list */}
          <div style={{ background: "rgba(2, 6, 23, 0.6)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: "600" }}>SERVED LIST</div>
            <div style={{ fontSize: "0.85rem", color: "#cbd5e1" }}>
              {[
                ["Closures served", feedCounts?.total],
                ["Access N/A (no severity from feed)", feedCounts?.na],
                ["Info (all lanes open)", feedCounts?.info],
                ["No street name", feedCounts?.noStreet],
                ["No headline", feedCounts?.noHeadline],
              ].map(([label, value]) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <span>{label}</span>
                  <strong style={{ color: "#e2e8f0", fontFamily: "monospace" }}>
                    {fmt(value)}{value != null && feedCounts?.total > 0 && label !== "Closures served"
                      ? ` (${Math.round((value / feedCounts.total) * 100)}%)` : ""}
                  </strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
