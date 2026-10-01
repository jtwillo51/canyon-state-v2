import { Logo } from "@/components/logo";
import { NotFoundCard } from "@/components/not-found-card";

// An address that matches no route. It renders outside the app shell (only the root layout), so it brings its
// own header, like the sign-in pages, and loads nothing that needs a viewer.
export default function NotFound() {
  return (
    <>
      <header className="bg-brand">
        <div className="mx-auto flex max-w-app px-4">
          <Logo />
        </div>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 py-16">
        <NotFoundCard />
      </main>
    </>
  );
}
