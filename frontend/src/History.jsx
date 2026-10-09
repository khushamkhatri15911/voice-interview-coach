import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { API_URL, getClientId } from "./api";

const STATUS_TEXT = { too_short: "Too short", failed: "Not scored" };

export default function HistoryScreen({ onBack, onOpen }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/history?client_id=${getClientId()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`server answered ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((e) => {
        if (!cancelled) setError(`Could not load history (${e.message})`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const scored = useMemo(() => (items || []).filter((i) => i.status === "scored"), [items]);

  const chartData = scored.map((i, idx) => ({
    label: `#${idx + 1}`,
    Overall: i.overall_score,
    Clarity: i.clarity,
    Structure: i.structure,
    Specificity: i.specificity,
    "Technical depth": i.technical_depth,
  }));

  const average = scored.length
    ? (scored.reduce((sum, i) => sum + i.overall_score, 0) / scored.length).toFixed(1)
    : "-";
  const best = scored.length ? Math.max(...scored.map((i) => i.overall_score)) : "-";
  const change =
    scored.length >= 2
      ? scored[scored.length - 1].overall_score - scored[0].overall_score
      : null;

  return (
    <div className="card wide">
      <h1>Your progress</h1>

      {error && <p className="error">{error}</p>}
      {!items && !error && <p className="sub">Loading...</p>}

      {items && items.length === 0 && (
        <p className="sub">No interviews yet. Complete one and it will appear here.</p>
      )}

      {items && items.length > 0 && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="stat-value">{scored.length}</div>
              <div className="stat-label">Scored interviews</div>
            </div>
            <div className="stat">
              <div className="stat-value">{average}</div>
              <div className="stat-label">Average score</div>
            </div>
            <div className="stat">
              <div className="stat-value">{best}</div>
              <div className="stat-label">Best score</div>
            </div>
            <div className="stat">
              <div className="stat-value">
                {change === null ? "-" : change > 0 ? `+${change}` : change}
              </div>
              <div className="stat-label">Since first</div>
            </div>
          </div>

          {scored.length >= 2 ? (
            <div className="chart-wrap">
              <ResponsiveContainer>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#2a2e3b" strokeDasharray="3 3" />
                  <XAxis dataKey="label" stroke="#9aa0b4" />
                  <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} stroke="#9aa0b4" />
                  <Tooltip contentStyle={{ background: "#181b24", border: "1px solid #2a2e3b" }} />
                  <Legend />
                  <Line type="monotone" dataKey="Overall" stroke="#5b8cff" strokeWidth={3} />
                  <Line type="monotone" dataKey="Clarity" stroke="#2fbf71" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="Structure" stroke="#e0b43a" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="Specificity" stroke="#d6455d" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="Technical depth" stroke="#b37bff" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="sub">Complete 2 scored interviews to see your progress chart.</p>
          )}

          <h2>Past interviews</h2>
          {[...items].reverse().map((i) => {
            const date = new Date(i.created_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            });
            const isScored = i.status === "scored";
            return (
              <button
                key={i.room_name}
                className="hrow"
                disabled={!isScored}
                onClick={() => onOpen(i.room_name)}
              >
                <span>
                  <b>{i.role}</b>
                  <br />
                  <small>
                    {date} · {i.interview_type}
                  </small>
                </span>
                <span className="badge">
                  {isScored ? `${i.overall_score}/10` : STATUS_TEXT[i.status] || i.status}
                </span>
              </button>
            );
          })}
        </>
      )}

      <button className="primary" onClick={onBack}>
        Back
      </button>
    </div>
  );
}