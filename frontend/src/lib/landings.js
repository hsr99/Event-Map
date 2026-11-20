// Pages for the searches people make: /events/concerts, /events/this-weekend, ...
// Each is the events directory with one filter applied, plus its own title,
// description and intro so Google has a page to match "concerts in Chennai" to.
// Keep the slugs in sync with api/sitemap.js.

// Counts only when plural reads right ("3 upcoming concerts", not "1 upcoming concerts").
const upcoming = (n, what) => `${n > 1 ? `${n} upcoming` : 'Upcoming'} ${what}`;

export const LANDINGS = {
  concerts: {
    category: 'concerts',
    title: 'Concerts & gigs in Chennai',
    link: 'Concerts & gigs',
    description: (n) =>
      `${upcoming(n, 'concerts, indie gigs, live music and DJ nights')} in Chennai, on one map with dates, venues and ticket prices.`,
    intro: 'Live music around Chennai: indie gigs, concerts, hip-hop and electronic nights, and the venues hosting them.',
  },
  'tech-events': {
    category: 'tech-events',
    title: 'Tech events & meetups in Chennai',
    link: 'Tech meetups',
    description: (n) =>
      `${upcoming(n, 'tech meetups, hackathons, workshops and conferences')} in Chennai, with dates, venues and registration links.`,
    intro: 'Developer meetups, hackathons, startup events and hands-on workshops happening around Chennai.',
  },
  'college-culturals': {
    category: 'college-culturals',
    title: 'College culturals & fests in Chennai',
    link: 'College culturals',
    description: (n) =>
      `${upcoming(n, 'college culturals, techfests and student festivals')} in Chennai, with dates, campuses and passes.`,
    intro: "Inter-college culturals, techfests and student-run festivals across Chennai's campuses.",
  },
  movies: {
    category: 'movies',
    title: 'Film screenings in Chennai',
    link: 'Film screenings',
    description: (n) =>
      `${upcoming(n, 'film screenings, film club nights and retrospectives')} in Chennai, with dates, venues and tickets.`,
    intro: 'Indie screenings, film club nights, retrospectives and special shows around Chennai.',
  },
  'social-gatherings': {
    category: 'social-gatherings',
    title: 'Social events in Chennai: walks, workshops & meetups',
    link: 'Walks & meetups',
    description: (n) =>
      `${upcoming(n, 'food walks, heritage tours, workshops and community meetups')} in Chennai, on one map.`,
    intro: 'Food walks, heritage tours, supper clubs, workshops and community meetups around Chennai.',
  },
  'this-weekend': {
    time: 'weekend',
    heading: 'This Weekend',
    title: 'Things to do in Chennai this weekend',
    link: 'This weekend',
    description: (n) =>
      `${n > 1 ? `${n} events` : 'Events'} in Chennai this weekend: concerts, gigs, meetups, workshops and screenings, from Friday evening to Sunday night.`,
    intro: 'Everything happening in Chennai from Friday evening to Sunday night.',
  },
  tonight: {
    time: 'tonight',
    heading: 'Tonight',
    title: 'Things to do in Chennai tonight',
    link: 'Tonight',
    description: (n) => `${n > 1 ? `${n} events` : 'Events'} in Chennai tonight: gigs, screenings, meetups and more.`,
    intro: 'What’s on in Chennai from this evening into the night.',
  },
};

/** The page that matches a category and time filter, e.g. ('concerts', 'all') -> '/events/concerts'. */
export function landingPath(category, time) {
  if (category && category !== 'all') return `/events/${category}`;
  if (time === 'weekend') return '/events/this-weekend';
  if (time === 'tonight') return '/events/tonight';
  return '/events';
}
