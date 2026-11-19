import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

const isPlaceholder = (value) => !value || value.includes('your-');

export const isSupabaseConfigured = !isPlaceholder(supabaseUrl) && !isPlaceholder(supabaseAnonKey);

// Public (anon) client: row-level security limits it to reading published
// events and venues. All writes go through the backend API.
export const supabase = isSupabaseConfigured ? createClient(supabaseUrl, supabaseAnonKey) : null;

const EVENT_COLUMNS =
  'id,title,category,area,venue,date,end_date,price,is_free,description,image_url,booking_link,contact_phone,instagram,lat,lng,is_featured';

/**
 * Published events, soonest first, in the shape the UI uses (`isFree`).
 * Returns null when Supabase isn't configured or the request fails, so the
 * caller can keep showing the bundled snapshot.
 */
export async function fetchPublishedEvents() {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from('events')
    .select(EVENT_COLUMNS)
    .eq('status', 'published')
    .order('date', { ascending: true });
  if (error) {
    console.warn('Could not load events from Supabase:', error.message);
    return null;
  }
  return data.map((row) => ({ ...row, isFree: Boolean(row.is_free) }));
}
