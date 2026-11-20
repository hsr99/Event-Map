/* global process */
// GET /sitemap.xml (rewritten here in vercel.json): the site's pages plus every
// upcoming published event, read live from Supabase with the public anon key.
const SITE = 'https://chennai-events-map.vercel.app';
const DAY_MS = 24 * 60 * 60 * 1000;

const STATIC_PAGES = [
  { path: '/', priority: '1.0', changefreq: 'daily' },
  { path: '/events', priority: '0.9', changefreq: 'daily' },
  { path: '/events/this-weekend', priority: '0.9', changefreq: 'daily' },
  { path: '/submit', priority: '0.5', changefreq: 'monthly' },
];

// Category pages (src/lib/landings.js), listed only while they have upcoming events.
const CATEGORY_PAGES = ['concerts', 'tech-events', 'college-culturals', 'movies', 'social-gatherings'];

const isUpcoming = (event, now) => {
  const end = new Date(event.end_date || event.date).getTime();
  return Number.isFinite(end) && end + DAY_MS > now;
};

async function upcomingEvents() {
  const base = process.env.VITE_SUPABASE_URL;
  const key = process.env.VITE_SUPABASE_ANON_KEY;
  if (!base || !key) return [];
  const res = await fetch(
    `${base}/rest/v1/events?select=id,category,date,end_date,updated_at&status=eq.published&order=date.asc`,
    { headers: { apikey: key, Authorization: `Bearer ${key}` } },
  );
  if (!res.ok) return [];
  const now = Date.now();
  return (await res.json()).filter((e) => isUpcoming(e, now));
}

const entry = ({ loc, lastmod, changefreq, priority }) =>
  [
    '  <url>',
    `    <loc>${loc}</loc>`,
    lastmod ? `    <lastmod>${lastmod}</lastmod>` : null,
    changefreq ? `    <changefreq>${changefreq}</changefreq>` : null,
    priority ? `    <priority>${priority}</priority>` : null,
    '  </url>',
  ]
    .filter(Boolean)
    .join('\n');

export default async function handler(req, res) {
  let events = [];
  try {
    events = await upcomingEvents();
  } catch {
    // Supabase unreachable: still serve the static pages.
  }
  const urls = [
    ...STATIC_PAGES.map((p) => ({ loc: `${SITE}${p.path}`, changefreq: p.changefreq, priority: p.priority })),
    ...CATEGORY_PAGES.filter((c) => events.some((e) => e.category === c)).map((c) => ({
      loc: `${SITE}/events/${c}`,
      changefreq: 'daily',
      priority: '0.8',
    })),
    ...events.map((e) => ({
      loc: `${SITE}/events?id=${Number(e.id)}`,
      lastmod: e.updated_at ? new Date(e.updated_at).toISOString().slice(0, 10) : undefined,
      changefreq: 'weekly',
      priority: '0.8',
    })),
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(entry).join('\n')}\n</urlset>\n`;
  res.setHeader('Content-Type', 'application/xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, s-maxage=3600, stale-while-revalidate=86400');
  res.status(200).send(xml);
}
