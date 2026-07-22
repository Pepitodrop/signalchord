import React, {useState} from "react";
import {SignalChordApiError, SignalChordClient} from "@signalchord/api-client";

export function OnboardingWorkspacePage({client, email, password, onCreated, onBackToLogin}: {
  client: SignalChordClient;
  email: string;
  password: string;
  onCreated: () => void;
  onBackToLogin: () => void;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await client.createOrganization(email, password, name);
      onCreated();
    } catch (thrown) {
      if (thrown instanceof SignalChordApiError && thrown.status === 401) {
        onBackToLogin();
        return;
      }
      setError("Couldn't create your workspace. Try a different name.");
    }
  };

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <h1>Name your workspace.</h1>
        <p className="muted">You'll be the owner — you can invite teammates later.</p>
        <label>
          Workspace name
          <input value={name} onChange={event => setName(event.target.value)} placeholder="Acme Research" required/>
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">Create workspace</button>
      </form>
    </main>
  );
}
