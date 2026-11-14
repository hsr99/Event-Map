import { useCallback, useMemo, useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, Search, X, Grid2X2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import EventCard from './EventCard';
import EventDrawer from './EventDrawer';
import Select from './Select';
import CategoryBentoOverlay from './CategoryBentoOverlay';
import { events } from '../data/events';

const BUDGETS = ['All', 'Free', 'Ticketed'];
const eventsByDate = [...events].sort((a, b) => new Date(a.date) - new Date(b.date));

const matchesQuery = (event, q) => !q || [event.title, event.venue, event.area].some((field) => field.toLowerCase().includes(q));
const matchesBudget = (event, budget) => budget === 'All' || (budget === 'Free' ? event.isFree : !event.isFree);
const matchesArea = (event, area) => area === 'All' || event.area === area;

const CATEGORY_TITLES = {
  'all': 'All Experiences',
  'college-culturals': 'College Culturals',
  'tech-events': 'Tech Events',
  'movies': 'Movies',
  'concerts': 'Concerts',
  'social-gatherings': 'Social Gatherings',
};

export default function UnifiedEventsDirectory({ theme, onToggleTheme }) {
  const navigate = useNavigate();

  const [activeCategory, setActiveCategory] = useState('all');
  const [isCategoryOverlayOpen, setIsCategoryOverlayOpen] = useState(false);

  const [query, setQuery] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('q') || '';
  });
  const [budget, setBudget] = useState('All');
  const [area, setArea] = useState('All');
  const [selectedEvent, setSelectedEvent] = useState(null);

  const pageTitle = CATEGORY_TITLES[activeCategory] || 'All Experiences';

  const categoryEvents = useMemo(() => {
    if (activeCategory === 'all') return eventsByDate;
    return eventsByDate.filter((e) => e.category === activeCategory);
  }, [activeCategory]);

  const AREA_OPTIONS = useMemo(() => [
    { value: 'All', label: 'All neighbourhoods' },
    ...[...new Set(categoryEvents.map((event) => event.area))].sort().map((a) => ({ value: a, label: a })),
  ], [categoryEvents]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (id) {
      const event = events.find((e) => e.id === parseInt(id, 10));
      if (event) {
        setSelectedEvent(event);
      }
    }
  }, []);

  const closeEvent = useCallback(() => setSelectedEvent(null), []);

  const visibleEvents = useMemo(() => {
    const q = query.trim().toLowerCase();
    return categoryEvents.filter(
      (event) => matchesQuery(event, q) && matchesBudget(event, budget) && matchesArea(event, area),
    );
  }, [categoryEvents, query, budget, area]);

  const hasFilters = Boolean(query.trim()) || budget !== 'All' || area !== 'All';

  const resetFilters = () => {
    setQuery('');
    setBudget('All');
    setArea('All');
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, y: 16, transition: { duration: 0.3, ease: 'easeIn' } }}
      className="min-h-svh"
    >
      <main className="mx-auto w-full px-6 pb-24 lg:px-12 xl:px-16 2xl:px-24">
        <section className="pb-10 pt-14 sm:pt-20">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="group mb-8 inline-flex cursor-pointer items-center gap-3 text-sm transition-colors hover:text-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 dark:hover:text-teal-400"
          >
            <ArrowLeft className="size-4 transition-transform duration-300 group-hover:-translate-x-1" strokeWidth={1.25} />
            <span className="hidden sm:inline">Back to Home</span>
            <span className="sm:hidden">Back</span>
          </button>
          
          <p className="flex items-center gap-4 text-[11px] uppercase tracking-[0.3em] text-muted">
            <span className="h-px w-10 bg-yellow-600 dark:bg-yellow-500" />
            Curated listings · Oct - Nov 2026
          </p>
          <motion.h1 
            key={pageTitle}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 font-display text-6xl leading-[0.85] uppercase tracking-[0.02em] sm:text-8xl"
          >
            {pageTitle}
          </motion.h1>
          
        </section>

        <section aria-label="Filters" className="border-y border-line py-6 transition-colors duration-200">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:gap-8">
            <button
              onClick={() => setIsCategoryOverlayOpen(true)}
              className="group flex h-10 cursor-pointer items-center justify-center gap-3 border border-line bg-transparent px-5 font-serif text-lg italic text-ink transition-colors hover:border-teal-700 hover:text-teal-800 dark:text-bone dark:hover:border-teal-400 dark:hover:text-teal-300 shrink-0"
            >
              <Grid2X2 className="h-4 w-4 opacity-70 group-hover:opacity-100" strokeWidth={1.5} />
              Explore by Categories
            </button>

            <label className="flex flex-1 items-center gap-3 border-b border-line pb-2 transition-colors duration-300 focus-within:border-teal-700 dark:focus-within:border-teal-400">
              <span className="sr-only">Search events</span>
              <Search className="size-4 shrink-0 text-muted" strokeWidth={1.25} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by event, venue or neighbourhood"
                className="w-full bg-transparent py-1 outline-none placeholder:italic placeholder:text-muted"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="Clear search"
                  className="text-muted cursor-pointer transition-colors hover:text-ink dark:hover:text-bone"
                >
                  <X className="size-4" strokeWidth={1.25} />
                </button>
              )}
            </label>

            <div className="flex flex-wrap items-end gap-x-12 gap-y-6">
              <div className="w-40">
                <Select
                  label="Admission"
                  value={budget}
                  options={BUDGETS.map((name) => ({ value: name, label: name }))}
                  onChange={setBudget}
                />
              </div>

              <div className="w-60">
                <Select label="Area" value={area} options={AREA_OPTIONS} onChange={setArea} />
              </div>
            </div>
          </div>
        </section>

        <div className="flex items-baseline justify-between py-6 text-sm">
          <p className="italic text-muted">
            Showing <span className="not-italic text-ink tabular-nums dark:text-bone">{visibleEvents.length}</span> of{' '}
            {categoryEvents.length} events
          </p>
          {hasFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="cursor-pointer underline decoration-line underline-offset-4 transition-colors hover:text-teal-700 hover:decoration-current dark:hover:text-teal-400"
            >
              Clear all filters
            </button>
          )}
        </div>

        <motion.div layout className="relative grid grid-cols-1 gap-x-8 gap-y-10 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          <AnimatePresence mode="popLayout">
            {visibleEvents.map((event) => (
              <EventCard key={event.id} event={event} onSelect={setSelectedEvent} />
            ))}
          </AnimatePresence>
        </motion.div>

        <AnimatePresence>
          {visibleEvents.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0, transition: { delay: 0.15 } }}
              exit={{ opacity: 0, transition: { duration: 0.15 } }}
              className="border border-line px-6 py-20 text-center transition-colors duration-200"
            >
              <h2 className="font-display text-5xl tracking-[0.02em]">Nothing on the calendar</h2>
              <p className="mt-3 italic text-muted">No events match this combination. Try loosening a filter or two.</p>
              <button
                type="button"
                onClick={resetFilters}
                className="mt-8 cursor-pointer text-sm underline decoration-line underline-offset-4 transition-colors hover:text-teal-700 hover:decoration-current dark:hover:text-teal-400"
              >
                Clear all filters
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {isCategoryOverlayOpen && (
          <CategoryBentoOverlay 
            onSelectCategory={(categoryId) => setActiveCategory(categoryId)} 
            onClose={() => setIsCategoryOverlayOpen(false)} 
          />
        )}
      </AnimatePresence>

      {createPortal(
        <AnimatePresence>
          {selectedEvent && <EventDrawer key={selectedEvent.id} event={selectedEvent} onClose={closeEvent} />}
        </AnimatePresence>,
        document.body,
      )}
    </motion.div>
  );
}
