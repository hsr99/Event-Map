import { useEffect } from 'react';

// Search and link-preview metadata for each page. Google runs the site's
// JavaScript, so tags set here are what it indexes. (WhatsApp and other link
// previews don't, so they always get the defaults in index.html.)
export const SITE_URL = 'https://chennai-events-map.vercel.app';
export const SITE_NAME = 'Gathr';
export const DEFAULT_TITLE = 'Chennai Event Map: concerts, workshops & meetups | Gathr';
export const DEFAULT_DESCRIPTION =
  "Find what's on in Chennai this week: concerts, gigs, tech meetups, workshops, college culturals and screenings, all on one live map. Free to browse, and anyone can add an event by dropping its poster.";

const setMeta = (attr, key, content) => {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
};

const setCanonical = (href) => {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
};

const JSON_LD_ID = 'page-structured-data';

const setJsonLd = (data) => {
  document.getElementById(JSON_LD_ID)?.remove();
  if (!data) return;
  const el = document.createElement('script');
  el.type = 'application/ld+json';
  el.id = JSON_LD_ID;
  // "<" can't end the script tag early inside JSON-LD
  el.textContent = JSON.stringify(data).replace(/</g, '\\u003c');
  document.head.appendChild(el);
};

/**
 * Set this page's title, description, canonical URL and structured data.
 * `path` is relative to the site root, e.g. '/events?id=4'.
 */
export function usePageMeta({ title, description, path = '/', jsonLd = null }) {
  const fullTitle = title ? `${title} | ${SITE_NAME}` : DEFAULT_TITLE;
  const desc = description || DEFAULT_DESCRIPTION;
  const url = `${SITE_URL}${path}`;
  const ld = jsonLd ? JSON.stringify(jsonLd) : '';

  useEffect(() => {
    document.title = fullTitle;
    setMeta('name', 'description', desc);
    setMeta('property', 'og:title', fullTitle);
    setMeta('property', 'og:description', desc);
    setMeta('property', 'og:url', url);
    setMeta('name', 'twitter:title', fullTitle);
    setMeta('name', 'twitter:description', desc);
    setCanonical(url);
    setJsonLd(ld ? JSON.parse(ld) : null);
  }, [fullTitle, desc, url, ld]);

  // Leaving the page: drop its structured data so it doesn't leak onto the next one.
  useEffect(() => () => setJsonLd(null), []);
}

const absolute = (url) => (!url ? undefined : url.startsWith('http') ? url : `${SITE_URL}${url.startsWith('/') ? '' : '/'}${url}`);

/** schema.org Event, which Google uses for event listings in search. */
export function eventJsonLd(event) {
  const url = `${SITE_URL}/events?id=${event.id}`;
  const venueName = (event.venue || '').split(',')[0].trim() || event.area || 'Chennai';
  const handle = (event.instagram || '').replace(/^@/, '');
  return {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: event.title,
    description: event.description || undefined,
    startDate: event.date,
    endDate: event.end_date || undefined,
    eventStatus: 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    url,
    image: event.image_url ? [absolute(event.image_url)] : undefined,
    location: {
      '@type': 'Place',
      name: venueName,
      address: {
        '@type': 'PostalAddress',
        streetAddress: event.venue || undefined,
        addressLocality: event.area || 'Chennai',
        addressRegion: 'Tamil Nadu',
        addressCountry: 'IN',
      },
      ...(typeof event.lat === 'number' && typeof event.lng === 'number'
        ? { geo: { '@type': 'GeoCoordinates', latitude: event.lat, longitude: event.lng } }
        : {}),
    },
    offers: {
      '@type': 'Offer',
      price: event.isFree ? 0 : Number(event.price || 0),
      priceCurrency: 'INR',
      availability: 'https://schema.org/InStock',
      url: event.booking_link || url,
    },
    ...(handle
      ? { organizer: { '@type': 'Organization', name: `@${handle}`, url: `https://www.instagram.com/${handle}/` } }
      : {}),
  };
}

/** Short search snippet for one event: "Sat, 22 Nov · The Backyard, Adyar · Free. A room full of…" */
export function eventDescription(event, formatDate) {
  const when = formatDate(event.date);
  const where = [(event.venue || '').split(',')[0].trim(), event.area].filter(Boolean).join(', ');
  const price = event.isFree ? 'Free' : `₹${Number(event.price || 0).toLocaleString('en-IN')}`;
  const lead = [when, where, price].filter(Boolean).join(' · ');
  const text = event.description ? `${lead}. ${event.description}` : `${lead}. On the Chennai event map.`;
  return text.length > 160 ? `${text.slice(0, 157).trimEnd()}…` : text;
}
