import { useEffect, useState } from 'react';
import { EventsContext } from './eventsContext';
import { events as snapshot } from './events';
import { fetchPublishedEvents } from '../lib/supabase';

const byDate = (list) => [...list].sort((a, b) => new Date(a.date) - new Date(b.date));

// Shows the bundled snapshot instantly, then swaps in live published events
// from Supabase. If Supabase is unreachable or unconfigured, the snapshot stays.
export default function EventsProvider({ children }) {
  const [state, setState] = useState(() => ({ events: byDate(snapshot), source: 'snapshot' }));

  useEffect(() => {
    let cancelled = false;
    fetchPublishedEvents().then((live) => {
      if (!cancelled && live) setState({ events: byDate(live), source: 'live' });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return <EventsContext.Provider value={state}>{children}</EventsContext.Provider>;
}
