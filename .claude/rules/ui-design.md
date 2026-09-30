---
paths:
  - "web/src/**/*.tsx"
  - "web/src/app/globals.css"
---

# UI design ("A3 copper")

Arizona's flag colors. The tokens are in `globals.css` and usable as Tailwind classes:

| Token | Use |
|---|---|
| `brand` (#0b2349), `brand-deep`, `brand-line`, `brand-mute` | Header, scoreboard, primary buttons; dividers and muted text on blue |
| `copper`, `copper-soft` (on dark), `copper-wash`, `copper-ink` | **Only** things measured against a goal: the active tab, goal meters (`GoalMeter`), the chosen comparison |
| `link` | Record links in tables |
| `up` / `down` (+ `-soft` on dark) | ▲ better / ▼ worse |
| shadcn's `primary`, `muted`, `border`, … | Everything else; `primary` is flag blue |

- **Copper has one meaning.** Don't use it for decoration, buttons or selection that isn't about a goal.
  Holding it to one job is what lets it carry meaning. Warnings ("do not discuss") stay amber.
- **Numbers are IBM Plex Mono** (`font-mono`, which also sets tabular figures). DataGrid does this for
  right-aligned columns automatically. Words are IBM Plex Sans.
- Radius is small (`--radius` 0.375rem). Cards are white (`bg-card`) on the warm paper background.
- Headers on the blue band use `text-brand-mute` for secondary text, never `text-muted-foreground`.
- Light mode only for now; dark mode is an open decision.
- Don't add a control that does nothing yet (the header search waits for the command palette).
- Give interactive or measured things accessible names (`aria-label`, `role="group"`): screen readers need
  them, and the e2e tests find elements by them.
