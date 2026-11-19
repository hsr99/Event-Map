const TIME_ZONE = 'Asia/Kolkata';

const shortDate = new Intl.DateTimeFormat('en-IN', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  timeZone: TIME_ZONE,
});
const longDate = new Intl.DateTimeFormat('en-IN', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: TIME_ZONE,
});
const time = new Intl.DateTimeFormat('en-IN', {
  hour: 'numeric',
  minute: '2-digit',
  timeZone: TIME_ZONE,
});

// Intl throws on an invalid date, which would take the whole page down; show nothing instead.
const safe = (formatter) => (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : formatter.format(d);
};

export const formatDate = safe(shortDate);
export const formatLongDate = safe(longDate);
export const formatTime = safe(time);
export const formatTimeRange = (start, end) => {
  const from = formatTime(start);
  const to = formatTime(end);
  if (!to) return from;
  // Multi-day events: show the end date too.
  const endDay = formatDate(end);
  return endDay && endDay !== formatDate(start) ? `${from} - ${endDay}, ${to}` : `${from} - ${to}`;
};
export const formatPrice = (event) => (event.isFree ? 'Free' : `₹${event.price.toLocaleString('en-IN')}`);
