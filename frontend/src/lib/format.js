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

export const formatDate = (iso) => shortDate.format(new Date(iso));
export const formatLongDate = (iso) => longDate.format(new Date(iso));
export const formatTime = (iso) => time.format(new Date(iso));
export const formatTimeRange = (start, end) => `${formatTime(start)} - ${formatTime(end)}`;
export const formatPrice = (event) => (event.isFree ? 'Free' : `₹${event.price.toLocaleString('en-IN')}`);
