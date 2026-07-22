import React, {useState} from "react";
import {SignalChordApiError, SignalChordClient} from "@signalchord/api-client";

export function LoginPage({client, onWorkspaceRequired, onAuthenticated}: {
  client: SignalChordClient;
  onWorkspaceRequired: (email: string, password: string) => void;
  onAuthenticated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const result = await client.webLogin(email, password);
      if (result.status === "workspace_required") onWorkspaceRequired(email, password);
      else onAuthenticated();
    } catch (thrown) {
      const message = thrown instanceof SignalChordApiError && thrown.status === 403
        ? "Verify your email before signing in. Check your inbox for the verification link."
        : "Sign-in failed. Check your email and password.";
      setError(message);
    }
  };

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <p className="eyebrow">SignalChord v1.0</p>
        <h1>Connected news intelligence.</h1>
        <p className="muted">Evidence-first monitoring for analysts.</p>
        <label>
          Email
          <input
            value={email}
            onChange={event => setEmail(event.target.value)}
            type="email"
            autoComplete="username"
            placeholder="analyst@signalchord.local"
            required
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={event => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">Sign in</button>
        <a href="/signup">Need an account? Sign up</a>
      </form>
    </main>
  );
}
