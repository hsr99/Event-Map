export default function EventImage({ event, className = '', imgClassName = '' }) {
  return (
    <div className={`relative overflow-hidden bg-ink/[0.04] dark:bg-bone/[0.04] ${className}`}>
      <span
        aria-hidden
        className="absolute inset-0 grid place-items-center font-display text-6xl tracking-wider text-ink/10 dark:text-bone/10"
      >
        {event.category}
      </span>
      <img
        src={event.image_url}
        alt={event.title}
        loading="lazy"
        onError={(e) => {
          e.currentTarget.style.visibility = 'hidden';
        }}
        className={`relative size-full object-cover ${imgClassName}`}
      />
    </div>
  );
}
