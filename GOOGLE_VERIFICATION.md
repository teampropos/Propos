# Google OAuth Verification — Submission Prep

Scope requested: `https://www.googleapis.com/auth/business.manage`
Classification: **Sensitive** (confirmed via Google's docs — not Restricted,
so no CASA security assessment or annual re-audit required). Typical review
time: 3–5 business days once submitted.

Only this one scope is requested anywhere in the codebase (`gbp/auth.py`) —
useful, since the form asks you to justify why a narrower scope isn't
sufficient, and the honest answer is there isn't a narrower one that covers
reading and replying to Business Profile reviews.

---

## Scope justification (paste into the verification form)

**Why Propos needs `business.manage`:**

Propos is a review-management tool for hospitality and retail businesses.
On connecting their Google Business Profile, Propos needs to:
1. Read new customer reviews as they're posted to the business's profile.
2. Post a reply to each review (either automatically for positive reviews,
   or after the business owner approves it in Propos's dashboard for
   sensitive/negative reviews).

`business.manage` is the only scope that grants read/reply access to
Business Profile reviews — there is no narrower Google-defined scope that
covers review management alone (the newer, more granular Business Profile
scopes cover things like business information and Q&A, not reviews). Propos
does not use this scope for anything beyond reading and replying to
reviews — it does not edit business hours, location data, photos, or any
other profile fields.

---

## Demo video — shot list

Record unlisted on YouTube, in English, screen + voice narration. Google
wants to see: the actual OAuth consent grant a user experiences, the
correct app name/client ID in the browser address bar during that grant,
and the functionality the sensitive scope unlocks.

1. **Start on the Propos onboarding/portal screen**, logged in as a test
   business account. Say what you're about to do: "This is Propos, a
   review-reply tool. I'm going to connect a Google Business Profile to
   show how the review permissions are used."
2. **Click "Connect Google Business Profile."** Let the browser redirect to
   Google's real consent screen.
3. **Pause on the consent screen** long enough for the video to clearly
   show: the Propos app name, and the URL bar showing
   `accounts.google.com` with the correct client ID / Propos branding.
   Narrate: "This is Google's consent screen. The user is granting Propos
   access to manage their Business Profile so it can read and reply to
   reviews."
4. **Approve the consent.** Get redirected back into the Propos portal.
5. **Show a real (or seeded test) review appearing** in the Propos
   dashboard's review list — this demonstrates the read side of the scope.
6. **Show Propos posting/approving a reply** to that review — either an
   auto-posted positive reply or manually approving a held one — then
   (ideally) flip to the actual Google Business Profile / Google Maps
   listing and show the reply live there. This demonstrates the write side
   of the scope.
7. **Close with a one-line summary**: "That's the full extent of what
   Propos does with the business.manage scope — reading and replying to
   reviews on the business's behalf."

Keep it under ~3 minutes. No editing needed — a single unbroken screen
recording is fine and often preferred by reviewers since it's harder to
fake.

---

## Other fields the form will ask for (have ready before starting)

- App name, logo, developer contact email — already set on the OAuth
  consent screen, just confirm they're current.
- Home page URL: `https://getpropos.com`
- Privacy policy URL: `https://getpropos.com/privacy-policy` (same domain
  as home page — required)
- Up to 3 links to feature documentation — we don't have public docs, so
  either skip these or link to the relevant marketing pages
  (`getpropos.com`, `getpropos.com/pricing`) that describe the review-reply
  feature.

## RESOLVED (24 Sept 2026) — app is fully live, no submission needed

Turns out the whole scope-justification/video path wasn't actually the
blocker. Here's what actually happened, in order:

1. Clicked **Publish app** on the Audience page (project `propos-2026-494401`)
   to push from Testing to production. This is required before Google will
   even evaluate verification requirements.
2. That surfaced the real requirement: **Branding verification**, triggered
   by having an app logo while in production (Branding page → Verification
   status → "Verify branding"). The `Data access` scopes table in the
   console never actually mattered — it turned out `business.manage` isn't
   currently classified as a sensitive/restricted scope in Google's live
   system at all, despite older third-party docs saying otherwise.
3. Branding verification failed once because `getpropos.com` wasn't
   verified as owned by `team@trypropos.com` (the account running this
   Cloud project) in Google Search Console — a *different* account,
   `team@getpropos.com`, had verified it previously under a stale session.
4. Fixed by verifying `getpropos.com` fresh under `team@trypropos.com` via
   Search Console, using the HTML-file method (uploaded
   `google11077215da4d4085.html` to the Next.js `public/` folder — note:
   this app does NOT serve new `public/` files without a rebuild+restart,
   contrary to typical Next.js behavior, so a full `npm run build` + `pm2
   restart` was needed even for that static file to go live).
5. Re-ran branding verification → passed → clicked **Publish branding**.

End state: `Verification centre` shows both **Branding status: verified,
shown to users** and **Data access status: not required**. No pending
review, no manual submission, nothing waiting on Google. Any real Google
account can now connect via OAuth without hitting the test-user
restriction or the "unverified app" warning screen.

The demo video (`https://youtu.be/FUA8uUcTBAU`) and the scope-justification
text below were prepared in case a manual sensitive-scope review was ever
needed, but as it turned out, that path was never actually required here.
Kept below for reference in case scope classification changes in future.

## Status (superseded — kept for history)
Checked the Branding page in Google Auth Platform (project `propos-2026-494401`):
- App name (Propos) and support email (team@trypropos.com) — already set.
- Home page, privacy policy link, and Terms of Service link — were all
  empty. Filled in and saved: `https://getpropos.com`,
  `https://getpropos.com/privacy-policy`, `https://getpropos.com/terms`.
- Authorised domain — already had `getpropos.com`.
- **App logo — uploaded and saved.** Cropped the icon mark (bar + ring +
  green accent) out of `~/Propos/propos-logo.svg` — the full wordmark was
  too wide for Google's square requirement — rendered it to a 627x627 PNG
  on a white background and uploaded it. Visible on the Branding page now.

All required Branding fields are filled in: app name, support email, logo,
home page, privacy policy link, ToS link, authorised domain.

Next steps: record the demo video per the shot list above, then submit for
verification from the Verification Centre page in Google Auth Platform
(project `propos-2026-494401`).
