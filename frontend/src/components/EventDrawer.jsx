import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowUpRight, X } from 'lucide-react';
import EventImage from './EventImage';
import { formatLongDate, formatPrice, formatTimeRange } from '../lib/format';

const EASE = [0.32, 0.72, 0, 1];

const CATEGORY_NAMES = {
  concerts: 'Concerts & Gigs',
  'tech-events': 'Tech Events',
  'social-gatherings': 'Social Gatherings',
  'college-culturals': 'College Culturals',
  movies: 'Movies & Screenings',
};

// Only http(s) links; anything else from a submission is ignored.
const safeLink = (url) => {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
};

export default function EventDrawer({ event, onClose }) {
  const bookingLink = safeLink(event.booking_link);
  const priceTone = event.isFree ? 'text-teal-700 dark:text-teal-400' : 'text-yellow-700 dark:text-yellow-500';

  useEffect(() => {
    const onKeyDown = (e) => e.key === 'Escape' && onClose();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose]);

  const details = [
    ['Venue', event.venue],
    ['Neighbourhood', event.area],
    ['Date', formatLongDate(event.date)],
    ['Timings', formatTimeRange(event.date, event.end_date)],
    ['Admission', event.isFree ? 'Free entry' : `${formatPrice(event)} per guest`],
  ];

  return (
    <>
      <motion.div
        aria-hidden
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.35 }}
        className="fixed inset-0 z-40 bg-ink/60 backdrop-blur-[2px]"
      />

      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-drawer-title"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ duration: 0.55, ease: EASE }}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-line bg-ivory text-ink transition-colors duration-200 dark:bg-ink dark:text-bone"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 sm:px-10">
          <p className="text-[11px] uppercase tracking-[0.3em] text-muted">Event details</p>
          <button
            type="button"
            onClick={onClose}
            autoFocus
            aria-label="Close details"
            className="cursor-pointer grid size-9 place-items-center border border-line transition-colors hover:border-ink/40 focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-teal-600 dark:hover:border-bone/40"
          >
            <X className="size-4" strokeWidth={1.25} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <EventImage event={event} className="aspect-[16/10]" />

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5, ease: EASE }}
            className="px-6 pb-10 pt-8 sm:px-10"
          >
            <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.22em] text-muted">
              <span className="text-teal-700 dark:text-teal-400">{CATEGORY_NAMES[event.category] || event.category}</span>
              <span aria-hidden className="h-px w-5 bg-current opacity-40" />
              <span>{event.area}</span>
            </p>
            <h2
              id="event-drawer-title"
              className="mt-4 font-display text-4xl leading-[0.9] tracking-[0.02em] sm:text-6xl"
            >
              {event.title}
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink/75 dark:text-bone/75">{event.description}</p>

            <dl className="mt-8 border-t border-line sm:mt-10">
              {details.map(([term, value]) => (
                <div key={term} className="grid grid-cols-[6.5rem_1fr] gap-4 sm:grid-cols-[8.5rem_1fr] border-b border-line py-4 text-sm">
                  <dt className="italic text-muted">{term}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </motion.div>
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-line px-6 pt-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:gap-6 sm:px-10">
          <div>
            <p className="text-xs italic text-muted">{event.isFree ? 'Admission' : 'Per guest'}</p>
            <p className={`mt-1 font-display text-4xl leading-none ${priceTone}`}>{formatPrice(event)}</p>
          </div>
          {bookingLink ? (
            <a
              href={bookingLink}
              target="_blank"
              rel="noopener noreferrer"
              className="cursor-pointer group inline-flex shrink-0 items-center gap-3 bg-ink px-5 pb-3 pt-3.5 font-display text-lg sm:gap-4 sm:px-7 sm:pb-3.5 sm:pt-4 sm:text-xl tracking-[0.14em] text-ivory transition-colors duration-300 hover:bg-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 dark:bg-bone dark:text-ink dark:hover:bg-teal-400"
            >
              {event.isFree ? 'Register' : 'Book Tickets'}
              <ArrowUpRight
                className="-mt-1 size-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                strokeWidth={1.5}
              />
            </a>
          ) : (
            <p className="max-w-[12rem] text-right text-sm italic text-muted">
              {event.isFree ? 'Just turn up, or check the poster for sign-up details.' : 'Check the poster for where to get tickets.'}
            </p>
          )}
        </div>
      </motion.aside>
    </>
  );
}
