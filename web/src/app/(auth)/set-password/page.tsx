import type { Metadata } from "next";

import { SetPasswordForm } from "./set-password-form";

export const metadata: Metadata = { title: "Set your password", referrer: "no-referrer" };

// The one-time token is in the link's #fragment, which browsers never send to any server: it stays out of
// server logs, proxies and Referer headers. The form below reads it in the browser.
export default function SetPasswordPage() {
  return <SetPasswordForm />;
}
