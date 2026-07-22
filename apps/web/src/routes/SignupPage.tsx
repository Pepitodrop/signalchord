import React, {useMemo, useState} from "react";
import {SignalChordClient} from "@signalchord/api-client";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:3000";

export function SignupPage() {
  const client = useMemo(() => new SignalChordClient(API_URL), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [betaAccessCode, setBetaAccessCode] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await client.signup(email, password, betaAccessCode);
      setSubmitted(true);
    } catch {
      setError("Sign-up failed. Check your beta access code and try again.");
    }
  };

  if (submitted) {
    return (
      <main className="login">
        <div className="card loginCard">
          <span className="logo">SC</span>
          <h1>Check your email</h1>
          <p className="muted">We sent a verification link to {email}. Click it to finish setting up your account.</p>
          <a href="/login">Back to sign in</a>
        </div>
      </main>
    );
  }

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <p className="eyebrow">SignalChord closed beta</p>
        <h1>Create your account.</h1>
        <label>
          Email
          <input
            value={email}
            onChange={event => setEmail(event.target.value)}
            type="email"
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={event => setPassword(event.target.value)}
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <label>
          Beta access code
          <input
            value={betaAccessCode}
            onChange={event => setBetaAccessCode(event.target.value)}
            autoComplete="off"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">Sign up</button>
        <a href="/login">Already have an account? Sign in</a>
      </form>
    </main>
  );
}
