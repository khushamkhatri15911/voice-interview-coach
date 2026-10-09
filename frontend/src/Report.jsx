import { useEffect, useState } from "react";
import { API_URL } from "./api";

export function ReportLoader({ roomName, onBack, backLabel, fresh }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      for (let tries = 0; tries < 60 && !cancelled; tries++) {
        try {
          const res = await fetch(`${API_URL}/report/${roomName}`);
          if (res.ok) {
            const data = await res.json();
            if (!cancelled) {
              if (data.error) setError(data.error);
              else setReport(data);
            }
            return;
          }
        } catch {
          // server hiccup, just try again
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (!cancelled) setError("The report is taking too long. Check the agent terminal.");
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [roomName]);

  if (report) return <ReportView report={report} onBack={onBack} backLabel={backLabel} />;

  if (error) {
    return (
      <div className="card narrow">
        <h1>No report</h1>
        <p className="sub">{error}</p>
        <button className="primary" onClick={onBack}>
          {backLabel}
        </button>
      </div>
    );
  }

  return (
    <div className="card narrow">
      <h1>{fresh ? "Scoring your interview" : "Loading report"}</h1>
      <div className="orb thinking" />
      {fresh && <p className="sub">This usually takes 10 to 20 seconds...</p>}
    </div>
  );
}

function ReportView({ report, onBack, backLabel }) {
  const scores = [
    ["Clarity", report.clarity],
    ["Structure", report.structure],
    ["Specificity", report.specificity],
    ["Technical depth", report.technical_depth],
  ];

  return (
    <div className="card wide">
      <h1>Your interview report</h1>
      <div className="overall">
        {report.overall_score}
        <span>/10</span>
      </div>

      {scores.map(([label, value]) => (
        <div className="bar-row" key={label}>
          <span className="bar-label">{label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${value * 10}%` }} />
          </div>
          <span className="bar-value">{value}</span>
        </div>
      ))}

      <h2>Strengths</h2>
      <ul>
        {report.strengths.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>

      <h2>To improve</h2>
      <ul>
        {report.weaknesses.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>

      <h2>Question by question</h2>
      {report.per_question.map((q, i) => (
        <div className="qcard" key={i}>
          <div className="qtitle">
            {q.question} <span className="qscore">{q.score}/10</span>
          </div>
          <p><b>Good:</b> {q.what_was_good}</p>
          <p><b>Improve:</b> {q.what_to_improve}</p>
          <p><b>Tip:</b> {q.better_answer_tip}</p>
        </div>
      ))}

      <h2>Next steps</h2>
      <ul>
        {report.next_steps.map((n, i) => (
          <li key={i}>{n}</li>
        ))}
      </ul>

      <button className="primary" onClick={onBack}>
        {backLabel}
      </button>
    </div>
  );
}