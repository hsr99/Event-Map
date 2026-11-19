# Chennai Events Map: About This Project

> Working title. A map-first discovery site for the Chennai events that big ticketing platforms ignore: open mics, workshops, college and community meets, pop-ups, small gigs.
>
> **Status:** idea validated on paper, nothing validated with real users yet. Everything marked *hypothesis* below is a bet to test, not a fact.

---

## 1. The idea in one paragraph

Most small events in Chennai live as a poster on one Instagram account or a WhatsApp forward. They are not on BookMyShow, District, or Insider, and they are hard to find unless you already follow the right accounts. This project turns those posters into structured events (using vision models), places them on a dark, glowing map of Chennai, and makes them filterable by type, area, and time. Organizers submit by uploading a poster or sending it to a bot; the pipeline does the typing.

**The one-line reason to come back (hypothesis):**
> *"Never miss the small stuff": the open mic, workshop or pop-up your friends will talk about on Monday that you'd otherwise never have seen.*

---

## 2. Why this might work, and why it might not

### Why
- Big platforms chase concerts, movies and IPL. District's FY26 revenue was reported at over ₹970 crore with continuing losses, and BookMyShow is described as holding around 70% of online movie ticketing. The long tail of small events is not their focus.
- Small organizers and cafés want footfall and already post posters everywhere; one more free place to be seen costs them little.
- A poster-to-event pipeline built on vision models is now cheap enough for one person to run.

### Why not (be honest)
- **Instagram is the real competitor.** People simply follow accounts. The map must be clearly better at *discovery*.
- **Cold start.** An empty-feeling map kills trust. Supply has to be seeded by hand.
- **Event discovery alone monetizes poorly.** One company-profile site (unverified) lists AllEvents at roughly $1.8M revenue against 20M+ monthly seekers. Expect small revenue early on; treat money in year one as a bonus.
- **Supply is ongoing work**, not a one-time build.
- Existing competitors: Luma's India community calendar, Loopin (city-by-city tech events, open source), ChennaiOrbit, dev.events, Meetup, AllEvents. Their Chennai depth for *non-tech, small* events is **unchecked**.

**Honest verdict:** very likely worth building as a portfolio project; plausible as a habit product; uncertain and probably small as a business. Build it as a time-boxed experiment with kill criteria (Section 9).

---

## 3. Audience and place

| Segment | Role | Notes |
|---|---|---|
| College students (~18-23) | Reach and word of mouth | High interest, low spend |
| Young professionals (~22-32), IT corridor | Core users; more spend | Pay for workshops, gigs, networking |
| Organizers, cafés, venues | **The paying side** | Want footfall; small organizers, college clubs, community groups first |

- National data (not Chennai-specific): over 70% of Gen Z and millennials in Tier 1 cities attended at least one ticketed show last year, but over 70% of a salaried Gen Z sample's spending goes to everyday needs. *Treat Chennai age data as a hypothesis until the survey runs.*
- **Where to start (hypothesis):** (1) OMR / IT corridor, (2) the Adyar-Besant Nagar-Mylapore-Alwarpet belt. The "Chennai this week" stats will show where events actually cluster.
- **Seasonal wedges:** Margazhi music season (the Tamil month starts 16 Dec 2026; some festivals start in November; existing schedule sites already exist, so the edge is a map with "tonight / free / near me") and college fest season (Jan-Feb). Margazhi skews older than the core audience, so treat it as a traffic spike, not the core.

---

## 4. Product

### Map concept
- Dark "city at night" base map; **glowing dots** coloured by category (circle layer plus blurred halo).
- Dots for events starting within ~3 hours pulse; started events fade; approximate locations are hollow.
- Filters: type chips, area dropdown, time chips (Now / Tonight / This weekend / Pick a date), "free only".
- Tap a dot: bottom sheet with title, time, venue, price, booking link, source link, add-to-calendar.
- City zoom clusters dots; a list view stays in sync with the visible map; mobile-first.
- Default view: "Tonight" if location is shared, else "This weekend". A stats strip: *"43 events this week · busiest: Adyar"*.
- Shareable URLs (filters in the URL), per-event pages, ICS calendar feeds for a filter.
- If under ~30 events, don't pad with fake density: zoom to clusters and show the list beside the map.

### Features by version
See Section 9. Highlights: poster upload, trust tiers, spam reports, venue directory, stats page, ICS feeds, Thursday digest, claim-your-listing, "Interested" counter, featured listings.

### "Interested" counter (crowd signal)
One-tap, no login, anonymous count per device per event, rate-limited. Show only above a threshold (e.g. 5+), plus "Popular this week" by relative rank. Label it **"interest on this site"**, not "expected crowd". Add venue capacity and an organizer "selling fast / sold out" flag. Needs a backend (V2).

---

## 5. Business model

**Who pays:** venues/cafés and organizers (for footfall), local brands and sponsors (for reach), not attendees.

| Order | Revenue | Notes |
|---|---|---|
| 1 | Free listing, build audience | Track views, clicks, interest from day one |
| 2 | Featured placement for small organizers/venues | Price after seeing click numbers; ask organizers, don't guess |
| 3 | Sponsored weekly digest | Local businesses near events |
| 4 | Organizer analytics (views, saves, registration clicks) | Subscription |
| 5 | Embeddable "events near this venue" widgets; B2B "what's on" feeds | Hotels, co-living, HR teams |
| 6 | Lightweight RSVP/ticketing for free/small events | Later; where the moat is, but needs payments and trust |

**Cost notes:** WhatsApp replies to users who message you were free within the 24-hour window as of the sources checked; outbound marketing broadcasts cost money per message (about ₹0.86 each in the Jan 2026 India rate seen). One provider guide claims billing changes from 1 Oct 2026, so **verify current Meta pricing** before budgeting. Prefer ICS/email/WhatsApp Channels for digests over paid broadcasts.

---

## 6. Architecture

```
SOURCES (ranked by reliability)
 1. Submissions   website form / WhatsApp bot (V2) / Telegram optional
                  (venue autocomplete + pin picker)
 2. Your feed     you share Instagram posts you found while browsing (manual)
 3. Safe crawl    httpx+BS4 first, Crawl4AI fallback; RSS/JSON-LD where present
 4. (Optional)    small Instaloader watchlist, throwaway account  [V3 experiment]
        |  image or text + source URL + post date
        v
CLOUD INBOX (free-tier DB + storage, always on)  ->  pending items
        v
WORKER (laptop batch, later a cheap VPS)
  hash -> exact duplicate? skip
  Gemini + Qwen: image -> strict JSON (+ is_event_poster, roles for handles)
  compare both models -> validate (date parses, future, fields present)
  -> venue match (directory) -> fuzzy dedupe -> trust-tier check
  -> publish | review queue | reject
        v
OUTPUTS: events.json (upcoming only) -> static MapLibre site (GitHub Pages)
         "Chennai this week" page, ICS feeds, Thursday digest
         report button -> reports table -> auto-hide -> admin review
         admin-only: organizer handles, strikes, audit log
```

### Key design decisions
- **Inbox and worker are separate:** uploads need an always-on endpoint; the laptop isn't always on. Uploads land in a free-tier cloud inbox; the worker processes whatever is waiting.
- **Direct image-to-JSON** (no separate OCR step). The two-model agreement (Gemini + Qwen) is the confidence signal: agree on date/time/venue -> publish; disagree -> review. Tesseract (`extract_poster.py`) stays only as a baseline in the 100-poster test.
- **Venue directory** seeded from OpenStreetMap (Overpass) plus manual additions. Each venue verified once, then trusted. Geocoding order: venue directory -> Nominatim restricted to Chennai (`countrycodes=in`, Chennai viewbox, bounded) -> area centroid marked "approximate" -> review queue.
- **Structured data first:** many event pages carry schema.org `Event` JSON-LD (Luma pages do), giving name, dates, venue and exact coordinates with no AI. Fall back to the LLM on page text, then to poster images.
- **Batch with retries** to cope with free-tier model quotas.
- Secrets in environment variables, never in the public repo.

### Extraction schema (strict JSON from the vision models)
```json
{
  "is_event_poster": true,
  "event_name": "Open Mic Night",
  "date": "2026-11-08",
  "date_end": null,
  "time": "19:00",
  "time_end": null,
  "venue": "The Hive Cafe",
  "area": "Besant Nagar",
  "ticket_price": "Rs 299",
  "booking_link": "bit.ly/example",
  "category": "comedy",
  "organizer_handle": "example_org",
  "venue_handle": "thehivecafe",
  "other_handles": [{"handle": "brandx", "role": "sponsor"}],
  "language": "en",
  "confidence": {"date": 0.9, "venue": 0.8}
}
```
Rules: return `null` for anything not on the poster (never guess); resolve missing years against the post date; a hallucinated value is worse than a missing one.

### Data model (SQLite)
`sources`, `posters` (hash, raw model outputs), `events` (fields, lat/lng, confidence, status: published / review / hidden / expired), `venues` (directory + verification state), `organizers` (admin-only; candidate / contacted / verified; consent; strikes), `reports`, `audit_log`, `submissions`.

### Source config (decide fetch method once per site)
```yaml
sources:
  - name: Luma event pages
    fetch: static
    extract: jsonld
  - name: FOSS United Chennai
    fetch: static
    extract: llm
  - name: eChai recurring meetups
    fetch: static
    purpose: organizer_directory
```
Default is **static first, Crawl4AI automatic fallback** if the page looks empty, with the method logged. Health checks: zero events from a normally productive source -> alert; very little text -> retry with browser.

---

## 7. Tooling decisions

| Tool | Decision | Why |
|---|---|---|
| httpx + BeautifulSoup | **Use** (default fetcher) | Fast; tests showed same content as the browser on tested sites |
| Crawl4AI | **Use** (JS pages / fallback) | Python-only, needs a browser install; heavier |
| Gemini + Qwen | **Use** for vision extraction | Run both, compare; validate on the 100-poster test |
| Tesseract / pytesseract | Baseline only | Weak on stylized posters |
| MapLibre + OSM tiles (+ Protomaps) | **Use** | Free, no backend needed for V1 |
| Nominatim | Use with cache and 1 req/s | Free; patchy for small venues, hence the venue directory |
| Google Geocoding/Places | Avoid for display data | Terms restrict caching and require Google maps for display |
| Instaloader | **Optional, V3**, throwaway account | Against Instagram's terms; anonymous access was blocked in testing; login hit a checkpoint |
| Browser agents (agent-browser, OpenCLI, Agent Reach) | **Not used** on Instagram/Google | Automating a logged-in session risks the account; adds no capability Crawl4AI lacks |
| Crawlee | Skip | Not needed at this scale |
| Firecrawl, Browser Use, instagrapi | Skip | Cost / risk / overkill |
| Instagram Graph API | Later, if approved | Gated: Meta app review, business verification, hashtag limits (30 per 7 days) |
| WhatsApp Business API | V2 | Official API only; avoid unofficial libraries |

---

## 8. Compliance, safety and trust

- **robots.txt first.** Skip disallowed URLs; read each site's terms before regular crawling. One-off tests are fine.
- **Instagram/Google:** automated access breaks their terms. Primary route is human-assisted (you share posts to your own intake). Instaloader is an optional, throwaway-account experiment, read-only, small, with a kill switch; nothing may depend on it. No detection-evasion tricks.
- **Copyright:** store extracted facts (title, date, venue, price), link back to the source, don't republish posters unless the organizer submitted them. Offer a visible takedown route.
- **Privacy:** store only organizer/venue handles (admin-only), with roles from the model, not mention counts. Anonymous interest counters. No personal data beyond what's needed. India's data protection law applies; get advice before building anything that profiles individuals.
- **Safety:** if a poster says "DM for location" or lists a private address, show the area only, not a pin.
- **Employment:** check your employment contract for outside-work/IP clauses before monetizing; build from scratch on public or anonymized data.

### Moderation (no approving every event)
1. **Pre-publish checks:** `is_event_poster`, date parses and is within ~120 days, duplicate check, blocklist (phones/URLs), per-submitter rate limit.
2. **Trust tiers:** *New* (auto-publish only if both models agree and validation passes, else review) -> *Verified organizer* (after a claim check or ~3 clean listings) -> *Trusted* (always publish; you see reports only).
3. **Reports:** report button on every listing; ~3 distinct reporters -> auto-hide pending review (not an instant ban); rate-limit reports; ignore bursts from brand-new anonymous sessions.
4. **Consequences:** confirmed spam = strike; 3 strikes = block; everything logged and reversible; simple appeal route.

### Venue verification (verify once per venue)
Checks: venue resolves to a real place in Chennai; area matches the poster; business status and opening hours (Places API, if used, store only your verdict and place ID); place type fits the event; review/rating sanity; web or Instagram presence. Output a score with reasons; **flag, don't reject** (new cafés, halls and pop-ups often have no reviews). A real venue doesn't make the event real: combine with organizer trust, a working booking link and a second source. Any LLM reading reviews or search results is read-only with no actions (untrusted text).

---

## 9. Plan

*Sized for ~8-10 hours a week alongside a full-time job; estimates are rough.*

### V1: Organizer-demo POC (about 2 weeks)
**Goal:** a working demo to show organizers.
- Static MapLibre site: glowing dots, filters, event cards, stats strip.
- 40-60 hand-verified real events, entered through your own extraction script (Gemini + Qwen).
- A local "drop a poster" page: poster in -> extracted event and preview card out (plus a recorded backup).
- Venue directory seeded from OSM; README with screenshots and architecture.
- In parallel: attendee survey and ~15 organizer DMs.
- **Not included:** accounts, moderation, backend, WhatsApp, crawling, Instagram automation.
- **Gate (suggested numbers):** 5 of 15 organizers reply, 3 send a poster/link, survey shows people miss events. Otherwise it stays on GitHub as a portfolio project.

### V2: Production-ready and hosted (about 5-6 weeks)
**Goal:** a product people can use daily.
- Hosting: static site (GitHub Pages or similar) + free-tier cloud inbox/API + worker on a schedule; domain, backups, privacy policy, terms, takedown contact.
- Submissions: website form with venue autocomplete and pin picker; **WhatsApp bot** (official API; Meta business verification takes time, so start early).
- Trust and safety: validation, two-model agreement, trust tiers, spam reports with auto-hide, admin review page, audit log.
- Growth: shareable event pages, ICS feeds, "Chennai this week" page, Thursday digest, "Interested" counter.
- Supply: a few safe crawls (static first), basic claim-your-listing.
- **Gate:** people return weekly; you review under ~20% of incoming posters.

### V3: Extended (ongoing)
- Optional Instaloader watchlist experiment (throwaway, read-only, kill switch); admin-only organizer-handle discovery with roles.
- Seasonal pages (Margazhi, college fests), featured listings, organizer analytics.
- More map layers: rent map, startup map, PGs. Natural-language search, Tamil support, embeddable widgets, RSVP.

### Decision at the end of each phase
Continue, pivot, or archive. Write the gate numbers down before starting so the call isn't made on vibes.

---

## 10. Validation plan

**Attendee survey** (Google Forms; ask behaviour first, the hypothetical last):
1. How often do you attend events in Chennai? 2. What kinds? 3. What was the last one and how did you hear about it? 4. Where do you look? 5. **In the last 3 months, did you miss an event because you found out too late or not at all?** (the key question) 6. How happy are you with how you find events? 7. Biggest frustration? 8. How likely would you use one map of everything? 9. What would matter most? 10. How do you want updates? 11. Area? 12. Optional contact for early access (the real "yes").

Add: "Do you organize or help run events?" and "Have you shared an event in a group chat?"

**Organizer DM (first message, one small ask):**
> Hi [name]! I'm building a free map of Chennai events, including community ones that only get posted on Instagram. Can I list your next event with a link back to you? Just send the poster or link and I'll add it, then tell you how many people click through. No cost, and I'll take it down anytime you ask.

Follow up with real view/click numbers before asking for anything regular. Track each organizer at: replied -> said yes -> sent a poster -> sent a second one unprompted.

**Test the paying side too:** talk to ~10 cafés/venues (5 OMR, 5 Adyar belt): how do you fill an event, what do you spend on promotion, what is one more full event worth?

---

## 11. Progress so far

- Pipeline pieces written and tested on synthetic data: `extract_poster.py` (pytesseract baseline, rule-based fields, confidence, needs-review flags) and `test_sources.py` (static fetch, Crawl4AI, robots.txt check, JSON-LD Event extraction, Instaloader new-posts-only logic with a safe stop on blocks).
- Findings from real runs:
  - Luma event pages: static fetch works and the page includes full Event JSON-LD (name, dates, venue, coordinates, organizer, availability). Price currency looked like a default (`usd`), so verify.
  - FOSS United Chennai and eChai pages: static and Crawl4AI returned the same content (3/3 expected words); static is much faster. Neither has JSON-LD, so the LLM extracts from text.
  - Instaloader without login: blocked. Login with a throwaway account hit a checkpoint. Decision: build on the manual share feed; keep Instaloader optional.
- Environment note: use **Python 3.12** (3.15 broke a Crawl4AI dependency build on Windows).

## 12. Open questions

1. Where does the cloud inbox live (free-tier backend vs cheap VPS)? Check current limits.
2. How do organizers prove ownership for "claim your listing"?
3. Do reports need a login (anonymous is easier but more abusable)?
4. Do the two vision models hold up on real Chennai posters (Tamil, stylized dates)? **The 100-poster test decides.**
5. How deep are existing competitors' Chennai coverage for small, non-tech events?
6. Does the Instagram Graph API (mentions, hashtag search) become available to you without business verification?
7. What do organizers actually say about paying for featured placement?

## 13. Suggested repo layout

```
events-map/
  README.md              # short pitch + screenshots
  ABOUT_THIS_PROJECT.md  # this file
  site/                  # static MapLibre front end + events.json
  worker/                # ingest, extract, validate, dedupe, publish
  tools/                 # extract_poster.py, test_sources.py
  data/                  # venues.csv (directory), sources.yaml
  docs/                  # survey, DM templates, test-set notes
```

## 14. Sources checked while researching

- District/Eternal numbers and BookMyShow share: https://the-ken.com/story/district-isnt-even-2-of-eternals-business-but-its-enough-to-rattle-bookmyshow/
- Margazhi 2026 dates: https://hindutone.com/festivals/margazhi-2026-tamil-month-festivals/ ; existing season site: https://season.mylaporetimes.com/
- Instaloader troubleshooting and CLI options: https://instaloader.github.io/troubleshooting.html , https://instaloader.github.io/cli-options.html
- Instagram hashtag search (limits, review): https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search
- WhatsApp Business pricing: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing.md
- Poster OCR benchmark (general, not Chennai-specific): https://arxiv.org/pdf/2603.24078
- Chennai community pages used in tests: https://fossunited.org/c/chennai , https://echai.ventures/chennai/communities/recurring-meetup , https://luma.com/bnaljef7

*Competitor details, pricing and API limits change often; re-verify before relying on any figure above.*
