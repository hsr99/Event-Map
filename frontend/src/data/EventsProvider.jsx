import { useEffect, useState } from 'react';
import { EventsContext } from './eventsContext';
import { events as snapshot } from './events';
import { fetchPublishedEvents } from '../lib/supabase';

const byDate = (list) => [...list].sort((a, b) => new Date(a.date) - new Date(b.date));

const IST_OFFSET_MS = 330 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

// Hide events that are over. With no end time, an event stays listed until the
// end of its day (Chennai time).
const isUpcoming = (event, now = Date.now()) => {
  const start = new Date(event.date).getTime();
  if (Number.isNaN(start)) return false;
  const end = new Date(event.end_date || event.endDate || NaN).getTime();
  if (!Number.isNaN(end)) return end >= now;
  const endOfDay = Math.floor((start + IST_OFFSET_MS) / DAY_MS) * DAY_MS + DAY_MS - IST_OFFSET_MS;
  return endOfDay > now;
};

const upcoming = (list) => byDate(list.filter((event) => isUpcoming(event)));

// Shows the bundled snapshot instantly, then swaps in live published events
// from Supabase. If Supabase is unreachable or unconfigured, the snapshot stays.
export default function EventsProvider({ children }) {
  const [state, setState] = useState(() => ({ events: upcoming(snapshot), source: 'snapshot' }));

  useEffect(() => {
    let cancelled = false;
    fetchPublishedEvents().then((live) => {
      if (!cancelled && live) setState({ events: upcoming(live), source: 'live' });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return <EventsContext.Provider value={state}>{children}</EventsContext.Provider>;
}
