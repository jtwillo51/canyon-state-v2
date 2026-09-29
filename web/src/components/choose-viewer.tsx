/** Shown in place of a page's data until someone is chosen in "View as". */
export function ChooseViewer() {
  return (
    <p className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
      Choose a person in <strong>View as</strong> (top right) to see their data.
    </p>
  );
}
