// A Server Component: this runs on the Next.js server, never in the browser.
// The browser receives finished HTML, so it never talks to FastAPI directly.

async function getApiStatus(): Promise<string> {
  try {
    // API_URL has no NEXT_PUBLIC_ prefix, so it is only readable on the server.
    const res = await fetch(`${process.env.API_URL}/health`);
    if (!res.ok) return `error ${res.status}`;
    const body: { status: string } = await res.json();
    return body.status;
  } catch {
    return "unreachable";
  }
}

export default async function Home() {
  const status = await getApiStatus();

  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-2xl font-semibold">Canyon State</h1>
      <p className="mt-4">
        API: <span className={status === "ok" ? "text-green-700" : "text-red-700"}>{status}</span>
      </p>
      <p className="mt-2 text-sm text-zinc-500">Rendered on the server at {new Date().toLocaleTimeString()}</p>
    </main>
  );
}
