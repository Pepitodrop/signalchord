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

// Polls until exactly `count` messages have been sent to `email` with a
// subject containing `subjectIncludes`, then returns — used to assert "one
// notification per qualifying alert" without a race against Mailpit's own
// delivery/indexing latency. Throws if the count is exceeded (a duplicate
// send) or never reached within the timeout.
export async function waitForMessageCount(
  email: string,
  subjectIncludes: string,
  count: number,
  {timeoutMs = 10_000, intervalMs = 500} = {},
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const matched = await countMatchingMessages(email, subjectIncludes);
    if (matched === count) return;
    if (matched > count) throw new Error(`expected ${count} message(s) to ${email}, found ${matched} (possible duplicate send)`);
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  throw new Error(`expected ${count} message(s) to ${email} matching "${subjectIncludes}" within ${timeoutMs}ms, condition never met`);
}

async function countMatchingMessages(email: string, subjectIncludes: string): Promise<number> {
  const search = await fetch(`${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${email} subject:"${subjectIncludes}"`)}`);
  if (!search.ok) return 0;
  const {messages} = (await search.json()) as MailpitSearchResponse;
  return messages.length;
}
