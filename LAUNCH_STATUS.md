# Propos — Launch Status Debrief

**Last updated:** 22 September 2026

This is a snapshot of exactly where the product stands, written so a new
session (Claude Code, Codex, or a human) can pick up from here without
re-deriving anything. If you're reading this because a terminal crashed —
nothing is lost. Everything described below is committed to GitHub and/or
already running in production.

**Database backups (22 Sept 2026):** production had zero backup strategy —
a droplet failure or bad migration would have meant permanent loss of every
client's data. Fixed: nightly `pg_dump` via `scripts/backup_db.sh`, kept
locally (14 days) and uploaded to a DigitalOcean Spaces bucket
(`propos-backups`, sgp1 region, 90-day retention) so it survives losing the
droplet entirely. Cron runs it at 3am Sydney time. Verified for real, not
just deployed: ran it manually, confirmed the file landed in both places,
and test-restored the dump into a throwaway database to confirm it's
actually valid. Spaces access keys live only in
`/root/.config/rclone/rclone.conf` on the droplet — not in git.

**Pre-launch audit (22 Sept 2026):** did a full click-through of the live
site and portal before submitting to Google for OAuth verification, since a
reviewer will actually look at this. Found and fixed one significant bug:
every primary CTA on the site ("Get started" in the nav, "Automate my
reviews" on the hero and final CTA section, and the login page's signup
link) was pointing at the old `/coming-soon` waitlist page instead of the
real `/get-started` checkout flow — only the pricing page's own buttons
linked correctly. That meant a visitor clicking the main call-to-action
almost anywhere on the site couldn't actually sign up. Fixed and deployed.
Also fixed: Privacy Policy and Terms both described a "magic link" email
approval flow that was never built (the real product holds negative
reviews in the portal instead), the footer's copyright year was hardcoded
to 2025, and a Preferences page bug where an unrecognized tone value left
the sample-reply box rendering empty. All fixed, deployed, committed,
pushed. See the "Other gaps" section below for what's still open.

**New feature (23 Sept 2026): connect-before-pay signup.** Account creation
is now decoupled from payment — `POST /api/auth/register` creates an
account with no Stripe involvement, so a prospective client can connect
their real Google Business Profile and see actual reviews with draft
replies in their portal before ever entering a card. Subscribing is a
separate, later step (`POST /api/checkout`, now authenticated) that
activates the same account via `client_reference_id` on the Stripe
session — the webhook updates the existing account rather than creating a
new one. Critically: nothing ever posts to a client's live Google listing
until `Client.is_subscribed` is true (checked in the auto-post loop, the
scheduled-post sweep, and the manual approve endpoint) — unpaid accounts
only ever see drafts, never live posts. `/get-started` now registers
instead of checking out; `/onboarding` reorders to Connect Google → tone/
cadence → name → Subscribe → backlog. Verified end-to-end against a real
account on production (register → connect → checkout session created,
correctly tied to that account) before deploying; test data cleaned up
after. Deployed, committed, pushed.

Bonus: this also fixes the Google OAuth demo-video blocker — the real
Connect Google flow is now reachable for free, right after registering,
with no Stripe step in the way. See `GOOGLE_VERIFICATION.md`.

**New feature (22 Sept 2026): reply cadence.** Clients can now choose how
long Propos waits before actually posting an auto-approved reply to
Google — instantly, within 24 hours, within 3–4 days, weekly, or monthly.
Set during onboarding (folded into the existing tone step) or changed
later in Preferences. Only affects the auto-post path for positive
reviews — negative/needs_human reviews always wait for the client's own
portal approval regardless of this setting. Implementation: `app/cadence.py`
computes the target post time; `scripts/poll_reviews.py` schedules rather
than immediately posts (unless cadence is INSTANT), and each 10-minute
poll cycle also checks for anything that's come due and posts it then.
Reviews awaiting their cadence window show a new "Scheduled" status in the
portal. Deployed, committed, pushed.

---

## The repos (there are three directories — only two are real)

- **`~/Propos/`** → GitHub `teampropos/Propos` — the real Flask backend.
- **`~/propos-website/`** → GitHub `teampropos/propos-website` — the real
  Next.js frontend (marketing site + client portal, at `/app/portal/`).
- **`~/Desktop/propos/`** → **stale, abandoned duplicate.** Do not use it.
  It hasn't been touched since before the backend was built and does not
  match production. It caused real confusion earlier in this project's
  history — if a future session starts working here by mistake, stop and
  redirect to the two repos above.

Both real repos are pushed to `main` and match what's deployed. Nothing is
sitting uncommitted.

---

## Production infrastructure

- **Server:** DigitalOcean droplet, Ubuntu 24.04, IP `134.199.152.252`
  (Sydney region), reached via SSH key at `~/.ssh/id_ed25519` on this Mac.
- **Frontend:** `getpropos.com` and `www.getpropos.com` → Next.js at
  `/var/www/propos`, run via **PM2** (process name `propos`), reverse-proxied
  by nginx (`/etc/nginx/sites-available/propos`), SSL via Certbot.
- **Backend:** `api.getpropos.com` → Flask at `/var/www/propos-api`, run via
  **gunicorn under systemd** (`propos-api.service`, 3 workers, port 5001
  locally), reverse-proxied by nginx (`/etc/nginx/sites-available/propos-api`),
  SSL via Certbot. Auto-restarts on crash and on boot.
- **Database:** PostgreSQL 16 on the same droplet. Database `propos`, owned
  by a dedicated non-superuser role `propos_app` (not the `postgres` user).
  Schema is current — the latest Alembic migration
  (`610dd02d0882_add_gbp_review_path_and_stripe_`) has been applied in
  production.
- **Swap:** the droplet had ~1GB RAM and **zero swap** — genuinely at risk of
  the OOM killer taking down the live site under any load. Added a 2GB
  swapfile (persisted in `/etc/fstab`). There's also a pending kernel upgrade
  on the droplet that wants a reboot — not urgent, just needs a quiet moment.
- **Cron** (droplet, `TZ=Australia/Sydney` in the crontab):
  - `*/10 * * * *` — `scripts/poll_reviews.py` (pulls new Google reviews)
  - Mondays 8am — `scripts/send_weekly_digest.py`
  - 1st of month, 8am — `scripts/send_monthly_report.py`
  - Logs land in `/var/log/propos/`.

**Production secrets** live only in `/var/www/propos-api/.env` on the
droplet itself (gitignored, never committed, and deliberately not copied
into this file either). If the droplet is ever rebuilt, those values need
to be reconstructed — ask Claude to pull them back up from this session's
history, or regenerate fresh ones (Stripe price IDs, Resend key, and the
Google OAuth client credentials in particular).

---

## What's live and working right now

- **Full visual redesign** — shipped across the whole site (marketing +
  portal). Ink/navy palette, Hanken Grotesk + Fraunces, hairline-grid
  layouts, no decorative scroll animation. Replaced the previous
  generic-blue/DM-Sans look.
- **Pricing** — flat **$12 AUD/month**, plus **$6/month per additional
  location**. The old founder-tier/standard split is fully removed from the
  UI and checkout logic. (The `founder_tier` column and `founder_counter`
  table still exist in the DB, unused — harmless, just not cleaned up.)
- **Stripe** — live mode, real Price IDs created for both the base plan and
  the additional-location add-on, mirrored in the sandbox account too for
  safe local testing. Live webhook endpoint points at
  `https://api.getpropos.com/webhooks/stripe` and listens for all four
  events the handler needs (`checkout.session.completed`,
  `invoice.payment_failed`, `customer.subscription.deleted`,
  `customer.subscription.updated`).
- **Google Business Profile integration** — real, multi-tenant, live.
  - `gbp/` module handles per-client OAuth (web flow, PKCE), account/location
    discovery, and review read/reply.
  - Uses raw REST calls, not `googleapiclient.discovery.build()` — Google
    pulled the legacy `mybusiness` v4 discovery document from its public
    directory entirely, so the usual client-library approach doesn't work.
    Account/location lookups live on `mybusinessaccountmanagement` and
    `mybusinessbusinessinformation`; reviews only exist on the legacy
    `mybusiness` v4 host. This is documented in `gbp/auth.py`.
  - On connect, the client's primary GBP location is auto-discovered and
    saved so review polling has somewhere to pull from immediately.
  - **⚠️ See "Biggest remaining blocker" below — this works today only for
    allow-listed test users.**
- **Review pipeline** — `scripts/poll_reviews.py` pulls new reviews every 10
  minutes, runs them through the (untouched) reply engine, and either
  auto-posts via the Google API or leaves them in the portal's Pending
  Approvals queue, exactly matching the existing routing rules (positive →
  auto, negative/spam/low-confidence → held).
- **Email system** — all sent via Resend (domain `getpropos.com` verified):
  welcome (with account setup link), onboarding confirmation, weekly digest,
  monthly win report (includes a Claude call to extract up to 3 recurring
  themes from that month's reviews), failed payment, cancellation, and
  password reset. Verified with a real test send.
- **Location management** — clients can add/remove additional locations from
  the portal; each add/remove actually creates/deletes a Stripe subscription
  item, not just a UI toggle.
- **Onboarding wizard** — step 2 (Connect Google) now triggers the real
  OAuth flow instead of a "coming soon" placeholder, with a skip option.
- **Auth** — Flask-JWT-Extended + bcrypt (not NextAuth, despite what an old
  planning brief said). Login, password reset (backend), JWT sessions,
  protected `/portal/*` routes — all working.

---

## ✅ RESOLVED (24 Sept 2026): Google OAuth is fully live in production

This was flagged as the #1 launch blocker — it's now done. The app is
published (Audience → Publishing status: **In production**), branding is
verified and shown to users, and Google's Verification Centre confirms
`business.manage` doesn't require sensitive-scope review at all (contrary
to what older docs suggested). Any real Google account can now complete
the "Connect Google Business Profile" flow — no test-user allow-list
restriction, no "unverified app" warning screen. Full details and the
exact steps taken are in `GOOGLE_VERIFICATION.md`.

---

## Other gaps, roughly in priority order

1. **Backlog processing isn't built.** The onboarding wizard's last step
   still lets someone opt into paying for a review backlog, but nothing
   actually processes it server-side (`# TODO: trigger backlog processing if
   requested` is still sitting in `POST /api/onboarding/complete`).
2. **No password reset UI.** The backend endpoints and the reset email both
   work, but `/forgot-password` and `/reset-password` pages don't exist on
   the frontend yet — they're 404s. Login already links to `/forgot-password`.
3. **No Google reconnect handling.** If a client's refresh token ever fails
   (revoked access, expired grant), there's no detection for it and no
   "reconnect your Google account" email — it would just silently stop
   working for that client.
4. **Nothing has been through the full flow with real money.** Everything's
   been verified structurally (webhooks fire correctly, endpoints respond
   correctly, emails send correctly) but no actual human has paid, received
   the welcome email, set a password, connected Google, and had a real
   review come in and get replied to, start to finish, in production.
5. **No uptime/crash monitoring.** systemd restarts the Flask app if it
   dies and PM2 does the same for the frontend, but nothing external
   (UptimeRobot, etc.) would tell you if the whole droplet went down.
6. **`founder_tier` / `founder_counter` DB cleanup.** Unused now, harmless,
   but a small migration to drop them would tidy things up.
