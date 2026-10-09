import { useEffect, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
} from "@livekit/components-react";
import "@livekit/components-styles";

const API_URL = "http://localhost:8000";

const INTERVIEW_TYPES = [
  { value: "behavioural", label: "Behavioural" },
  { value: "technical", label: "Technical" },
  { value: "mixed", label: "Mixed" },
];

export default function App() {
  const [role, setRole] = useState("Junior Data Analyst");
  const [interviewType, setInterviewType] = useState("behavioural");
  const [connection, setConnection] = useState(null);
  const [roomName, setRoomName] = useState(null);
  const [phase, setPhase] = useState("setup"); // setup | live | scoring
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startInterview() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, interview_type: interviewType }),
      });
      if (!res.ok) throw new Error(`server answered ${res.status}`);
      const data = await res.json();
      setConnection({ serverUrl: data.serverUrl, token: data.participantToken });
      setRoomName(data.roomName);
      setPhase("live");
    } catch (e) {
      setError(`Could not start the interview. Is the FastAPI server running? (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  function endInterview() {
    setPhase((p) => (p === "live" ? "scoring" : p));
    setConnection(null);
  }

  function restart() {
    setRoomName(null);
    setPhase("setup");
  }

  if (phase === "scoring") {
    return <ScoringScreen roomName={roomName} onRestart={restart} />;
  }

  if (phase === "setup") {
    return (
      <div className="card narrow">
        <h1>Voice Interview Coach</h1>
        <p className="sub">Practice a real spoken interview and get scored feedback.</p>

        <label htmlFor="role">Job role</label>
        <input
          id="role"
          type="text"
          value={role}
          maxLength={60}
          onChange={(e) => setRole(e.target.value)}
        />

        <label>Interview type</label>
        <div className="types">
          {INTERVIEW_TYPES.map((t) => (
            <button
              key={t.value}
              className={interviewType === t.value ? "active" : ""}
              onClick={() => setInterviewType(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <button className="primary" onClick={startInterview} disabled={loading || !role.trim()}>
          {loading ? "Starting..." : "Start interview"}
        </button>
        {error && <p className="error">{error}</p>}
        <p className="tip">Use headphones so the interviewer doesn't hear itself.</p>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={connection.serverUrl}
      token={connection.token}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={endInterview}
    >
      <InterviewScreen role={role} interviewType={interviewType} onEnd={endInterview} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

const STATUS_LABELS = {
  connecting: "Connecting...",
  initializing: "Alex is getting ready...",
  listening: "Listening to you",
  thinking: "Thinking...",
  speaking: "Alex is speaking",
  disconnected: "Disconnected",
};

function InterviewScreen({ role, interviewType, onEnd }) {
  const { state } = useVoiceAssistant();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();

  return (
    <div className="card narrow">
      <h1>Interview in progress</h1>
      <p className="meta">
        {role} · {interviewType}
      </p>

      <div className={`orb ${state}`} />
      <div className="status">{STATUS_LABELS[state] || state}</div>

      <button
        className="secondary"
        onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
      >
        {isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}
      </button>
      <button className="danger" onClick={onEnd}>
        End interview
      </button>
    </div>
  );
}

function ScoringScreen({ roomName, onRestart }) {
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

  if (report) return <ReportView report={report} onRestart={onRestart} />;

  if (error) {
    return (
      <div className="card narrow">
        <h1>No report</h1>
        <p className="sub">{error}</p>
        <button className="primary" onClick={onRestart}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="card narrow">
      <h1>Scoring your interview</h1>
      <div className="orb thinking" />
      <p className="sub">This usually takes 10 to 20 seconds...</p>
    </div>
  );
}

function ReportView({ report, onRestart }) {
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

      <button className="primary" onClick={onRestart}>
        Practice again
      </button>
    </div>
  );
}