import { Logo } from "@/components/logo";

// Signing in and setting a password: no header, no data, nothing that needs a session.
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="bg-brand">
        <div className="mx-auto flex max-w-app px-4">
          <Logo href="/sign-in" />
        </div>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 py-16">
        <div className="w-full max-w-sm rounded-md border bg-card p-6 shadow-xs">{children}</div>
      </main>
    </>
  );
}
