import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  ChevronDown,
  EyeOff,
  ExternalLink,
  Loader2,
  Lock,
  MapPin,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import ChennaiMap from '../components/ChennaiMap';
import { adminRequest } from '../lib/api';
import { formatDate, formatTime } from '../lib/format';

const TOKEN_KEY = 'jarvis-admin-token';

const CATEGORIES = [
  { id: 'concerts', name: 'Concerts & Gigs' },
  { id: 'tech-events', name: 'Tech Events' },
  { id: 'social-gatherings', name: 'Social Gatherings' },
  { id: 'college-culturals', name: 'College Culturals' },
  { id: 'movies', name: 'Movies & Screenings' },
];

const TABS = [
  { id: 'review', label: 'To review' },
  { id: 'published', label: 'Live' },
  { id: 'hidden', label: 'Hidden' },
];

const FIELD_LABELS = {
  title: 'title',
  category: 'category',
  venue: 'venue',
  area: 'area',
  date: 'date',
  lat: 'map pin',
  lng: 'map pin',
};

const STATUS_NAMES = { published: 'Live', review: 'In review', hidden: 'Hidden', expired: 'Expired' };

const PRECISION_NOTES = {
  venue: { text: 'Exact venue pin', tone: 'ok' },
  area: { text: 'Pinned to the neighbourhood centre, not the exact venue', tone: 'warn' },
  city: { text: 'Pinned to the centre of Chennai: venue not recognised. Set the area or adjust the pin.', tone: 'bad' },
  manual: { text: 'Pin set by hand', tone: 'ok' },
};

const readToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
};
const saveToken = (token) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: stays signed in for this tab only */
  }
};

// ISO timestamp -> value for a datetime-local input, in Chennai time.
const toLocalInput = (iso) => {
  if (!iso) return '';
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
};

const toDraft = (ev) => ({
  title: ev.title || '',
  category: ev.category || '',
  venue: ev.venue || '',
  area: ev.area || '',
  date: toLocalInput(ev.date),
  end_date: toLocalInput(ev.end_date),
  is_free: Boolean(ev.is_free),
  price: ev.is_free ? '' : String(ev.price ?? ''),
  booking_link: ev.booking_link || '',
  contact_phone: ev.contact_phone || '',
  instagram: ev.instagram || '',
  description: ev.description || '',
  is_featured: Boolean(ev.is_featured),
  lat: ev.lat ?? '',
  lng: ev.lng ?? '',
});

// Only send what changed, in the shape the API expects.
const changesFrom = (original, draft) => {
  const out = {};
  for (const key of ['title', 'category', 'venue', 'area', 'date', 'end_date', 'booking_link', 'contact_phone', 'instagram', 'description']) {
    if (draft[key] !== original[key]) out[key] = draft[key];
  }
  if (draft.is_featured !== original.is_featured) out.is_featured = draft.is_featured;
  if (draft.is_free !== original.is_free || draft.price !== original.price) {
    out.is_free = draft.is_free;
    out.price = draft.is_free ? 0 : Number(draft.price || 0);
  }
  if (String(draft.lat) !== String(original.lat) || String(draft.lng) !== String(original.lng)) {
    const lat = draft.lat === '' ? null : Number(draft.lat);
    const lng = draft.lng === '' ? null : Number(draft.lng);
    out.lat = Number.isFinite(lat) ? lat : null;
    out.lng = Number.isFinite(lng) ? lng : null;
  }
  return out;
};

const timeAgo = (iso) => {
  if (!iso) return '';
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
};

const inputClass =
  'w-full border-b border-line bg-transparent py-2 font-serif text-base outline-none transition-colors focus:border-teal-700 dark:focus:border-teal-400';
const labelClass = 'mb-1 block text-[11px] uppercase tracking-widest text-muted';

// --------------------------------------------------------------------------
// Password gate
// --------------------------------------------------------------------------
function PasswordGate({ onUnlock, initialError }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState(initialError || '');
  const [checking, setChecking] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!password.trim()) return;
    setChecking(true);
    setError('');
    try {
      await adminRequest(password.trim(), '/api/admin/session');
      onUnlock(password.trim());
    } catch (err) {
      setError(err.status ? err.message : "Couldn't reach the server. It may be waking up, so try again in a minute.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <form onSubmit={submit} className="mx-auto mt-16 max-w-sm border border-line p-6 sm:p-8">
      <div className="flex items-center gap-3 text-muted">
        <Lock className="size-4" strokeWidth={1.5} />
        <p className="text-[11px] uppercase tracking-[0.3em]">Review desk</p>
      </div>
      <h1 className="mt-4 font-display text-4xl uppercase tracking-[0.02em]">Admin sign-in</h1>
      <label htmlFor="admin-password" className={`${labelClass} mt-8`}>
        Password
      </label>
      <input
        id="admin-password"
        type="password"
        autoComplete="current-password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={inputClass}
      />
      {error && (
        <p role="alert" className="mt-4 flex items-start gap-2 text-sm text-rose-700 dark:text-rose-300">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
      <button
        type="submit"
        disabled={checking || !password.trim()}
        className="mt-8 flex w-full cursor-pointer items-center justify-center gap-2 bg-ink px-6 py-3 font-display text-lg tracking-[0.14em] text-ivory transition-colors hover:bg-teal-700 disabled:opacity-50 dark:bg-bone dark:text-ink dark:hover:bg-teal-400"
      >
        {checking && <Loader2 className="size-4 animate-spin" />}
        Unlock
      </button>
    </form>
  );
}

// --------------------------------------------------------------------------
// One submission: summary row + editor
// --------------------------------------------------------------------------
function EventEditor({ event, token, theme, open, onToggle, onChanged, onRemoved, onAuthError }) {
  const original = useMemo(() => toDraft(event), [event]);
  const [draft, setDraft] = useState(original);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  // When the saved event changes (after a save), start editing from the new values.
  const [draftSource, setDraftSource] = useState(original);
  if (draftSource !== original) {
    setDraftSource(original);
    setDraft(original);
  }

  const changes = changesFrom(original, draft);
  const dirty = Object.keys(changes).length > 0;
  const set = (key) => (e) => setDraft((d) => ({ ...d, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const missing = [...new Set((event.missing || []).map((f) => FIELD_LABELS[f] || f))];
  const sub = event.submission || {};
  const extractedBy = sub.extracted_data?._backend || sub.extracted_data?.backend;
  const precision = PRECISION_NOTES[event.location_precision];
  const hasPin = typeof event.lat === 'number' && typeof event.lng === 'number';
  const duplicates = event.duplicates || [];

  const run = async (label, fn) => {
    setBusy(label);
    setError('');
    try {
      await fn();
    } catch (err) {
      if (err.status === 401) onAuthError();
      else setError(err.status ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setBusy('');
    }
  };

  const save = () =>
    run('save', async () => {
      const updated = await adminRequest(token, `/api/admin/events/${event.id}`, { method: 'PATCH', body: changes });
      onChanged(updated);
    });

  const setStatus = (status) =>
    run(status, async () => {
      if (dirty) await adminRequest(token, `/api/admin/events/${event.id}`, { method: 'PATCH', body: changes });
      const updated = await adminRequest(token, `/api/admin/events/${event.id}/status`, {
        method: 'POST',
        body: { status },
      });
      onChanged(updated);
    });

  const remove = () =>
    run('delete', async () => {
      await adminRequest(token, `/api/admin/events/${event.id}`, { method: 'DELETE' });
      onRemoved(event.id);
    });

  const mapEvent = useMemo(() => (hasPin ? [{ ...event, isFree: Boolean(event.is_free) }] : []), [event, hasPin]);

  return (
    <li className="border border-line">
      {/* Summary row */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-start gap-4 p-3 text-left transition-colors hover:bg-ink/[0.03] sm:p-4 dark:hover:bg-bone/[0.03]"
      >
        <div className="aspect-[3/4] w-14 shrink-0 overflow-hidden border border-line bg-ink/5 sm:w-16 dark:bg-bone/5">
          {event.image_url && <img src={event.image_url} alt="" className="size-full object-cover" loading="lazy" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-xl tracking-[0.02em] sm:text-2xl">
            {event.title || <span className="italic text-muted">Untitled poster</span>}
          </p>
          <p className="mt-0.5 truncate text-sm italic text-muted">
            {event.date ? `${formatDate(event.date)} · ${formatTime(event.date)}` : 'No date'} ·{' '}
            {(event.venue || '').split(',')[0] || 'No venue'}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] uppercase tracking-wider">
            {missing.length > 0 ? (
              <span className="border border-amber-600/50 px-1.5 py-0.5 text-amber-700 dark:text-amber-400">
                Needs {missing.join(', ')}
              </span>
            ) : (
              <span className="border border-teal-600/50 px-1.5 py-0.5 text-teal-700 dark:text-teal-400">Ready</span>
            )}
            {duplicates.length > 0 && (
              <span className="flex items-center gap-1 border border-rose-500/60 bg-rose-500/5 px-1.5 py-0.5 text-rose-700 dark:text-rose-300">
                <Copy className="size-3" /> Possible duplicate
              </span>
            )}
            {event.location_precision === 'city' && (
              <span className="border border-rose-500/50 px-1.5 py-0.5 text-rose-700 dark:text-rose-300">Rough pin</span>
            )}
            {sub.source && <span className="border border-line px-1.5 py-0.5 text-muted">{sub.source.replace('_', ' ')}</span>}
            {sub.created_at && <span className="px-1.5 py-0.5 text-muted">{timeAgo(sub.created_at)}</span>}
          </div>
        </div>
        <ChevronDown className={`mt-1 size-5 shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Editor */}
      {open && duplicates.length > 0 && (
        <div className="border-t border-rose-500/40 bg-rose-500/[0.04] p-4 sm:px-6">
          <p className="flex items-center gap-2 text-sm font-medium text-rose-700 dark:text-rose-300">
            <Copy className="size-4" /> Looks like {duplicates.length === 1 ? 'an event' : 'events'} already on record
          </p>
          <p className="mt-1 text-xs text-muted">
            If it's the same event, delete this one. A series (same design, new date) is fine to keep.
          </p>
          <ul className="mt-3 space-y-2">
            {duplicates.map((d) => (
              <li key={d.id} className="flex items-center gap-3 border border-line bg-ivory p-2 dark:bg-ink">
                <div className="aspect-[3/4] w-10 shrink-0 overflow-hidden border border-line bg-ink/5 dark:bg-bone/5">
                  {d.image_url && <img src={d.image_url} alt="" className="size-full object-cover" loading="lazy" />}
                </div>
                <div className="min-w-0 flex-1 text-sm">
                  <p className="truncate font-medium">{d.title || <span className="italic text-muted">Untitled poster</span>}</p>
                  <p className="truncate text-xs text-muted">
                    #{d.id} · {STATUS_NAMES[d.status] || d.status} ·{' '}
                    {d.date ? formatDate(d.date) : 'No date'} · {(d.venue || '').split(',')[0] || 'No venue'}
                  </p>
                </div>
                <span className="shrink-0 text-right text-[10px] uppercase tracking-wider text-rose-700 dark:text-rose-300">
                  {d.reason}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {open && (
        <div className="grid grid-cols-1 gap-8 border-t border-line p-4 sm:p-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="space-y-4">
            {event.image_url ? (
              <a href={event.image_url} target="_blank" rel="noreferrer" className="group block">
                <img src={event.image_url} alt={`Poster for ${event.title || 'submission'}`} className="w-full border border-line" />
                <span className="mt-2 inline-flex items-center gap-1 text-xs text-muted group-hover:text-teal-700 dark:group-hover:text-teal-400">
                  Open full size <ExternalLink className="size-3" />
                </span>
              </a>
            ) : (
              <p className="border border-dashed border-line p-6 text-center text-sm italic text-muted">No poster</p>
            )}
            <dl className="space-y-2 text-sm">
              <div>
                <dt className={labelClass}>Submitter contact (private)</dt>
                <dd className="break-words">{sub.submitter_contact || <span className="italic text-muted">Not given</span>}</dd>
              </div>
              {extractedBy && (
                <div>
                  <dt className={labelClass}>Read by</dt>
                  <dd className="text-muted">{extractedBy}</dd>
                </div>
              )}
            </dl>
          </div>

          <div className="space-y-5">
            <div>
              <label className={labelClass} htmlFor={`title-${event.id}`}>Title</label>
              <input id={`title-${event.id}`} value={draft.title} onChange={set('title')} className={`${inputClass} text-lg`} />
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor={`cat-${event.id}`}>Category</label>
                <select id={`cat-${event.id}`} value={draft.category} onChange={set('category')} className={`${inputClass} cursor-pointer`}>
                  <option value="">Not set</option>
                  {CATEGORIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <span className={labelClass}>Admission</span>
                <div className="flex items-center gap-4 py-2">
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input type="checkbox" checked={draft.is_free} onChange={set('is_free')} className="size-4 accent-teal-600" />
                    Free
                  </label>
                  {!draft.is_free && (
                    <label className="flex items-center gap-1 text-sm">
                      <span className="text-muted">₹</span>
                      <input
                        type="number"
                        min="0"
                        value={draft.price}
                        onChange={set('price')}
                        aria-label="Price"
                        className="w-24 border-b border-line bg-transparent py-1 outline-none focus:border-teal-700 dark:focus:border-teal-400"
                      />
                    </label>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor={`date-${event.id}`}>Starts (Chennai time)</label>
                <input id={`date-${event.id}`} type="datetime-local" value={draft.date} onChange={set('date')} className={inputClass} />
              </div>
              <div>
                <label className={labelClass} htmlFor={`end-${event.id}`}>Ends (optional)</label>
                <input id={`end-${event.id}`} type="datetime-local" value={draft.end_date} onChange={set('end_date')} className={inputClass} />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor={`venue-${event.id}`}>Venue</label>
                <input id={`venue-${event.id}`} value={draft.venue} onChange={set('venue')} className={inputClass} />
              </div>
              <div>
                <label className={labelClass} htmlFor={`area-${event.id}`}>Area</label>
                <input id={`area-${event.id}`} value={draft.area} onChange={set('area')} className={inputClass} placeholder="e.g. Adyar" />
              </div>
            </div>

            {/* Location */}
            <div className="space-y-2">
              <p className="flex items-start gap-2 text-sm">
                <MapPin
                  className={`mt-0.5 size-4 shrink-0 ${
                    precision?.tone === 'bad' ? 'text-rose-600' : precision?.tone === 'warn' ? 'text-amber-600' : 'text-teal-600'
                  }`}
                />
                <span className="text-muted">
                  {hasPin ? precision?.text || 'Pinned' : 'No pin yet. Add a venue or area and save.'}
                  {(changes.venue !== undefined || changes.area !== undefined) && ' · The pin moves to match when you save.'}
                </span>
              </p>
              {hasPin && open && (
                <ChennaiMap
                  events={mapEvent}
                  selectedEventId={event.id}
                  theme={theme}
                  className="h-48 w-full border border-line"
                />
              )}
              <details className="text-sm">
                <summary className="cursor-pointer text-muted hover:text-teal-700 dark:hover:text-teal-400">Adjust pin by hand</summary>
                <div className="mt-2 grid grid-cols-2 gap-4">
                  <label className="text-xs text-muted">
                    Latitude
                    <input type="number" step="any" value={draft.lat} onChange={set('lat')} className={inputClass} />
                  </label>
                  <label className="text-xs text-muted">
                    Longitude
                    <input type="number" step="any" value={draft.lng} onChange={set('lng')} className={inputClass} />
                  </label>
                </div>
                <p className="mt-1 text-xs italic text-muted">
                  Tip: right-click the spot in Google Maps to copy its coordinates.
                </p>
              </details>
            </div>

            <div>
              <label className={labelClass} htmlFor={`link-${event.id}`}>Booking link</label>
              <input id={`link-${event.id}`} type="url" value={draft.booking_link} onChange={set('booking_link')} className={inputClass} placeholder="https://" />
            </div>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor={`phone-${event.id}`}>Organiser phone</label>
                <input id={`phone-${event.id}`} type="tel" value={draft.contact_phone} onChange={set('contact_phone')} className={inputClass} placeholder="98765 43210" />
              </div>
              <div>
                <label className={labelClass} htmlFor={`ig-${event.id}`}>Organiser Instagram</label>
                <input id={`ig-${event.id}`} value={draft.instagram} onChange={set('instagram')} className={inputClass} placeholder="@handle" />
              </div>
            </div>
            <p className="-mt-3 text-xs italic text-muted">
              Shown publicly as the event's button: booking link first, then Instagram, then phone. None of them = no button.
            </p>
            <div>
              <label className={labelClass} htmlFor={`desc-${event.id}`}>Description</label>
              <textarea
                id={`desc-${event.id}`}
                rows={3}
                value={draft.description}
                onChange={set('description')}
                className="w-full border border-line bg-transparent p-2 font-serif text-sm outline-none focus:border-teal-700 dark:focus:border-teal-400"
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={draft.is_featured} onChange={set('is_featured')} className="size-4 accent-teal-600" />
              Feature on the home page
            </label>

            {error && (
              <p role="alert" className="flex items-start gap-2 border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-700 dark:text-rose-300">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{error}</span>
              </p>
            )}

            {/* Actions */}
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
              {event.status !== 'published' && (
                <button
                  type="button"
                  onClick={() => setStatus('published')}
                  disabled={Boolean(busy)}
                  className="flex cursor-pointer items-center gap-2 bg-teal-700 px-5 py-2.5 font-display text-lg tracking-[0.12em] text-white transition-colors hover:bg-teal-600 disabled:opacity-50"
                >
                  {busy === 'published' ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
                  {dirty ? 'Save & publish' : 'Publish'}
                </button>
              )}
              <button
                type="button"
                onClick={save}
                disabled={!dirty || Boolean(busy)}
                className="flex cursor-pointer items-center gap-2 border border-line px-5 py-2.5 font-display text-lg tracking-[0.12em] transition-colors hover:border-ink/40 disabled:cursor-default disabled:opacity-40 dark:hover:border-bone/40"
              >
                {busy === 'save' && <Loader2 className="size-4 animate-spin" />}
                Save
              </button>
              {event.status !== 'hidden' && (
                <button
                  type="button"
                  onClick={() => setStatus('hidden')}
                  disabled={Boolean(busy)}
                  className="flex cursor-pointer items-center gap-2 px-3 py-2.5 text-sm text-muted transition-colors hover:text-ink disabled:opacity-50 dark:hover:text-bone"
                >
                  {busy === 'hidden' ? <Loader2 className="size-4 animate-spin" /> : <EyeOff className="size-4" />}
                  Hide
                </button>
              )}
              <div className="ml-auto">
                {confirmDelete ? (
                  <span className="flex items-center gap-2 text-sm">
                    <span className="text-muted">Delete for good?</span>
                    <button
                      type="button"
                      onClick={remove}
                      disabled={Boolean(busy)}
                      className="cursor-pointer bg-rose-700 px-3 py-1.5 text-white hover:bg-rose-600 disabled:opacity-50"
                    >
                      {busy === 'delete' ? 'Deleting…' : 'Delete'}
                    </button>
                    <button type="button" onClick={() => setConfirmDelete(false)} className="cursor-pointer px-2 py-1.5 text-muted">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="flex cursor-pointer items-center gap-1.5 px-2 py-2.5 text-sm text-muted transition-colors hover:text-rose-600"
                  >
                    <Trash2 className="size-4" /> Delete
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </li>
  );
}

// --------------------------------------------------------------------------
// Page
// --------------------------------------------------------------------------
export default function AdminView({ theme }) {
  const [token, setToken] = useState(readToken);
  const [gateError, setGateError] = useState('');
  const [tab, setTab] = useState('review');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);
  const [notice, setNotice] = useState('');

  // Keep the review desk out of search engines.
  useEffect(() => {
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow';
    document.head.appendChild(meta);
    const previousTitle = document.title;
    document.title = 'Review desk | Jarvis';
    return () => {
      meta.remove();
      document.title = previousTitle;
    };
  }, []);

  const lock = useCallback((message = '') => {
    saveToken('');
    setToken('');
    setGateError(message);
  }, []);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    adminRequest(token, `/api/admin/events?status=${tab}`)
      .then((list) => {
        if (cancelled) return;
        setEvents(list);
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) lock('That password no longer works. Sign in again.');
        else setError(err.status ? err.message : "Couldn't reach the server. It may be waking up, so try again in a minute.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, tab, reloadKey, lock]);

  const reload = () => {
    setLoading(true);
    setReloadKey((k) => k + 1);
  };

  const switchTab = (id) => {
    if (id === tab) return;
    setEvents([]);
    setLoading(true);
    setOpenId(null);
    setTab(id);
  };

  const unlock = (value) => {
    saveToken(value);
    setLoading(true);
    setToken(value);
    setGateError('');
  };

  const handleChanged = (updated) => {
    if (updated.status !== tab) {
      setEvents((list) => list.filter((e) => e.id !== updated.id));
      setOpenId(null);
      setNotice(
        updated.status === 'published'
          ? `"${updated.title}" is live.`
          : updated.status === 'hidden'
            ? `"${updated.title || 'Untitled poster'}" hidden.`
            : `Moved to ${updated.status}.`,
      );
    } else {
      setEvents((list) => list.map((e) => (e.id === updated.id ? updated : e)));
      setNotice('Saved.');
    }
  };

  const handleRemoved = (id) => {
    setEvents((list) => list.filter((e) => e.id !== id));
    setOpenId(null);
    setNotice('Deleted.');
  };

  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(''), 3500);
    return () => clearTimeout(t);
  }, [notice]);

  if (!token) {
    return (
      <div className="px-6 pb-24">
        <PasswordGate onUnlock={unlock} initialError={gateError} />
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-4 pb-24 pt-8 sm:px-6 lg:px-12">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.3em] text-muted">
              <span className="h-px w-8 bg-yellow-600 dark:bg-yellow-500" />
              Review desk
            </p>
            <h1 className="mt-3 font-display text-5xl uppercase tracking-[0.02em] sm:text-6xl">Submissions</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={reload}
              disabled={loading}
              className="flex cursor-pointer items-center gap-2 border border-line px-3 py-2 text-sm transition-colors hover:border-ink/40 dark:hover:border-bone/40"
            >
              <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
            <button
              type="button"
              onClick={() => lock('')}
              className="flex cursor-pointer items-center gap-2 border border-line px-3 py-2 text-sm transition-colors hover:border-ink/40 dark:hover:border-bone/40"
            >
              <Lock className="size-4" /> Lock
            </button>
          </div>
        </div>

        <div role="tablist" className="mt-8 flex gap-6 border-b border-line">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => switchTab(t.id)}
              className={`-mb-px cursor-pointer border-b-2 pb-3 text-sm uppercase tracking-widest transition-colors ${
                tab === t.id
                  ? 'border-teal-600 text-ink dark:border-teal-400 dark:text-bone'
                  : 'border-transparent text-muted hover:text-ink dark:hover:text-bone'
              }`}
            >
              {t.label}
              {tab === t.id && !loading && <span className="ml-2 text-muted">{events.length}</span>}
            </button>
          ))}
        </div>

        <div aria-live="polite" className="min-h-6 py-3 text-sm text-teal-700 dark:text-teal-400">
          {notice}
        </div>

        {error && (
          <p role="alert" className="mb-4 flex items-start gap-2 border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-700 dark:text-rose-300">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </p>
        )}

        {loading && events.length === 0 ? (
          <p className="flex items-center gap-2 py-12 text-muted">
            <Loader2 className="size-4 animate-spin" /> Loading…
          </p>
        ) : events.length === 0 && !error ? (
          <p className="py-12 text-center italic text-muted">
            {tab === 'review' ? 'Nothing waiting for review. All caught up.' : 'Nothing here.'}
          </p>
        ) : (
          <ul className="space-y-3">
            {events.map((ev) => (
              <EventEditor
                key={ev.id}
                event={ev}
                token={token}
                theme={theme}
                open={openId === ev.id}
                onToggle={() => setOpenId((id) => (id === ev.id ? null : ev.id))}
                onChanged={handleChanged}
                onRemoved={handleRemoved}
                onAuthError={() => lock('That password no longer works. Sign in again.')}
              />
            ))}
          </ul>
        )}
      </div>
    </motion.div>
  );
}
