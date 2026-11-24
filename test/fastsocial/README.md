# FastSocial test run (23 Nov 2026)

One-off test of the FastSocial Instagram data API (fastsocial.co) to see whether it
finds small Chennai event hosts. 8 of the free plan's 50 monthly credits were used.

| File | What's in it |
|---|---|
| `search_handles.csv` | Accounts returned by keyword search: "chennai workshop" (19) and "Chennai" (20). Follower counts only for the 4 that were checked. Open in Excel. |
| `hashtag_chennaiworkshops.csv` | 15 posts from `#chennaiworkshops`. FastSocial returned account IDs, not handles, and no captions. Post links open on Instagram. |
| `raw_*.json` | The API responses exactly as returned. |

Findings: specific searches ("chennai workshop") return small hosts (23–411 followers
in the 4 checked); generic ones ("Chennai") return fan, weather and meme pages. The
hashtag gave mostly old "top" posts with no handles. No location IDs came back.
