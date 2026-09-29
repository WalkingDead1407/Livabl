import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Neighborhood } from '../types';
import { getScoreColor } from '../utils';
import { fetchNeighbourhoodBoundaries, type OsmPolygon } from '../api/overpass';

interface LiveMapProps {
  neighborhoods: Neighborhood[];
  selected: Neighborhood | null;
  onSelect: (n: Neighborhood) => void;
  theme: 'light' | 'dark';
}

function getWardColor(score: number): string {
  if (score >= 68) return '#16a34a';
  if (score >= 45) return '#d97706';
  return '#dc2626';
}

function getTileUrl(theme: 'light' | 'dark'): string {
  return theme === 'dark'
    ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`
    : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
}

function createTileLayer(theme: 'light' | 'dark'): L.TileLayer {
  const options: L.TileLayerOptions = {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  };

  if (theme === 'dark') {
    options.subdomains = 'abcd';
  }

  return L.tileLayer(getTileUrl(theme), options);
}

export default function LiveMap({ neighborhoods, selected, onSelect, theme }: LiveMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<string, L.Marker>>({});
  const polygonsRef = useRef<L.Polygon[]>([]);
  const polygonsByWardRef = useRef<Record<string, L.Polygon[]>>({});
  const wardColorByIdRef = useRef<Record<string, string>>({});
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [wardsLoaded, setWardsLoaded] = useState(false);

  // Initialize map once
  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    // React strict mode may remount before Leaflet fully cleans the DOM node.
    delete (container as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;

    const map = L.map(container, {
      center: [28.6139, 77.2090],
      zoom: 11,
      zoomControl: false,
    });
    const tileLayer = createTileLayer(theme).addTo(map);
    tileLayerRef.current = tileLayer;
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      tileLayerRef.current = null;
      delete (container as HTMLDivElement & { _leaflet_id?: number })._leaflet_id;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    tileLayerRef.current?.remove();
    tileLayerRef.current = createTileLayer(theme).addTo(map);
  }, [theme]);

  // Draw real Delhi ward boundaries
  useEffect(() => {
    const map = mapRef.current;
    if (!map || wardsLoaded || neighborhoods.length === 0) return;

    let cancelled = false;
    const neighborhoodByName = new Map(
      neighborhoods.map((n) => [n.name.trim().toLowerCase(), n]),
    );

    fetchNeighbourhoodBoundaries()
      .then((wards: OsmPolygon[]) => {
        if (cancelled) return;

        polygonsRef.current.forEach((p) => p.remove());
        polygonsRef.current = [];
        polygonsByWardRef.current = {};
        wardColorByIdRef.current = {};

        wards.forEach((ward) => {
          const color = getWardColor(ward.score);
          const matchedNeighborhood = neighborhoodByName.get(
            ward.name.trim().toLowerCase(),
          );
          const wardKey = matchedNeighborhood?.id ?? ward.name.trim().toLowerCase();
          wardColorByIdRef.current[wardKey] = color;

          ward.coordinates.forEach((ring) => {
            if (ring.length < 3) return;
            const polygon = L.polygon(ring, {
              color,
              fillColor: color,
              fillOpacity: 0.12,
              weight: 0.8,
              opacity: 0.5,
            });

            if (matchedNeighborhood) {
              polygon.on('click', () => onSelect(matchedNeighborhood));
            }

            polygon.addTo(map);
            polygonsRef.current.push(polygon);
            polygonsByWardRef.current[wardKey] ??= [];
            polygonsByWardRef.current[wardKey].push(polygon);
          });
        });

        setWardsLoaded(true);
      })
      .catch((err) => {
        console.warn("[Wards] Failed to draw ward boundaries:", err);
      });

    return () => {
      cancelled = true;
    };
  }, [wardsLoaded, neighborhoods, onSelect, theme]);

  useEffect(() => {
    Object.entries(polygonsByWardRef.current).forEach(([wardId, polygons]) => {
      const isSelected = selected?.id === wardId;
      const baseColor = wardColorByIdRef.current[wardId] ?? '#d97706';
      polygons.forEach((polygon) => {
        polygon.setStyle({
          weight: isSelected ? 2.2 : 0.8,
          opacity: isSelected ? 0.95 : 0.5,
          fillOpacity: isSelected ? 0.2 : 0.12,
          color: baseColor,
          fillColor: baseColor,
        });
        if (isSelected) {
          polygon.bringToFront();
        }
      });
    });
  }, [selected]);

  // Add score pins for our key neighborhoods
  useEffect(() => {
    const map = mapRef.current;
    if (!map || neighborhoods.length === 0) return;

    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    neighborhoods.forEach((n) => {
      const color = getScoreColor(n.score);
      const isSelected = selected?.id === n.id;

      const selectedMarkerBg = theme === 'dark' ? '#f3f4ef' : '#1a1a18';
      const selectedMarkerText = theme === 'dark' ? '#171b1f' : '#ffffff';
      const markerBorder = theme === 'dark' ? '#171b1f' : '#ffffff';

      const icon = L.divIcon({
        className: '',
        html: `<div style="
          width: ${isSelected ? 40 : 30}px;
          height: ${isSelected ? 40 : 30}px;
          border-radius: 50%;
          background: ${isSelected ? selectedMarkerBg : color};
          border: 2.5px solid ${markerBorder};
          display: flex; align-items: center; justify-content: center;
          font-family: 'DM Mono', monospace;
          font-size: ${isSelected ? 12 : 10}px;
          font-weight: 500; color: ${isSelected ? selectedMarkerText : 'white'};
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          cursor: pointer;
        ">${n.score}</div>`,
        iconSize: [isSelected ? 40 : 30, isSelected ? 40 : 30],
        iconAnchor: [isSelected ? 20 : 15, isSelected ? 20 : 15],
      });

      const marker = L.marker([n.coordinates.lat, n.coordinates.lng], {
        icon, zIndexOffset: 1000,
      });

      marker.bindPopup(L.popup({ closeButton: false, offset: [0, -12] })
        .setContent(`
          <div style="font-family:'DM Sans',sans-serif;padding:4px;min-width:150px;color:${theme === 'dark' ? '#f3f4ef' : '#1a1a18'};">
            <div style="font-size:13px;font-weight:600;margin-bottom:4px;">${n.name}</div>
            <div style="font-size:11px;color:${theme === 'dark' ? '#b5b8b0' : '#6b6b64'};margin-bottom:6px;">${n.region}</div>
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px;">
              <span style="color:${theme === 'dark' ? '#b5b8b0' : '#6b6b64'};">Hospital Score</span>
              <span style="font-family:'DM Mono',monospace;">${n.breakdown.hospital_score}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px;">
              <span style="color:${theme === 'dark' ? '#b5b8b0' : '#6b6b64'};">School Score</span>
              <span style="font-family:'DM Mono',monospace;">${n.breakdown.school_score}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;">
              <span style="color:${theme === 'dark' ? '#b5b8b0' : '#6b6b64'};">Pollution Score</span>
              <span style="font-family:'DM Mono',monospace;">${n.breakdown.pollution_score}</span>
            </div>
          </div>
        `));

      marker.on('mouseover', () => marker.openPopup());
      marker.on('mouseout', () => marker.closePopup());
      marker.on('click', () => onSelect(n));
      marker.addTo(map);
      markersRef.current[n.id] = marker;
    });
  }, [neighborhoods, selected, onSelect, theme]);

  // Fly to selected neighborhood
  useEffect(() => {
    if (!mapRef.current || !selected) return;
    mapRef.current.flyTo(
      [selected.coordinates.lat, selected.coordinates.lng],
      13, { duration: 1 }
    );
  }, [selected]);

  return (
    <div className="map-area">
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
