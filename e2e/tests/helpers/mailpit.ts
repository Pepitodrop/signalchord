const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025";

interface MailpitMessageSummary {
  ID: string;
}

interface MailpitSearchResponse {
  messages: MailpitMessageSummary[];
}

interface MailpitMessage {
  Text: string;
}

// Polls Mailpit's HTTP API (the local dev SMTP catcher, see docker-compose.yml)
// for the most recent verification email sent to `email`, and extracts the
// /verify-email?token=... link from its plain-text body.
export async function waitForVerificationLink(
  email: string,
  {timeoutMs = 10_000, intervalMs = 500} = {},
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const link = await tryFetchVerificationLink(email);
    if (link) return link;
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  throw new Error(`No verification email found for ${email} within ${timeoutMs}ms`);
}

async function tryFetchVerificationLink(email: string): Promise<string | null> {
  const search = await fetch(`${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`);
  if (!search.ok) return null;

  const {messages} = (await search.json()) as MailpitSearchResponse;
  const latest = messages[0];
  if (!latest) return null;

  const messageResponse = await fetch(`${MAILPIT_URL}/api/v1/message/${latest.ID}`);
  if (!messageResponse.ok) return null;

  const message = (await messageResponse.json()) as MailpitMessage;
  const match = message.Text.match(/https?:\/\/\S+\/verify-email\?token=\S+/);
  return match ? match[0] : null;
}

export async function clearMailpit(): Promise<void> {
  await fetch(`${MAILPIT_URL}/api/v1/messages`, {method: "DELETE"});
}
