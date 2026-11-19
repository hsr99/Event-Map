import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft,
  Search,
  X,
  Grid2X2,
  LayoutGrid,
  Map as MapIcon,
  Columns2,
  Sparkles,
  ChevronRight,
  ChevronLeft,
  ArrowUpRight,
  Calendar,
  MapPin,
  Ticket,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import EventCard from './EventCard';
import EventDrawer from './EventDrawer';
import Select from './Select';
import CategoryBentoOverlay from './CategoryBentoOverlay';
import ChennaiMap from './ChennaiMap';
import { useEvents } from '../data/eventsContext';
import { formatDate, formatTime } from '../lib/format';

const BUDGETS = ['All', 'Free', 'Ticketed'];
const TIME_FILTERS = [
  { id: 'all', label: 'All Dates' },
  { id: 'weekend', label: 'This Weekend' },
  { id: 'tonight', label: 'Tonight / Evening' },
];

const matchesQuery = (event, q) =>
  !q || [event.title, event.venue, event.area, event.category].some((field) => field.toLowerCase().includes(q));

const matchesBudget = (event, budget) =>
  budget === 'All' || (budget === 'Free' ? event.isFree : !event.isFree);

const matchesArea = (event, area) =>
  area === 'All' || event.area === area;

// Time windows are worked out in Chennai time (UTC+5:30), whatever the visitor's device is set to.
const IST_OFFSET_MS = 330 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

// Midnight (Chennai) at the start of the day containing `ms`, plus the weekday (0 = Sunday).
const chennaiDay = (ms) => {
  const shifted = new Date(ms + IST_OFFSET_MS);
  const midnight = Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate()) - IST_OFFSET_MS;
  return { midnight, weekday: shifted.getUTCDay() };
};

// [start, end) in epoch ms for a time filter, relative to now.
const timeWindow = (timeFilter, now = Date.now()) => {
  const { midnight, weekday } = chennaiDay(now);
  if (timeFilter === 'tonight') {
    // Today from 5 pm until 4 am tomorrow.
    return [midnight + 17 * 60 * 60 * 1000, midnight + DAY_MS + 4 * 60 * 60 * 1000];
  }
  if (timeFilter === 'weekend') {
    // Friday 6 pm to Monday midnight: this one if we're in it, otherwise the next.
    const daysToFriday = weekday === 0 ? -2 : weekday === 6 ? -1 : 5 - weekday;
    const friday = midnight + daysToFriday * DAY_MS;
    // Mid-weekend, earlier days are over: start from today.
    return [Math.max(friday + 18 * 60 * 60 * 1000, midnight), friday + 3 * DAY_MS];
  }
  return null;
};

const matchesTime = (event, range) => {
  if (!range) return true;
  const start = new Date(event.date).getTime();
  const endValue = event.end_date || event.endDate;
  const end = endValue ? new Date(endValue).getTime() : start;
  // Starts inside the window, or is still running when it opens.
  return start < range[1] && end >= range[0];
};

const CATEGORY_TITLES = {
  all: 'All Experiences',
  'college-culturals': 'College Culturals',
  'tech-events': 'Tech Events',
  movies: 'Movies',
  concerts: 'Concerts',
  'social-gatherings': 'Social Gatherings',
};

export default function UnifiedEventsDirectory({ theme, onToggleTheme }) {
  const navigate = useNavigate();
  const { events: eventsByDate } = useEvents();

  const [activeCategory, setActiveCategory] = useState('all');
  const [isCategoryOverlayOpen, setIsCategoryOverlayOpen] = useState(false);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'split' | 'map'
  const [timeFilter, setTimeFilter] = useState('all');

  const [query, setQuery] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('q') || '';
  });
  const [budget, setBudget] = useState('All');
  const [area, setArea] = useState('All');

  const [selectedEvent, setSelectedEvent] = useState(null); // Full drawer
  const [focusedEventId, setFocusedEventId] = useState(null); // Active pin/card highlight
  const [visibleMapEventIds, setVisibleMapEventIds] = useState(null);
  const [filterByMapBounds, setFilterByMapBounds] = useState(false);

  const carouselRef = useRef(null);
  const mapViewRef = useRef(null);

  // Split view (list beside map) needs a wide screen. Drop back to the list
  // if the window shrinks below the lg breakpoint while it's open.
  useEffect(() => {
    const wide = window.matchMedia('(min-width: 1024px)');
    const onChange = () => {
      if (!wide.matches) setViewMode((mode) => (mode === 'split' ? 'grid' : mode));
    };
    onChange();
    wide.addEventListener('change', onChange);
    return () => wide.removeEventListener('change', onChange);
  }, []);

  // On phones the map sits below the filters; bring it into view when chosen.
  useEffect(() => {
    if (viewMode !== 'map' || !window.matchMedia('(max-width: 639px)').matches) return;
    const id = requestAnimationFrame(() => mapViewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    return () => cancelAnimationFrame(id);
  }, [viewMode]);

  const pageTitle = CATEGORY_TITLES[activeCategory] || 'All Experiences';

  const categoryEvents = useMemo(() => {
    if (activeCategory === 'all') return eventsByDate;
    return eventsByDate.filter((e) => e.category === activeCategory);
  }, [activeCategory, eventsByDate]);

  const AREA_OPTIONS = useMemo(
    () => [
      { value: 'All', label: 'All neighbourhoods' },
      ...[...new Set(categoryEvents.map((event) => event.area))].sort().map((a) => ({ value: a, label: a })),
    ],
    [categoryEvents],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (id) {
      const event = eventsByDate.find((e) => e.id === parseInt(id, 10));
      if (event) {
        setSelectedEvent(event);
        setFocusedEventId(event.id);
      }
    }
  }, [eventsByDate]);

  const closeEvent = useCallback(() => setSelectedEvent(null), []);

  // Only let map movement re-filter the list when "filter by map area" is on;
  // otherwise every pan would rebuild the list and re-trigger the map.
  const boundsIds = filterByMapBounds ? visibleMapEventIds : null;

  // Map reports the on-screen events after every move; skip the update when nothing changed.
  const handleBoundsChange = useCallback((ids) => {
    setVisibleMapEventIds((prev) =>
      prev && prev.length === ids.length && prev.every((id, i) => id === ids[i]) ? prev : ids,
    );
  }, []);

  const visibleEvents = useMemo(() => {
    const q = query.trim().toLowerCase();
    const range = timeWindow(timeFilter);
    return categoryEvents.filter((event) => {
      const basicMatch =
        matchesQuery(event, q) &&
        matchesBudget(event, budget) &&
        matchesArea(event, area) &&
        matchesTime(event, range);

      if (!basicMatch) return false;
      if (boundsIds && boundsIds.length > 0) {
        return boundsIds.includes(event.id);
      }
      return true;
    });
  }, [categoryEvents, query, budget, area, timeFilter, boundsIds]);

  // Compute live Chennai stats
  const stats = useMemo(() => {
    const areaCounts = {};
    visibleEvents.forEach((ev) => {
      areaCounts[ev.area] = (areaCounts[ev.area] || 0) + 1;
    });
    let topArea = 'Chennai';
    let maxCount = 0;
    Object.entries(areaCounts).forEach(([ar, cnt]) => {
      if (cnt > maxCount) {
        maxCount = cnt;
        topArea = ar;
      }
    });
    return {
      total: visibleEvents.length,
      areasCount: Object.keys(areaCounts).length,
      topArea: maxCount > 0 ? topArea : null,
      topCount: maxCount,
    };
  }, [visibleEvents]);

  const hasFilters =
    Boolean(query.trim()) ||
    budget !== 'All' ||
    area !== 'All' ||
    timeFilter !== 'all' ||
    activeCategory !== 'all' ||
    filterByMapBounds;

  const resetFilters = () => {
    setQuery('');
    setBudget('All');
    setArea('All');
    setTimeFilter('all');
    setActiveCategory('all');
    setFilterByMapBounds(false);
  };

  // Handler for pin click on map
  const handleMapPinSelect = useCallback((event) => {
    setFocusedEventId(event.id);
    if (viewMode === 'split') {
      const el = document.getElementById(`split-card-${event.id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [viewMode]);

  // Carousel scroll helpers for Map view
  const scrollCarousel = (direction) => {
    if (!carouselRef.current) return;
    const offset = direction === 'left' ? -320 : 320;
    carouselRef.current.scrollBy({ left: offset, behavior: 'smooth' });
  };

  // The active focused event object
  const focusedEvent = useMemo(() => {
    if (!focusedEventId) return visibleEvents[0] || null;
    return visibleEvents.find((e) => e.id === focusedEventId) || visibleEvents[0] || null;
  }, [focusedEventId, visibleEvents]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } }}
      exit={{ opacity: 0, y: 16, transition: { duration: 0.3, ease: 'easeIn' } }}
      className="min-h-svh"
    >
      <main className="mx-auto w-full px-4 pb-12 sm:px-6 sm:pb-24 lg:px-12 xl:px-16 2xl:px-24">
        {/* Header Section */}
        <section className="pb-5 pt-5 sm:pb-8 sm:pt-14">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="group inline-flex cursor-pointer items-center gap-3 text-sm transition-colors hover:text-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 dark:hover:text-teal-400"
            >
              <ArrowLeft
                className="size-4 transition-transform duration-300 group-hover:-translate-x-1"
                strokeWidth={1.25}
              />
              <span className="hidden sm:inline">Back to Home</span>
              <span className="sm:hidden">Back</span>
            </button>

            {/* View Mode Switcher */}
            <div className="flex items-center gap-1 rounded-sm border border-line p-1 bg-ink/[0.02] dark:bg-bone/[0.02] shadow-sm">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs sm:px-3.5 font-serif uppercase tracking-wider transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-ink text-ivory dark:bg-bone dark:text-ink font-semibold'
                    : 'text-muted hover:text-ink dark:hover:text-bone'
                }`}
              >
                <LayoutGrid className="size-3.5" />
                <span>List</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('split')}
                className={`hidden lg:flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs sm:px-3.5 font-serif uppercase tracking-wider transition-colors ${
                  viewMode === 'split'
                    ? 'bg-ink text-ivory dark:bg-bone dark:text-ink font-semibold'
                    : 'text-muted hover:text-ink dark:hover:text-bone'
                }`}
              >
                <Columns2 className="size-3.5" />
                <span className="hidden sm:inline">Split</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('map')}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs sm:px-3.5 font-serif uppercase tracking-wider transition-colors ${
                  viewMode === 'map'
                    ? 'bg-ink text-ivory dark:bg-bone dark:text-ink font-semibold'
                    : 'text-muted hover:text-ink dark:hover:text-bone'
                }`}
              >
                <MapIcon className="size-3.5" />
                <span>Map</span>
              </button>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-baseline justify-between gap-3 sm:mt-8 sm:gap-4">
            <div>
              <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.3em] text-muted">
                <span className="h-px w-8 bg-yellow-600 dark:bg-yellow-500" />
                Curated Chennai listings · 2026
              </p>
              <motion.h1
                key={pageTitle}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 font-display text-5xl leading-[0.85] uppercase tracking-[0.02em] sm:mt-4 sm:text-8xl"
              >
                {pageTitle}
              </motion.h1>
            </div>

            {/* Live Stats Badge */}
            <div className="flex items-center gap-3 border border-line px-3 py-2 text-xs italic text-muted sm:px-4">
              <Sparkles className="size-3.5 text-teal-600 dark:text-teal-400" />
              <span>
                <strong className="not-italic text-ink dark:text-bone">{stats.total}</strong> active listings across{' '}
                <strong className="not-italic text-ink dark:text-bone">{stats.areasCount}</strong> areas
                {stats.topArea && (
                  <>
                    {' · '}busiest: <span className="text-teal-700 dark:text-teal-400 not-italic font-semibold">{stats.topArea}</span>
                  </>
                )}
              </span>
            </div>
          </div>
        </section>

        {/* Filter Controls Bar */}
        <section aria-label="Filters" className="border-y border-line py-4 sm:py-5 transition-colors duration-200">
          <div className="flex flex-col gap-4 sm:gap-6 lg:flex-row lg:items-end lg:gap-8">
            <div className="flex items-end gap-3 lg:contents">
            <button
              onClick={() => setIsCategoryOverlayOpen(true)}
              className="group flex h-10 shrink-0 cursor-pointer items-center justify-center gap-2 border border-line bg-transparent px-3 font-serif sm:gap-3 sm:px-5 text-base italic text-ink transition-colors hover:border-teal-700 hover:text-teal-800 dark:text-bone dark:hover:border-teal-400 dark:hover:text-teal-300"
            >
              <Grid2X2 className="h-4 w-4 opacity-70 group-hover:opacity-100" strokeWidth={1.5} />
              Categories
              {activeCategory !== 'all' && (
                <span className="ml-1 size-2 rounded-full bg-teal-600 dark:bg-teal-400" />
              )}
            </button>

            {/* Search Input */}
            <label className="flex min-w-0 flex-1 items-center gap-3 border-b border-line pb-2 transition-colors duration-300 focus-within:border-teal-700 dark:focus-within:border-teal-400">
              <span className="sr-only">Search events</span>
              <Search className="size-4 shrink-0 text-muted" strokeWidth={1.25} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search events & venues"
                className="w-full bg-transparent py-1 outline-none placeholder:italic placeholder:text-muted"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="Clear search"
                  className="cursor-pointer text-muted transition-colors hover:text-ink dark:hover:text-bone"
                >
                  <X className="size-4" strokeWidth={1.25} />
                </button>
              )}
            </label>
            </div>

            {/* Time Filter Chips */}
            <div className="-mx-4 flex items-center gap-2 overflow-x-auto px-4 pb-1 no-scrollbar sm:mx-0 sm:px-0">
              {TIME_FILTERS.map((tf) => {
                const isActive = timeFilter === tf.id;
                return (
                  <button
                    key={tf.id}
                    type="button"
                    onClick={() => setTimeFilter(tf.id)}
                    className={`cursor-pointer whitespace-nowrap px-3 py-1.5 text-xs font-serif transition-colors border ${
                      isActive
                        ? 'border-teal-700 bg-teal-700/10 text-teal-800 dark:border-teal-400 dark:bg-teal-400/10 dark:text-teal-300 font-semibold'
                        : 'border-line text-muted hover:border-ink/40 dark:hover:border-bone/40'
                    }`}
                  >
                    {tf.label}
                  </button>
                );
              })}
            </div>

            {/* Select Dropdowns */}
            <div className="grid grid-cols-2 gap-x-5 gap-y-4 sm:flex sm:flex-wrap sm:items-end sm:gap-x-8">
              <div className="min-w-0 sm:w-36">
                <Select
                  label="Budget"
                  value={budget}
                  options={BUDGETS.map((name) => ({ value: name, label: name }))}
                  onChange={setBudget}
                />
              </div>

              <div className="min-w-0 sm:w-52">
                <Select label="Area" value={area} options={AREA_OPTIONS} onChange={setArea} />
              </div>
            </div>
          </div>
        </section>

        {/* Status Bar */}
        <div className="flex items-baseline justify-between gap-4 py-4 text-sm sm:py-5">
          <div className="flex items-center gap-4">
            <p className="italic text-muted">
              Showing <span className="not-italic tabular-nums text-ink dark:text-bone font-semibold">{visibleEvents.length}</span> of{' '}
              {categoryEvents.length} events
            </p>
            {viewMode === 'map' && (
              <label className="hidden sm:flex items-center gap-2 cursor-pointer text-xs text-muted hover:text-ink dark:hover:text-bone transition-colors ml-4 border-l border-line pl-4">
                <input
                  type="checkbox"
                  checked={filterByMapBounds}
                  onChange={(e) => setFilterByMapBounds(e.target.checked)}
                  className="size-3.5 accent-teal-600 cursor-pointer"
                />
                <span>Filter by map view</span>
              </label>
            )}
          </div>

          {hasFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="shrink-0 cursor-pointer underline decoration-line underline-offset-4 transition-colors hover:text-teal-700 hover:decoration-current dark:hover:text-teal-400 text-xs uppercase tracking-wider"
            >
              <span className="sm:hidden">Clear</span>
              <span className="hidden sm:inline">Clear all filters</span>
            </button>
          )}
        </div>

        {/* VIEW 1: Grid Mode */}
        {viewMode === 'grid' && (
          <motion.div
            layout
            className="relative grid grid-cols-3 gap-x-2.5 gap-y-4 sm:grid-cols-2 sm:gap-x-8 sm:gap-y-10 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"
          >
            <AnimatePresence mode="popLayout">
              {visibleEvents.map((event) => (
                <EventCard key={event.id} event={event} onSelect={setSelectedEvent} />
              ))}
            </AnimatePresence>
          </motion.div>
        )}

        {/* VIEW 2: Split Mode (List + Sticky Map with Interactive Sync) */}
        {viewMode === 'split' && (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-start">
            {/* Left side: Scrollable Event Cards */}
            <div className="space-y-4 lg:col-span-5 xl:col-span-5 max-h-[80vh] overflow-y-auto pr-3 no-scrollbar">
              {visibleEvents.map((event) => {
                const isFocused = focusedEventId === event.id;
                return (
                  <div
                    key={event.id}
                    id={`split-card-${event.id}`}
                    onClick={() => setFocusedEventId(event.id)}
                    className={`cursor-pointer group flex flex-col sm:flex-row gap-4 border p-4 transition-all ${
                      isFocused
                        ? 'border-teal-600 bg-teal-500/5 shadow-md dark:border-teal-400 dark:bg-teal-400/5'
                        : 'border-line hover:border-ink/40 dark:hover:border-bone/40 bg-ink/[0.015] dark:bg-bone/[0.015]'
                    }`}
                  >
                    {/* Poster Thumbnail */}
                    <div className="relative aspect-[4/3] sm:aspect-square sm:size-28 shrink-0 overflow-hidden bg-ink/10 dark:bg-bone/10">
                      <img
                        src={event.image_url}
                        alt={event.title}
                        className="size-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                      <span className="absolute bottom-1 left-1 bg-ink/80 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-ivory backdrop-blur-sm dark:bg-bone/80 dark:text-ink font-semibold">
                        {event.area}
                      </span>
                    </div>

                    {/* Card Info */}
                    <div className="flex flex-1 flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] uppercase tracking-wider font-semibold text-teal-700 dark:text-teal-400">
                            {event.category.replace('-', ' ')}
                          </span>
                          <span className="text-xs font-semibold tabular-nums text-muted">
                            {event.isFree ? 'Free' : `₹${event.price}`}
                          </span>
                        </div>

                        <h4 className="mt-1 font-display text-xl leading-snug tracking-wide group-hover:text-teal-700 dark:group-hover:text-teal-400 transition-colors line-clamp-2">
                          {event.title}
                        </h4>

                        <p className="mt-1 flex items-center gap-1.5 text-xs text-muted italic line-clamp-1">
                          <MapPin className="size-3 shrink-0" />
                          <span>{event.venue}</span>
                        </p>
                      </div>

                      <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-2 text-xs">
                        <span className="italic text-muted">
                          {formatDate(event.date)} · {formatTime(event.date)}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(event);
                          }}
                          className="flex items-center gap-1 text-[11px] uppercase tracking-wider font-semibold text-teal-700 hover:underline dark:text-teal-400"
                        >
                          <span>Details</span>
                          <ArrowUpRight className="size-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Right side: Sticky Live Interactive Map */}
            <div className="sticky top-28 h-[80vh] overflow-hidden border border-line lg:col-span-7 xl:col-span-7 shadow-xl">
              <ChennaiMap
                events={visibleEvents}
                selectedEventId={focusedEventId}
                onSelectEvent={handleMapPinSelect}
                onBoundsChange={handleBoundsChange}
                theme={theme}
                interactive={true}
              />
            </div>
          </div>
        )}

        {/* VIEW 3: Full Map View with Bottom Floating Carousel */}
        {viewMode === 'map' && (
          <div ref={mapViewRef} className="relative -mx-4 h-[calc(100svh-8.5rem-env(safe-area-inset-bottom))] scroll-mt-[3.75rem] overflow-hidden border-y border-line shadow-2xl sm:mx-0 sm:h-[82vh] sm:scroll-mt-0 sm:border">
            {/* The Full MapLibre Container */}
            <ChennaiMap
              events={visibleEvents}
              selectedEventId={focusedEventId}
              onSelectEvent={handleMapPinSelect}
              onBoundsChange={handleBoundsChange}
              theme={theme}
              interactive={true}
            />

            {/* Bottom Floating Carousel Drawer */}
            <div className="pointer-events-none absolute inset-x-0 bottom-3 z-20 px-3 sm:bottom-4 sm:px-8">
              <div className="pointer-events-auto mx-auto max-w-5xl rounded-sm border border-line bg-ivory/95 p-2.5 shadow-2xl sm:p-3 backdrop-blur-xl dark:bg-ink/95">
                <div className="flex items-center justify-between pb-2 px-1 text-xs uppercase tracking-widest text-muted border-b border-line mb-3">
                  <div className="flex items-center gap-2">
                    <span className="size-2 rounded-full bg-teal-500" />
                    <span>Chennai Radar Events ({visibleEvents.length})</span>
                  </div>
                  <div className="hidden items-center gap-1 sm:flex">
                    <button
                      type="button"
                      onClick={() => scrollCarousel('left')}
                      className="cursor-pointer p-1 hover:text-ink dark:hover:text-bone transition-colors"
                      title="Previous"
                    >
                      <ChevronLeft className="size-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollCarousel('right')}
                      className="cursor-pointer p-1 hover:text-ink dark:hover:text-bone transition-colors"
                      title="Next"
                    >
                      <ChevronRight className="size-4" />
                    </button>
                  </div>
                </div>

                {/* Horizontal Scroll Cards */}
                <div
                  ref={carouselRef}
                  className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-1 no-scrollbar scroll-smooth sm:gap-4"
                >
                  {visibleEvents.map((event) => {
                    const isFocused = focusedEventId === event.id;
                    return (
                      <div
                        key={event.id}
                        onClick={() => setFocusedEventId(event.id)}
                        className={`cursor-pointer group flex w-[78vw] max-w-[320px] shrink-0 snap-start gap-3 border p-3 transition-all sm:w-auto sm:min-w-[280px] ${
                          isFocused
                            ? 'border-teal-600 bg-teal-500/10 dark:border-teal-400 dark:bg-teal-400/10 shadow-sm'
                            : 'border-line hover:border-ink/40 dark:hover:border-bone/40 bg-ink/[0.02] dark:bg-bone/[0.02]'
                        }`}
                      >
                        <div className="size-18 shrink-0 overflow-hidden bg-ink/10 dark:bg-bone/10">
                          <img
                            src={event.image_url}
                            alt={event.title}
                            className="size-full object-cover transition-transform group-hover:scale-105"
                          />
                        </div>

                        <div className="flex flex-1 flex-col justify-between min-w-0">
                          <div>
                            <div className="flex items-center justify-between text-[10px] text-muted uppercase tracking-wider">
                              <span className="text-teal-700 dark:text-teal-400 font-semibold truncate">
                                {event.area}
                              </span>
                              <span>{event.isFree ? 'Free' : `₹${event.price}`}</span>
                            </div>
                            <h5 className="font-display text-base leading-tight tracking-wide group-hover:text-teal-700 dark:group-hover:text-teal-400 transition-colors line-clamp-1 mt-0.5">
                              {event.title}
                            </h5>
                          </div>

                          <div className="mt-2 flex items-center justify-between text-[11px]">
                            <span className="italic text-muted">{formatDate(event.date)}</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedEvent(event);
                              }}
                              className="font-semibold uppercase tracking-wider text-teal-700 hover:underline dark:text-teal-400"
                            >
                              Open
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
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

      {/* Category Overlay */}
      <AnimatePresence>
        {isCategoryOverlayOpen && (
          <CategoryBentoOverlay
            onSelectCategory={(categoryId) => setActiveCategory(categoryId)}
            onClose={() => setIsCategoryOverlayOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Event Details Drawer */}
      {createPortal(
        <AnimatePresence>
          {selectedEvent && <EventDrawer key={selectedEvent.id} event={selectedEvent} onClose={closeEvent} />}
        </AnimatePresence>,
        document.body,
      )}
    </motion.div>
  );
}
