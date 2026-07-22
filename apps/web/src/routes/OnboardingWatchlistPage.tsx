import React, {useState} from "react";
import {SignalChordClient} from "@signalchord/api-client";

export function OnboardingWatchlistPage({client, onCreated}: {client: SignalChordClient; onCreated: () => void}) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await client.createWatchlist({name, items: []});
      onCreated();
    } catch {
      setError("Couldn't create your watchlist. Try again.");
    }
  };

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <h1>Add your first watchlist.</h1>
        <p className="muted">Track an entity, topic, or search term. You can add more later.</p>
        <label>
          Watchlist name
          <input value={name} onChange={event => setName(event.target.value)} placeholder="Competitor moves" required/>
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">Create watchlist</button>
      </form>
    </main>
  );
}
