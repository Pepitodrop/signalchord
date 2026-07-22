import React, {useEffect, useMemo, useState} from "react";
import {SignalChordClient} from "@signalchord/api-client";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:3000";

type Status = "verifying" | "success" | "error";

export function VerifyEmailPage() {
  const client = useMemo(() => new SignalChordClient(API_URL), []);
  const [status, setStatus] = useState<Status>("verifying");
  const [resendEmail, setResendEmail] = useState("");
  const [resendSent, setResendSent] = useState(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setStatus("error");
      return;
    }
    client.verifyEmail(token).then(() => setStatus("success")).catch(() => setStatus("error"));
  }, [client]);

  const resend = async (event: React.FormEvent) => {
    event.preventDefault();
    await client.resendVerification(resendEmail);
    setResendSent(true);
  };

  return (
    <main className="login">
      <div className="card loginCard">
        <span className="logo">SC</span>
        {status === "verifying" && <p className="muted">Verifying your email…</p>}
        {status === "success" && (
          <>
            <h1>Email verified</h1>
            <p className="muted">You're all set.</p>
            <a href="/login">Continue to sign in</a>
          </>
        )}
        {status === "error" && (
          <>
            <h1>That link didn't work</h1>
            <p className="muted">It may have expired or already been used. Request a new one below.</p>
            {resendSent ? (
              <p className="muted">If an account with that email exists and needs verification, we've sent a new link.</p>
            ) : (
              <form onSubmit={resend}>
                <label>
                  Email
                  <input value={resendEmail} onChange={event => setResendEmail(event.target.value)} type="email" required/>
                </label>
                <button className="primary">Resend verification email</button>
              </form>
            )}
          </>
        )}
      </div>
    </main>
  );
}
