import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

/**
 * Fetch events from Supabase (or return null if unconfigured)
 */
export async function fetchSupabaseEvents() {
  if (!supabase) return null;
  try {
    const { data, error } = await supabase
      .from('events')
      .select('*')
      .eq('status', 'published')
      .order('date', { ascending: true });

    if (error) {
      console.warn('Supabase fetch error:', error);
      return null;
    }
    return data;
  } catch (err) {
    console.warn('Supabase error:', err);
    return null;
  }
}

/**
 * Submit community poster to Supabase submissions intake
 */
export async function submitPosterToSupabase({ source = 'web_form', submitterContact, rawPosterUrl, extractedData }) {
  if (!supabase) return null;
  return await supabase
    .from('submissions')
    .insert([
      {
        source,
        submitter_contact: submitterContact,
        raw_poster_url: rawPosterUrl,
        extracted_data: extractedData,
        status: 'review',
      },
    ])
    .select();
}
