import { createContext, useContext } from 'react';

export const EventsContext = createContext({ events: [], source: 'snapshot' });

// { events, source } where source is 'live' (Supabase) or 'snapshot' (bundled fallback)
export const useEvents = () => useContext(EventsContext);
