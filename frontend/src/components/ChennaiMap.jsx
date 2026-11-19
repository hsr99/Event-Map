import { useEffect, useRef, useState, useCallback } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { LocateFixed } from 'lucide-react';
import { formatPrice, formatDate, formatTime } from '../lib/format';

// Category color accents matching the site's palette
const CATEGORY_COLORS = {
  concerts: '#eab308', // Gold
  'tech-events': '#2dd4bf', // Teal
  'college-culturals': '#f43f5e', // Rose
  'social-gatherings': '#34d399', // Emerald
  movies: '#38bdf8', // Sky
  default: '#2dd4bf',
};

// MapLibre locates its worker relative to its own bundle, which Vite relocates
// (dev pre-bundling and production builds). Without the worker, GeoJSON sources
// never load, so no event pins appear. Point it at the real file explicitly.
maplibregl.setWorkerUrl(maplibreWorkerUrl);

const CHENNAI_CENTER = [80.24, 13.04]; // [lng, lat]
const CHENNAI_BOUNDS = [
  [80.05, 12.80], // Southwest coords
  [80.35, 13.25], // Northeast coords
];

// Phones show a narrow slice of the city, so start one step further out.
const defaultZoom = () =>
  typeof window !== 'undefined' && window.matchMedia('(max-width: 639px)').matches ? 10.6 : 11.5;

export default function ChennaiMap({
  events = [],
  selectedEventId = null,
  onSelectEvent,
  theme = 'dark',
  className = '',
  interactive = true,
  onBoundsChange,
}) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);
  const selectedMarkerRef = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const isDark = theme === 'dark';

  // Construct MapLibre style with clean ESRI Dark/Light Gray Canvas tiles (no API key required)
  const getMapStyle = useCallback((dark) => {
    const themeName = dark ? 'Dark' : 'Light';
    return {
      version: 8,
      sources: {
        'esri-base': {
          type: 'raster',
          tiles: [
            `https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_${themeName}_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
          ],
          tileSize: 256,
          attribution:
            '&copy; <a href="https://www.esri.com">Esri</a> &copy; OpenStreetMap contributors',
        },
        'esri-labels': {
          type: 'raster',
          tiles: [
            `https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_${themeName}_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
          ],
          tileSize: 256,
        },
      },
      layers: [
        {
          id: 'esri-base-layer',
          type: 'raster',
          source: 'esri-base',
          minzoom: 0,
          maxzoom: 20,
        },
        {
          id: 'esri-labels-layer',
          type: 'raster',
          source: 'esri-labels',
          minzoom: 0,
          maxzoom: 20,
        },
      ],
    };
  }, []);

  // Initialize Map
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle(isDark),
      center: CHENNAI_CENTER,
      zoom: defaultZoom(),
      minZoom: 9.5,
      maxZoom: 18,
      maxBounds: CHENNAI_BOUNDS,
      attributionControl: false,
    });

    if (interactive) {
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    }

    map.on('load', () => {
      setMapLoaded(true);
    });

    mapRef.current = map;

    return () => {
      if (selectedMarkerRef.current) {
        selectedMarkerRef.current.remove();
        selectedMarkerRef.current = null;
      }
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update style when theme changes
  useEffect(() => {
    if (!mapRef.current || !mapLoaded) return;
    mapRef.current.setStyle(getMapStyle(isDark));
  }, [isDark, mapLoaded, getMapStyle]);

  // Convert events to GeoJSON
  const geojson = {
    type: 'FeatureCollection',
    features: events
      .filter((e) => typeof e.lat === 'number' && typeof e.lng === 'number')
      .map((e) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [e.lng, e.lat],
        },
        properties: {
          id: e.id,
          title: e.title,
          category: e.category,
          area: e.area,
          venue: e.venue,
          date: e.date,
          price: e.price,
          isFree: e.isFree,
          image_url: e.image_url,
          color: CATEGORY_COLORS[e.category] || CATEGORY_COLORS.default,
        },
      })),
  };

  // Add / update GeoJSON source & layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const addEventLayers = () => {
      if (map.getSource('events-source')) {
        map.getSource('events-source').setData(geojson);
        return;
      }

      map.addSource('events-source', {
        type: 'geojson',
        data: geojson,
      });

      // Layer 1: Selected / Active Marker Pulsing Halo
      map.addLayer({
        id: 'selected-halo',
        type: 'circle',
        source: 'events-source',
        filter: ['==', ['get', 'id'], selectedEventId || -1],
        paint: {
          'circle-radius': 28,
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.45,
          'circle-stroke-width': 2.5,
          'circle-stroke-color': ['get', 'color'],
        },
      });

      // Layer 2: Outer glow halo
      map.addLayer({
        id: 'events-glow',
        type: 'circle',
        source: 'events-source',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            10, 12,
            14, 22,
            18, 36,
          ],
          'circle-color': ['get', 'color'],
          'circle-opacity': isDark ? 0.4 : 0.28,
          'circle-blur': 0.85,
        },
      });

      // Layer 3: Middle stroke ring
      map.addLayer({
        id: 'events-ring',
        type: 'circle',
        source: 'events-source',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            10, 6,
            14, 10,
            18, 16,
          ],
          'circle-color': 'transparent',
          'circle-stroke-width': 2,
          'circle-stroke-color': ['get', 'color'],
          'circle-stroke-opacity': 0.9,
        },
      });

      // Layer 4: Solid vibrant core
      map.addLayer({
        id: 'events-core',
        type: 'circle',
        source: 'events-source',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            10, 4.5,
            14, 7,
            18, 12,
          ],
          'circle-color': ['get', 'color'],
          'circle-opacity': 1,
        },
      });

      // Hover popup interaction
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 14,
        className: 'jarvis-map-popup',
      });
      popupRef.current = popup;

      map.on('mouseenter', 'events-core', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const coordinates = e.features[0].geometry.coordinates.slice();
        const props = e.features[0].properties;

        const isFree = props.isFree === true || props.isFree === 'true';
        const priceLabel = isFree ? 'Free' : `₹${Number(props.price || 0).toLocaleString('en-IN')}`;

        const html = `
          <div style="font-family: inherit; padding: 4px; min-width: 170px;">
            <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; color: ${props.color}; font-weight: 600;">
              ${props.category.replace('-', ' ')} · ${props.area}
            </div>
            <div style="font-size: 14px; font-weight: 700; margin: 3px 0 2px; color: ${isDark ? '#ede9dd' : '#121212'}; line-height: 1.2;">
              ${props.title}
            </div>
            <div style="font-size: 11px; opacity: 0.7; color: ${isDark ? '#ede9dd' : '#121212'};">
              ${formatDate(props.date)} · ${formatTime(props.date)}
            </div>
            <div style="margin-top: 6px; font-size: 12px; font-weight: 600; color: ${isFree ? '#2dd4bf' : '#eab308'};">
              ${priceLabel}
            </div>
          </div>
        `;

        popup.setLngLat(coordinates).setHTML(html).addTo(map);
      });

      map.on('mouseleave', 'events-core', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });

      // Click event on map marker dot
      map.on('click', 'events-core', (e) => {
        if (!e.features || !e.features.length) return;
        const id = Number(e.features[0].properties.id);
        const event = events.find((item) => item.id === id);
        if (event) {
          if (onSelectEvent) onSelectEvent(event);
        }
      });
    };

    if (map.isStyleLoaded()) {
      addEventLayers();
    } else {
      map.once('style.load', addEventLayers);
    }
  }, [events, mapLoaded, isDark, onSelectEvent]);

  // Update selected halo filter
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !map.getLayer('selected-halo')) return;
    map.setFilter('selected-halo', ['==', ['get', 'id'], selectedEventId || -1]);
  }, [selectedEventId, mapLoaded]);

  // Sync visible events when map bounds change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !onBoundsChange || !mapLoaded) return;

    const handleMoveEnd = () => {
      const bounds = map.getBounds();
      const visible = events.filter((e) => {
        if (typeof e.lat !== 'number' || typeof e.lng !== 'number') return false;
        return bounds.contains([e.lng, e.lat]);
      });
      onBoundsChange(visible.map((e) => e.id));
    };

    map.on('moveend', handleMoveEnd);
    return () => {
      map.off('moveend', handleMoveEnd);
    };
  }, [events, onBoundsChange, mapLoaded]);

  // Dynamic Pin Pointer & Smooth Zoom-in to Event Location
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // Clean up existing pointer marker
    if (selectedMarkerRef.current) {
      selectedMarkerRef.current.remove();
      selectedMarkerRef.current = null;
    }

    if (!selectedEventId) return;

    const ev = events.find((e) => e.id === selectedEventId);
    if (!ev || typeof ev.lat !== 'number' || typeof ev.lng !== 'number') return;

    const venueShort = (ev.venue || '').split(',')[0].trim();
    const color = CATEGORY_COLORS[ev.category] || CATEGORY_COLORS.default;

    // Create custom DOM Pin Element with pointer stem and pulse
    const el = document.createElement('div');
    el.className = 'jarvis-pointer-marker cursor-pointer select-none';
    el.style.zIndex = '35';
    el.innerHTML = `
      <div style="display: flex; flex-direction: column; align-items: center; transform: translate(0, -10px); filter: drop-shadow(0 6px 12px rgba(0,0,0,0.45));">
        <!-- Floating Label Badge -->
        <div style="
          background: ${isDark ? '#141414' : '#fffff5'};
          color: ${isDark ? '#f4f0e6' : '#111111'};
          border: 1.5px solid ${color};
          border-radius: 4px;
          padding: 3px 8px;
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
          letter-spacing: 0.05em;
          margin-bottom: 3px;
          display: flex;
          align-items: center;
          gap: 5px;
        ">
          <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ${color};"></span>
          <span>${ev.area} · ${venueShort}</span>
        </div>

        <!-- Teardrop Pin Head & Pulse Beacon -->
        <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
          <div style="
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background: ${color};
            opacity: 0.35;
            animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
          "></div>
          <div style="
            position: relative;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: ${color};
            border: 2px solid ${isDark ? '#121212' : '#ffffff'};
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            <svg viewBox="0 0 24 24" style="width: 15px; height: 15px; fill: ${isDark ? '#121212' : '#ffffff'};">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
          </div>
        </div>

        <!-- Pin Tail Arrow pointing straight at GPS lat/lng -->
        <div style="
          width: 0;
          height: 0;
          border-left: 5px solid transparent;
          border-right: 5px solid transparent;
          border-top: 7px solid ${color};
          margin-top: -2px;
        "></div>
      </div>
    `;

    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (onSelectEvent) onSelectEvent(ev);
    });

    const marker = new maplibregl.Marker({
      element: el,
      anchor: 'bottom',
    })
      .setLngLat([ev.lng, ev.lat])
      .addTo(map);

    selectedMarkerRef.current = marker;

    // Fast, snappy camera transition directly to the venue (350ms ease)
    map.easeTo({
      center: [ev.lng, ev.lat],
      zoom: 14.8,
      duration: 350,
      essential: true,
    });
  }, [selectedEventId, events, mapLoaded, isDark, onSelectEvent]);

  const handleRecenter = () => {
    if (!mapRef.current) return;
    mapRef.current.flyTo({
      center: CHENNAI_CENTER,
      zoom: defaultZoom(),
      speed: 1.4,
    });
  };

  return (
    <div className={`relative size-full overflow-hidden ${className}`}>
      <div ref={mapContainer} className="size-full" />

      {/* City Indicator Badge */}
      <div className="pointer-events-none absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full border border-line bg-ivory/85 px-3 py-1 text-[11px] uppercase tracking-wider backdrop-blur-md dark:bg-ink/85 text-muted shadow-sm">
        <span className="size-2 rounded-full bg-teal-500 animate-pulse" />
        <span className="hidden sm:inline">Chennai Radar ({events.length} active)</span>
        <span className="sm:hidden">{events.length} live</span>
      </div>

      {/* Recenter Button */}
      <button
        type="button"
        onClick={handleRecenter}
        title="Recenter Chennai"
        className="cursor-pointer absolute left-4 bottom-4 z-10 flex items-center gap-1.5 rounded-sm border border-line bg-ivory/90 px-2.5 py-1.5 text-xs font-serif text-ink backdrop-blur-md transition-colors hover:border-teal-700 dark:bg-ink/90 dark:text-bone dark:hover:border-teal-400 shadow-sm"
      >
        <LocateFixed className="size-3.5 text-teal-600 dark:text-teal-400" />
        <span className="hidden sm:inline">Recenter</span>
      </button>
    </div>
  );
}
