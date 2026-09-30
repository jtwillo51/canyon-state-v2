# Deploying the public demo

Three free services: **Neon** (Postgres), **Render** (the FastAPI API) and **Vercel** (the Next.js app).
The demo runs in `DEMO_MODE`: a "View as" switcher alongside sign-in, a banner saying the data is
fictional, and a nightly reseed that undoes whatever visitors change.

> **Synthetic data only.** In demo mode anyone can act as anyone through "View as" (that's the point of the
> demo). Never point it at a database that holds the agency's real data.

Order matters: the database first (and seeded), then the API, then the web app.

## 1. Database: Neon

1. Sign up at neon.tech and create a project (e.g. `canyon-state-demo`, region US West).
2. Copy the **direct** connection string (turn "Connection pooling" off in the connect dialog). It looks
   like `postgresql://user:password@ep-something.us-west-2.aws.neon.tech/neondb?sslmode=require`.
   The API converts this format itself; paste it as-is.

## 2. Load the demo data (GitHub Actions)

Store the connection string as a repository secret (the command prompts for the value, so it never
lands in your shell history):

```bash
gh secret set DEMO_DATABASE_URL --repo jtwillo51/canyon-state-v2
```

Then run the **Reseed demo** workflow once by hand (Actions tab → Reseed demo → Run workflow), or:

```bash
gh workflow run reseed-demo.yml --repo jtwillo51/canyon-state-v2
```

It migrates the database, loads the synthetic seed, and runs the jobs once (so there are notifications to show).
From then on it runs nightly at 3 am Arizona time.

## 3. API: Render

1. Sign up at render.com with GitHub and allow access to `canyon-state-v2`.
2. **New → Blueprint**, pick the repo. Render reads `render.yaml`.
3. When asked for `DATABASE_URL`, paste the Neon connection string. Deploy.
4. Check `https://<your-service>.onrender.com/health` returns `{"status":"ok","database":"ok"}`.

The free plan sleeps after 15 idle minutes; the next request takes about a minute to wake it. To keep it awake
during working hours, set the repository variable (not a secret; the address is public anyway):

```bash
gh variable set DEMO_API_URL --repo jtwillo51/canyon-state-v2 --body https://<your-service>.onrender.com
```

The **Keep demo warm** workflow then pings it every 10 minutes, 7 am to 7 pm Arizona time on weekdays.
Outside those hours, open the link yourself a minute before sending it.

## 4. Web: Vercel

1. Sign up at vercel.com with GitHub and import `canyon-state-v2`.
2. Set **Root Directory** to `web`. The framework (Next.js) is detected.
3. Environment variables:
   - `API_URL` = your Render URL, e.g. `https://canyon-state-api.onrender.com` (no trailing slash)
   - `DEMO_MODE` = `true`
4. Deploy, open the URL, and pick someone in **View as**.

## Updating

Pushing to `main` redeploys both: Render re-runs the build (including migrations) and Vercel rebuilds
the web app. After an API change, regenerate the web types locally (`npm run gen:api` in `web/`) and commit
`schema.d.ts` with it.

## A real deployment (not the demo)

Real sign-in is the only way in when neither `DEV_AUTH` nor `DEMO_MODE` is set: leave both unset, and the "View as"
header and its user list simply don't exist.

1. Deploy the API and web app as above, without `DEMO_MODE` and without running the seed.
2. From the API server's shell, create the first admin and get their one-time link:
   `uv run python -m scripts.make_link dana@agency.example --name "Dana Whitfield" --site https://your-web-app`
3. They open the link, choose a password, and add everyone else from the **Team** page.

The web app must be served over HTTPS in production: the session cookie is `__Host-`-prefixed, which browsers
only accept on secure origins.
