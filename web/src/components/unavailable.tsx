/** In place of one section whose data didn't load, so the rest of the page still works. */
export function Unavailable({ what }: { what: string }) {
  return (
    <p role="status" className="rounded-md border border-dashed px-4 py-3 text-sm text-muted-foreground">
      Couldn&apos;t load {what} just now. Refresh the page to try again.
    </p>
  );
}
