import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Circle,
  Polyline,
  Popup,
  Marker,
  useMap,
  useMapEvents,
} from "react-leaflet";
import jsPDF from "jspdf";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";

const API =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:5000";

const DEFAULTS = {
  lat: 18.75,
  lon: 72.65,
  time: "2026-08-14T23:59:59Z",
  hours: 48,
};

const WINDOW_PRESETS = [6, 12, 24, 48];
const MAX_VISIBLE_CANDIDATES = 5;

function Icon({ name, size = 17 }) {
  const p = {
    viewBox: "0 0 24 24",
    width: size,
    height: size,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  const paths = {
    radar: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 4v8l5 3"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    vessel: <><path d="M4 16h16l-2-7H6l-2 7Z"/><path d="M8 9V6h8v3M5 19c2 1 4 1 7 0 3 1 5 1 7 0"/></>,
    chart: <><path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 5-7"/></>,
    report: <><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.2-1.7l2-1.5-2-3.4-2.4 1a7 7 0 0 0-2.8-1.6L13.4 2h-4l-.3 2.8A7 7 0 0 0 6.3 6.4l-2.4-1-2 3.4 2 1.5A7 7 0 0 0 3.7 12c0 .6.1 1.2.2 1.7l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 2.8 1.6l.3 2.8h4l.3-2.8a7 7 0 0 0 2.8-1.6l2.4 1 2-3.4-2-1.5c.1-.5.2-1.1.2-1.7Z"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    target: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></>,
    play: <path d="m9 6 10 6-10 6V6Z"/>,
    pause: <><path d="M8 6v12M16 6v12"/></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5M4 20h16"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    alert: <><path d="M12 3 21 20H3L12 3Z"/><path d="M12 9v5M12 17h.01"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    chevron: <path d="m9 6 6 6-6 6"/>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    mapPin: <><path d="M12 21s7-6.2 7-12A7 7 0 1 0 5 9c0 5.8 7 12 7 12Z"/><circle cx="12" cy="9" r="2.3"/></>,
    expand: <><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5"/></>,
  };
  return <svg {...p}>{paths[name] || paths.target}</svg>;
}

function MapViewStyles() {
  return (
    <style>{`
      .basemap-switch {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        padding: 2px;
        border: 1px solid rgba(71, 126, 139, .38);
        border-radius: 7px;
        background: rgba(5, 18, 24, .82);
      }
      .basemap-switch button {
        border: 0;
        border-radius: 5px;
        background: transparent;
        color: #7f9ca6;
        font: 700 9px/1.2 inherit;
        letter-spacing: .12em;
        padding: 7px 8px;
        cursor: pointer;
      }
      .basemap-switch button:hover,
      .basemap-switch button.active {
        color: #071317;
        background: #28d1c5;
      }
      .sar-preview-empty {
        min-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        color: #8aa5ad;
        border: 1px dashed rgba(111, 155, 164, .3);
        background: rgba(2, 12, 17, .55);
        font-size: 11px;
      }
      .legend-basemap {
        opacity: .85;
        letter-spacing: .08em;
      }
      .sb-map-wrap.selecting .leaflet-container {
        cursor: crosshair !important;
      }
    `}</style>
  );
}

function num(v, digits = 2) {
  if (v === null || v === undefined || v === "") return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function fmt(v, digits = 1, suffix = "") {
  const x = num(v, digits);
  return x === null ? "—" : `${x.toFixed(digits)}${suffix}`;
}

function first(...values) {
  return values.find((v) => v !== undefined && v !== null && v !== "");
}

function utc(v) {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? String(v)
    : d.toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function assessmentTone(value) {
  const s = String(value || "").toUpperCase();
  if (s.includes("INTENTIONAL")) return "risk";
  if (s.includes("INVESTIGATION")) return "watch";
  if (s.includes("ACCIDENTAL")) return "info";
  return "neutral";
}

function normalize(result) {
  const rows = Array.isArray(result?.candidates) ? result.candidates : [];
  const candidates = rows.map((row, i) => {
    const c = row?.candidate || {};
    const vessels = Array.isArray(row?.nearby_vessels)
      ? row.nearby_vessels
      : [];
    return {
      ...c,
      environmental_hindcast: row?.environmental_hindcast || null,
      index: i + 1,
      lat: num(first(c.latitude, c.lat)),
      lon: num(first(c.longitude, c.lon)),
      area: num(first(c.area_pixels, c.candidate_pixel_count)),
      contrast: num(first(c.local_contrast_db)),
      median: num(first(c.candidate_median_db)),
      vessels: vessels
        .map((v) => {
          const inv = v?.investigation || {};
          const tl = v?.timeline || {};
          return {
            ...v,
            name: first(v.name, `Candidate vessel ${i + 1}`),
            mmsi: first(v.mmsi, "—"),
            lat: num(first(v.latitude, v.lat)),
            lon: num(first(v.longitude, v.lon)),
            score: num(first(v.responsibility_score)),
            correlation: num(first(v.correlation_score)),
            distance: num(first(v.distance_km)),
            reliability: num(first(v.ais_reliability)),
            gap: num(first(tl.ais_gap_hours, inv.ais_gap_hours, v.ais_gap_hours)),
            sourceDistance: num(first(inv.source_distance_km)),
            evidence: num(first(inv.evidence_score)),
            reachable: Boolean(inv.physically_reachable),
            trajectory: Boolean(tl.trajectory_compatible),
            anomaly: Boolean(inv.kinematic_anomaly),
            priority: first(inv.priority, "REVIEW"),
            assessment: first(inv.assessment, "INVESTIGATION REVIEW"),
            flags: Array.isArray(inv.flags) ? inv.flags : [],
            last: tl.last_known_position || null,
            next: tl.next_known_position || null,
            historical: inv.estimated_historical_position || null,
          };
        })
        .sort((a, b) => (b.score ?? -1) - (a.score ?? -1)),
    };
  });
  return { ...result, candidates };
}

function MapFocus({ point }) {
  const map = useMap();
  React.useEffect(() => {
    if (point?.lat == null || point?.lon == null) return;
    map.flyTo([Number(point.lat), Number(point.lon)], 11, { duration: 0.65 });
}, [point?.lat, point?.lon, point?.token, map]);
  return null;
}

function MapClickHandler({ onSelect, enabled }) {
  useMapEvents({
    click(event) {
      if (!enabled) return;
      onSelect(Number(event.latlng.lat.toFixed(5)), Number(event.latlng.lng.toFixed(5)));
    },
  });
  return null;
}

function VesselMarkerIcon({ selected = false, heading = 0, historical = false }) {
  const rotation = Number.isFinite(Number(heading)) ? Number(heading) : 0;
  return L.divIcon({
    className: "slickback-vessel-icon",
    html: `
      <div class="slickback-vessel-glyph ${selected ? "selected" : ""} ${historical ? "historical" : ""}" title="AIS vessel" style="transform:rotate(${rotation}deg)">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d="M16 3 25 24l-9-4-9 4L16 3Z"/>
          <path d="M11 25h10M8 28h16"/>
        </svg>
      </div>`,
    iconSize: selected ? [34, 34] : [28, 28],
    iconAnchor: selected ? [17, 17] : [14, 14],
  });
}

function loadImageDataUrl(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      context.drawImage(image, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };
    image.onerror = reject;
    image.src = url;
  });
}

function Metric({ label, value, accent = false }) {
  return (
    <div className={`metric ${accent ? "metric-accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EvidenceBar({ label, value, note }) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="evidence-bar">
      <div className="bar-head">
        <span>{label}</span>
        <strong>{note ?? `${safe.toFixed(0)}%`}</strong>
      </div>
      <div className="bar-track"><i style={{ width: `${safe}%` }} /></div>
    </div>
  );
}

function App() {
  const [lat, setLat] = useState(DEFAULTS.lat);
  const [lon, setLon] = useState(DEFAULTS.lon);
  const [time, setTime] = useState(DEFAULTS.time);
  const [hours, setHours] = useState(DEFAULTS.hours);
  const [data, setData] = useState(null);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [vesselIndex, setVesselIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [layers, setLayers] = useState({
    candidates: true,
    vessels: true,
    source: true,
    radius: true,
    route: true,
  });
  const [layersOpen, setLayersOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [rewindHour, setRewindHour] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [search, setSearch] = useState("");
  const [focusPoint, setFocusPoint] = useState(null);
  const [mapSelectedPoint, setMapSelectedPoint] = useState(null);
  const [mapSelectMode, setMapSelectMode] = useState(false);
  const [basemap, setBasemap] = useState("satellite");
  const [sarImageFailed, setSarImageFailed] = useState(false);
  const [sarPreviewIndex, setSarPreviewIndex] = useState(0);

  const model = useMemo(() => (data ? normalize(data) : null), [data]);
  const sarPreviewCandidates = useMemo(() => {
    if (!data) return [];

    const rawValues = [
      data?.satellite?.image_path,
      data?.satellite?.preview_path,
      data?.satellite?.image_url,
      data?.satellite?.image,
      data?.analysis?.satellite?.image_path,
      data?.analysis?.satellite?.preview_path,
      data?.analysis?.satellite?.image_url,
      data?.analysis?.image_path,
      data?.analysis?.preview_path,
    ];

    const urls = rawValues
      .filter((value) => value !== undefined && value !== null && String(value).trim() !== "")
      .map((value) => {
        const raw = String(value).trim();

        if (/^https?:\/\//i.test(raw)) {
          return `${raw}${raw.includes("?") ? "&" : "?"}analysis=${encodeURIComponent(data?.analysis_id || Date.now())}`;
        }

        const clean = raw.replace(/\\/g, "/").replace(/^\.\//, "");
        let relative;

        if (clean.startsWith("/analysis-files/")) {
          relative = clean;
        } else if (clean.includes("analysis-files/")) {
          relative = `/${clean.substring(clean.indexOf("analysis-files/"))}`;
        } else {
          const filename = clean.split("/").filter(Boolean).pop();
          relative = filename ? `/analysis-files/${filename}` : null;
        }

        if (!relative) return null;

        return `${API}${relative}${relative.includes("?") ? "&" : "?"}analysis=${encodeURIComponent(data?.analysis_id || Date.now())}`;
      })
      .filter(Boolean);

    return [...new Set(urls)];
  }, [data]);

  const sarPreviewUrl = sarPreviewCandidates[sarPreviewIndex] || null;

  React.useEffect(() => {
    setSarPreviewIndex(0);
    setSarImageFailed(false);
  }, [data]);

  const visibleCandidates = useMemo(() => {
    if (!model?.candidates) return [];
    return [...model.candidates]
      .sort((a, b) => (Number(b.sar_priority_score) || 0) - (Number(a.sar_priority_score) || 0))
      .slice(0, MAX_VISIBLE_CANDIDATES);
  }, [model]);
  const candidate = visibleCandidates[candidateIndex] || null;
  const vessels = candidate?.vessels || [];
  const vessel = vessels[vesselIndex] || null;

  const filteredCandidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return visibleCandidates;
    return visibleCandidates.filter((c) =>
      `${c.index} ${c.lat} ${c.lon} ${c.contrast}`.toLowerCase().includes(q)
    );
  }, [visibleCandidates, search]);

  const qualifiedLeads = useMemo(
  () =>
    vessels.filter((v) =>
      String(v.priority || "")
        .toUpperCase()
        .startsWith("HIGH PRIORITY")
    ).length,
  [vessels]
);

  const maxScore = useMemo(
    () => Math.max(1, ...vessels.map((v) => Number(v.score) || 0)),
    [vessels]
  );

  const mapCenter = candidate?.lat != null
    ? [candidate.lat, candidate.lon]
    : [Number(lat), Number(lon)];

  const route = useMemo(() => {
    if (!vessel) return null;
    const points = [];
    const last = vessel.last;
    const historical = vessel.historical;
    const next = vessel.next;

    for (const p of [last, historical, next]) {
      const a = num(p?.latitude ?? p?.lat);
      const b = num(p?.longitude ?? p?.lon);
      if (a !== null && b !== null) points.push([a, b]);
    }
    const current = [vessel.lat, vessel.lon];
    if (current[0] !== null && current[1] !== null) points.push(current);
    return points.length > 1 ? points : null;
  }, [vessel]);

  const rewindPoint = useMemo(() => {
    if (!vessel) return null;
    const start = vessel.last || vessel.historical;
    const end = { latitude: vessel.lat, longitude: vessel.lon };
    const aLat = num(start?.latitude ?? start?.lat);
    const aLon = num(start?.longitude ?? start?.lon);
    const bLat = num(end.latitude);
    const bLon = num(end.longitude);
    if ([aLat, aLon, bLat, bLon].some((x) => x === null)) return null;
    const t = Math.max(0, Math.min(1, rewindHour / Math.max(1, hours)));
    return { lat: aLat + (bLat - aLat) * t, lon: aLon + (bLon - aLon) * t };
  }, [vessel, rewindHour, hours]);

  React.useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setRewindHour((h) => {
        if (h >= hours) {
          setPlaying(false);
          return hours;
        }
        return Math.min(hours, h + 1);
      });
    }, 260);
    return () => clearInterval(id);
  }, [playing, hours]);

async function runAnalysis(nextHours = hours) {
  const cleanLat = Number(lat);
  const cleanLon = Number(lon);
  const cleanHours = Math.max(
    1,
    Math.min(48, Number(nextHours) || 48)
  );

  if (!Number.isFinite(cleanLat) || cleanLat < -90 || cleanLat > 90) {
    setError("Latitude must be a number between -90 and 90 degrees.");
    return;
  }

  if (!Number.isFinite(cleanLon) || cleanLon < -180 || cleanLon > 180) {
    setError("Longitude must be a number between -180 and 180 degrees.");
    return;
  }

  setLat(cleanLat);
  setLon(cleanLon);
  setHours(cleanHours);
  setLoading(true);
  setError("");
  setData(null);
  setActiveTab("overview");
  setCandidateIndex(0);
  setVesselIndex(0);
  setRewindHour(cleanHours);
  setPlaying(false);
  setSarPreviewIndex(0);
  setSarImageFailed(false);

  try {
    const response = await fetch(`${API}/analyze-spill`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        spill_lat: cleanLat,
        spill_lon: cleanLon,
        observation_time: time,
        hours_back: cleanHours,
      }),
    });

    let json;

    try {
      json = await response.json();
    } catch {
      throw new Error(
        `Backend returned ${response.status} without valid JSON.`
      );
    }

    if (!response.ok) {
      throw new Error(
        json?.detail || `Backend returned ${response.status}`
      );
    }

    if (
      json?.status &&
      !["success", "completed"].includes(
        String(json.status).toLowerCase()
      )
    ) {
      throw new Error(
        json?.detail || "Analysis did not complete successfully."
      );
    }

    if (!json || typeof json !== "object") {
      throw new Error("Analysis service returned an empty response.");
    }

    setData(json);
  } catch (e) {
    console.error("SlickBack analysis error:", e);
    setError(
      e?.message || "Unable to reach the analysis service."
    );
  } finally {
    setLoading(false);
  }
}

  function selectCandidate(index) {
    setCandidateIndex(index);
    setVesselIndex(0);
    setRewindHour(hours);
    setActiveTab("overview");
  }

  function resetWorkspace() {
    setData(null);
    setError("");
    setMapSelectedPoint(null);
    setCandidateIndex(0);
    setVesselIndex(0);
    setRewindHour(0);
    setPlaying(false);
  }

function focusIncident() {
  const point =
    candidate &&
    candidate.lat != null &&
    candidate.lon != null
      ? {
          lat: Number(candidate.lat),
          lon: Number(candidate.lon),
        }
      : {
          lat: Number(lat),
          lon: Number(lon),
        };

  if (
    !Number.isFinite(point.lat) ||
    !Number.isFinite(point.lon)
  ) {
    return;
  }

  setFocusPoint({
    lat: point.lat,
    lon: point.lon,
    token: Date.now(),
  });
}

  function selectMapLocation(latitude, longitude) {
    setLat(latitude);
    setLon(longitude);
    setData(null);
    setError("");
    setCandidateIndex(0);
    setVesselIndex(0);
    setRewindHour(hours);
    setPlaying(false);
    setMapSelectedPoint({ lat: latitude, lon: longitude, token: Date.now() });
    setMapSelectMode(false);
    setFocusPoint({ lat: latitude, lon: longitude, token: Date.now() });
  }

  async function exportReport() {
    if (!model || !candidate) return;
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const margin = 42;
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const contentWidth = pageWidth - margin * 2;
    let y = 48;
    const heading = (text) => {
      if (y > pageHeight - 80) { doc.addPage(); y = 48; }
      doc.setFont("helvetica", "bold"); doc.setFontSize(12); doc.setTextColor(20);
      doc.text(text, margin, y); y += 18;
    };
    const line = (text, indent = 0) => {
      const wrapped = doc.splitTextToSize(String(text), contentWidth - indent);
      if (y + wrapped.length * 13 > pageHeight - 45) { doc.addPage(); y = 48; }
      doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.setTextColor(35);
      doc.text(wrapped, margin + indent, y); y += wrapped.length * 13 + 3;
    };
    doc.setFont("helvetica", "bold"); doc.setFontSize(20); doc.setTextColor(15);
    doc.text("SLICKBACK", margin, y); y += 22;
    doc.setFontSize(13); doc.text("MARITIME OIL-SPILL INVESTIGATION DOSSIER", margin, y); y += 16;
    doc.setFont("helvetica", "normal"); doc.setFontSize(8); doc.setTextColor(95);
    doc.text(`Generated ${new Date().toISOString()}`, margin, y); y += 24;
    heading("1. INCIDENT PARAMETERS");
    line(`Investigation coordinate: ${fmt(lat, 6)}, ${fmt(lon, 6)}`);
    line(`Selected SAR candidate: #${candidate.index} at ${fmt(candidate.lat, 6)}, ${fmt(candidate.lon, 6)}`);
    line(`Observation time: ${utc(time)}`);
    line(`AIS correlation window: ${hours} hours`);
    line(`SAR mission: ${model.satellite?.mission || "Sentinel-1"}`);
    line(`Detected regions returned by backend: ${model.candidates?.length || 0}`);
    line(`Regions surfaced in dashboard: ${Math.min(MAX_VISIBLE_CANDIDATES, model.candidates?.length || 0)}`);
    line(`Live AIS provider status: ${model.live_ais?.available ? "Available" : model.live_ais?.reason || "Unavailable"}`);
    line(`Nearby vessel records for selected candidate: ${vessels.length}`);
    heading("2. SAR SIGNAL");
    line(`Local contrast: ${fmt(candidate.contrast, 2, " dB")}`);
    line(`Detected area: ${fmt(candidate.area, 0, " pixels")}`);
    line(`Candidate median backscatter: ${fmt(candidate.median, 2, " dB")}`);
    line(`Adaptive threshold: ${fmt(model.detection?.adaptive_threshold_db, 2, " dB")}`);
    try {
      if (!sarPreviewUrl) throw new Error("No analysis-specific Sentinel-1 image was returned.");
      const imageData = await loadImageDataUrl(sarPreviewUrl);
      if (y > pageHeight - 300) { doc.addPage(); y = 48; }
      heading("3. SENTINEL-1 ANALYSIS PREVIEW");
      const imageHeight = Math.min(270, contentWidth * 0.72);
      doc.addImage(imageData, "PNG", margin, y, contentWidth, imageHeight);
      y += imageHeight + 18;
      line("This is the generated Sentinel-1 analysis preview served by the SlickBack backend, not a generic map image.");
    } catch {
      heading("3. SENTINEL-1 ANALYSIS PREVIEW");
      line("Preview image could not be embedded. It remains available from the backend analysis-files endpoint.");
    }
    heading("4. TOP 5 SAR CANDIDATES");
    visibleCandidates.forEach((c, i) => {
      line(`${i + 1}. Candidate #${c.index} · ${fmt(c.lat, 6)}, ${fmt(c.lon, 6)}`);
      line(`Contrast ${fmt(c.contrast, 2, " dB")} · median ${fmt(c.median, 2, " dB")} · area ${fmt(c.area, 0, " px")} · priority ${fmt(c.sar_priority_score, 1)}`, 12);
      line(`Geometry: ${fmt(c.width_pixels, 0, " px")} × ${fmt(c.height_pixels, 0, " px")} · aspect ${fmt(c.aspect_ratio, 2)} · solidity ${fmt(c.solidity, 2)} · eccentricity ${fmt(c.eccentricity, 2)}`, 12);
    });
    heading("5. TOP INVESTIGATION VESSELS");
    const reportVessels = vessels.slice(0, 5);
    if (!reportVessels.length) line("No vessel records were returned for the selected candidate.");
    reportVessels.forEach((v, i) => {
      line(`${i + 1}. ${v.name} · MMSI ${v.mmsi}`);
     line(
  `Investigation score ${fmt(v.score, 1)} · correlation ${fmt(v.correlation, 3)} · distance ${fmt(v.distance, 1, " km")} · AIS gap ${fmt(v.gap, 1, " h")}`,
  12
);
      line(`Trajectory ${v.trajectory ? "compatible" : "not confirmed"} · reachability ${v.reachable ? "supported" : "not supported"} · assessment ${v.assessment}`, 12);
    });
    heading("6. ENVIRONMENTAL HINDCAST / SOURCE RECONSTRUCTION");
    const env = candidate?.environmental_hindcast || model.environmental_hindcast || model.environment || {};
    line(`Source estimate: ${fmt(env.source_lat ?? env.latitude, 6)}, ${fmt(env.source_lon ?? env.longitude, 6)}`);
    line(`Uncertainty radius: ${fmt(env.uncertainty_radius_km, 2, " km")}`);
    line(`Particle count: ${env.particle_count ?? "—"}`);
    line(`Hours rewound: ${env.hours_rewound ?? hours}`);
    line(`Release window: ${utc(env.release_window_start)} → ${utc(env.release_window_end)}`);
    line(`Environmental model: ${env.environment?.model || env.environment?.source || env.source || "Returned by backend"}`);
    line("The reconstruction estimates a plausible upstream/source region using the returned environmental hindcast. It is an investigation aid and not a proof of causation.");

    heading("7. TEMPORAL RECONSTRUCTION");
    line(`Current replay position: ${rewindHour} hours before observation.`);
    if (vessel) {
      line(`Selected vessel: ${vessel.name} (MMSI ${vessel.mmsi})`);
      line(`Historical point available: ${vessel.historical ? "Yes" : "No"}`);
      line(`Last known point available: ${vessel.last ? "Yes" : "No"}`);
      line(`Next known point available: ${vessel.next ? "Yes" : "No"}`);
    }
    line("Temporal replay is an investigation aid based on returned AIS positions; it does not prove causation.");
    heading("8. LIMITATIONS");
    line("AIS gaps represent missing information. Ranked vessels are investigation leads, not autonomous accusations or legal findings.");
    line("Satellite candidates are signals requiring confirmation and may include non-oil look-alikes caused by sea state, wind, wakes, or other surface effects.");
    doc.setFontSize(8); doc.setTextColor(100);
    doc.text("SLICKBACK · Detection → Reconstruction → Correlation → Evidence Fusion → Human Verification", margin, pageHeight - 25);
    doc.save(`SlickBack_Investigation_${String(vessel?.name || "Incident").replace(/[^a-z0-9_-]/gi, "_")}.pdf`);
  }

  return (
    <div className="sb-shell">
      <MapViewStyles />
      <aside className="sb-sidebar">
        <div className="sb-brand">
          <div className="sb-mark">S</div>
          <div>
            <div className="sb-brand-name">SLICK<span>BACK</span></div>
            <div className="sb-brand-sub">MARITIME INTELLIGENCE</div>
          </div>
        </div>

        <div className="sb-side-label">WORKSPACE</div>
        <nav className="sb-nav">
          <button className="active"><Icon name="radar"/><span>Situation room</span><b>01</b></button>
          <button onClick={() => setActiveTab("overview")}><Icon name="layers"/><span>Incidents</span></button>
          <button onClick={() => setActiveTab("vessel")}><Icon name="vessel"/><span>Vessel intelligence</span></button>
          <button onClick={() => setActiveTab("method")}><Icon name="chart"/><span>Evidence analysis</span></button>
          <button onClick={exportReport} disabled={!model}><Icon name="report"/><span>Reports</span></button>
        </nav>

        <div className="sb-side-label sb-side-system">SYSTEM</div>
        <div className="sb-system">
          <div><i className="dot live"/><span>Analysis service</span><strong>{loading ? "RUNNING" : "READY"}</strong></div>
          <div><i className={`dot ${model ? "live" : "dim"}`}/><span>Evidence store</span><strong>{model ? "SYNCED" : "IDLE"}</strong></div>
          <div><i className="dot dim"/><span>Live AIS</span><strong>LOCAL</strong></div>
        </div>

        <button className="sb-config" onClick={() => setLayersOpen((v) => !v)}>
          <Icon name="settings"/><span>Configuration</span>
        </button>

        <div className="sb-sidebar-footer">
          <span className="dot live"/> PIPELINE ONLINE
          <div className="sb-analyst"><div>SB</div><span><strong>Analyst</strong><small>Operations</small></span></div>
        </div>
      </aside>

      <main className="sb-main">
        <header className="sb-topbar">
          <div className="sb-breadcrumb"><span>OPERATIONS</span><i>›</i><strong>INCIDENT 26-0814-72</strong><em>ACTIVE</em></div>
          <div className="sb-top-actions">
            <span className="utc-live"><Icon name="clock" size={13}/> UTC {new Date().toISOString().slice(11, 19)}</span>
            <span className="health"><i className="dot live"/> SYSTEM OPERATIONAL</span>
            <button title="Reset workspace" onClick={resetWorkspace}><Icon name="close" size={15}/></button>
            <div className="sb-avatar">A</div>
          </div>
        </header>

        <section className="sb-command">
          <div className="sb-command-copy">
            <div className="eyebrow">MARITIME INCIDENT / OIL SPILL</div>
            <div className="sb-title-line">
              <h1>Oil-spill investigation</h1>
              <span className={model ? "status-good" : loading ? "status-run" : "status-idle"}>
                <i/> {loading ? "ANALYSIS RUNNING" : model ? "ANALYSIS COMPLETE" : "READY"}
              </span>
            </div>
            <p>Detect the signal. Reconstruct the source. Correlate vessel movement. Review the evidence trail.</p>
          </div>

          <div className="sb-controls">
            <label><span>LATITUDE</span><input type="number" step="0.0001" value={lat} onChange={(e) => setLat(e.target.value)}/></label>
            <label><span>LONGITUDE</span><input type="number" step="0.0001" value={lon} onChange={(e) => setLon(e.target.value)}/></label>
            <label className="time-control"><span>OBSERVATION TIME</span><input type="datetime-local" value={time.replace("Z","")} onChange={(e) => {
              const d = new Date(e.target.value);
              if (!Number.isNaN(d.getTime())) setTime(d.toISOString());
            }}/></label>
            <div className="window-control"><span>AIS WINDOW</span><select value={hours} onChange={(e) => runAnalysis(Number(e.target.value))}>{WINDOW_PRESETS.map((h) => <option key={h} value={h}>{h} H</option>)}</select></div>
            <button className="sb-run" onClick={() => runAnalysis()} disabled={loading}>
              {loading ? <span className="spinner"/> : <Icon name="radar" size={15}/>}
              {loading ? "ANALYZING" : "RUN ANALYSIS"} {!loading && <Icon name="arrow" size={14}/>}
            </button>
          </div>
        </section>

        {error && (
          <div className="sb-error">
            <Icon name="alert" size={16}/>
            <div><strong>ATTENTION</strong><span>{error}</span></div>
            <button onClick={() => setError("")}>×</button>
          </div>
        )}

        <section className="sb-workspace">
          <div className="sb-map-card">
            <div className="sb-panel-head">
              <div><span>GEOSPATIAL INVESTIGATION</span><strong>{model ? `Top ${Math.min(MAX_VISIBLE_CANDIDATES, model.candidates.length)} of ${model.candidates.length} detected candidates` : "Investigation field"}</strong></div>
              <div className="sb-map-head-actions">
                <span className="live-map"><i className="dot live"/> LIVE MAP</span>
                <button onClick={() => setLayersOpen((v) => !v)}><Icon name="layers" size={14}/> LAYERS</button>
                <div className="basemap-switch" role="group" aria-label="Map view">
                  <button
                    type="button"
                    className={basemap === "satellite" ? "active" : ""}
                    onClick={() => setBasemap("satellite")}
                    title="Satellite imagery"
                  >
                    SATELLITE
                  </button>
                  <button
                    type="button"
                    className={basemap === "street" ? "active" : ""}
                    onClick={() => setBasemap("street")}
                    title="Street map"
                  >
                    STREET
                  </button>
                </div>
                <button className={mapSelectMode ? "active" : ""} onClick={() => setMapSelectMode((v) => !v)}><Icon name="mapPin" size={14}/> {mapSelectMode ? "SELECTING" : "SELECT LOCATION"}</button>
                <button onClick={focusIncident} disabled={loading}><Icon name="target" size={14}/> FOCUS</button>
              </div>
            </div>

            <div className={`sb-map-wrap ${mapSelectMode ? "selecting" : ""}`}>
              <MapContainer center={mapCenter} zoom={8} className="sb-map" scrollWheelZoom>
                 <MapClickHandler onSelect={selectMapLocation} enabled={mapSelectMode}/>
                 {focusPoint && <MapFocus point={focusPoint}/>}
                {basemap === "street" ? (
                  <TileLayer
                    key="street-basemap"
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    maxZoom={19}
                  />
                ) : (
                  <TileLayer
                    key="satellite-basemap"
                    attribution='&copy; Esri'
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    maxZoom={19}
                  />
                )}

                {mapSelectedPoint && (
                  <Marker position={[mapSelectedPoint.lat, mapSelectedPoint.lon]} icon={L.divIcon({ className: "slickback-selection-pin", html: `<div><span></span></div>`, iconSize: [24,24], iconAnchor: [12,12] })}>
                    <Popup><strong>New analysis location</strong><br/>{fmt(mapSelectedPoint.lat,5)}, {fmt(mapSelectedPoint.lon,5)}<br/>Click RUN ANALYSIS to investigate.</Popup>
                  </Marker>
                )}

                {layers.source && (
                  <CircleMarker
                    center={[Number(lat), Number(lon)]}
                    radius={7}
                    pathOptions={{ color: "#ffffff", fillColor: "#25d4c7", fillOpacity: .95, weight: 2 }}
                  >
                    <Popup><strong>Investigation location</strong><br/>{fmt(lat,5)}, {fmt(lon,5)}</Popup>
                  </CircleMarker>
                )}

                {layers.candidates && visibleCandidates.map((c, i) => c.lat != null && (
                  <CircleMarker
                    key={`candidate-${i}`}
                    center={[c.lat, c.lon]}
                    radius={i === candidateIndex ? 12 : 6}
                    pathOptions={{
                      color: i === candidateIndex ? "#ffffff" : "#ff6b61",
                      fillColor: "#ff655b",
                      fillOpacity: i === candidateIndex ? .95 : .55,
                      weight: i === candidateIndex ? 3 : 1,
                    }}
                    eventHandlers={{ click: () => selectCandidate(i) }}
                  >
                    <Popup><strong>SAR candidate #{i + 1}</strong><br/>{fmt(c.lat,6)}, {fmt(c.lon,6)}<br/>Contrast {fmt(c.contrast,2," dB")}</Popup>
                  </CircleMarker>
                ))}

                {layers.vessels && vessels.map((v, i) => v.lat != null && (
                  <React.Fragment key={`vessel-${v.mmsi}-${i}`}>
                    <Marker
                      position={i === vesselIndex && rewindPoint ? [rewindPoint.lat, rewindPoint.lon] : [v.lat, v.lon]}
                      icon={VesselMarkerIcon({ selected: i === vesselIndex, heading: v.heading, historical: false })}
                      eventHandlers={{ click: () => { setVesselIndex(i); setActiveTab("vessel"); } }}
                    >
                      <Popup><strong>{v.name}</strong><br/>MMSI {v.mmsi}<br/>Priority {fmt(v.score,1)}</Popup>
                    </Marker>
                    {i === vesselIndex && v.historical && (
                      <CircleMarker
                        center={[Number(v.historical.latitude), Number(v.historical.longitude)]}
                        radius={4}
                        pathOptions={{ color: "#b9d9f7", fillColor: "#b9d9f7", fillOpacity: .9, weight: 1 }}
                      />
                    )}
                  </React.Fragment>
                ))}

                {layers.route && route && <Polyline positions={route} pathOptions={{ color: "#8bd6cf", weight: 2, opacity: .75, dashArray: "7 8" }}/>}
                {layers.radius && candidate?.lat != null && <Circle center={[candidate.lat, candidate.lon]} radius={10000} pathOptions={{ color: "#ff746a", weight: 1, dashArray: "5 7", fillOpacity: .035 }}/>}
              </MapContainer>

              <div className="map-readout top-left"><span>ACTIVE FIELD</span><strong>{candidate ? `CANDIDATE ${candidateIndex + 1}` : "AWAITING ANALYSIS"}</strong><small>{fmt(candidate?.lat,5)}, {fmt(candidate?.lon,5)}</small></div>
              <div className="map-readout top-right"><span>WGS84</span><strong>{fmt(lat,4)}° N&nbsp;&nbsp; {fmt(lon,4)}° E</strong><small>{hours}H correlation window</small></div>

              {mapSelectMode && (
                <div className="map-select-banner"><Icon name="mapPin" size={13}/> CLICK ANYWHERE ON THE MAP TO SET THE ANALYSIS LOCATION</div>
              )}

            {!model && !loading && !mapSelectMode && (
  <div className="map-empty">
    <div className="radar-orbit"><i/><b/></div>
    <strong>Ready for investigation</strong>
    <span>Enter the incident parameters and run the evidence pipeline.</span>
    <button onClick={() => runAnalysis()}>
      START ANALYSIS <Icon name="arrow" size={13}/>
    </button>
  </div>
)}

              {loading && (
                <div className="map-loading">
                  <div className="scan-ring"/><strong>FUSING EVIDENCE</strong>
                  <span>Sentinel-1 → SAR candidates → AIS correlation → lead assessment</span>
                  <div className="loading-steps"><b>01 DETECT</b><b>02 CORRELATE</b><b>03 RECONSTRUCT</b><b>04 RANK</b></div>
                </div>
              )}

              {layersOpen && (
                <div className="layers-pop">
                  <div className="pop-title">MAP LAYERS</div>
                  {Object.entries(layers).map(([key, value]) => (
                    <label key={key}>
                      <input type="checkbox" checked={value} onChange={(e) => setLayers((old) => ({ ...old, [key]: e.target.checked }))}/>
                      <span>{key === "route" ? "Historical route" : key === "radius" ? "Correlation radius" : key[0].toUpperCase() + key.slice(1)}</span>
                    </label>
                  ))}
                </div>
              )}

              <div className="map-legend">
                <span><i className="legend-sar"/> SAR candidate</span>
                <span><i className="legend-vessel"/> AIS vessel</span>
                <span><i className="legend-history"/> Historical</span>
                <span><i className="legend-route"/> Movement</span>
               <span className="legend-basemap">
  {basemap === "street" ? "STANDARD MAP" : "SATELLITE"}
</span>
              </div>
            </div>

            <div className="sb-rewind">
              <div className="rewind-title">
                <div><span>TEMPORAL REWIND</span><strong>{rewindHour}H BEFORE OBSERVATION</strong></div>
                <div className="rewind-actions">
                  <button onClick={() => setRewindHour(0)}>ORIGIN</button>
                  <button onClick={() => setRewindHour(hours)}>OBSERVED</button>
                  <button className="play" onClick={() => setPlaying((v) => !v)} disabled={!vessel}>{playing ? <Icon name="pause" size={13}/> : <Icon name="play" size={13}/>} {playing ? "PAUSE" : "PLAY"}</button>
                </div>
              </div>
              <input
                className="rewind-slider"
                type="range"
                min="0"
                max={hours}
                value={Math.min(rewindHour, hours)}
                onChange={(e) => { setPlaying(false); setRewindHour(Number(e.target.value)); }}
              />
              <div className="rewind-scale"><span>{hours}H AGO</span><i/><i/><i/><span>OBSERVATION</span></div>
              <p>Visual reconstruction uses the returned historical/current AIS points. Intermediate positions are interpolated for the replay view.</p>
            </div>
          </div>

          <aside className="sb-evidence-card">
            <div className="sb-evidence-head">
              <div><span className="eyebrow">INVESTIGATION SUMMARY</span><h2>Evidence review</h2></div>
              <span className={model ? "rail-complete" : "rail-ready"}><i/> {loading ? "RUNNING" : model ? "COMPLETE" : "READY"}</span>
            </div>

            {!model && !loading && (
              <div className="sb-empty-review">
                <div className="empty-icon"><Icon name="radar" size={22}/></div>
                <strong>No active investigation</strong>
                <p>Run the pipeline to populate SAR detections, vessel correlation and the evidence chain.</p>
                <button onClick={() => runAnalysis()}>START ANALYSIS <Icon name="arrow" size={13}/></button>
              </div>
            )}

            {loading && (
              <div className="sb-pipeline">
                <div className="pipeline-title"><span>ANALYSIS PIPELINE</span><b>RUNNING</b></div>
                {["Satellite evidence","SAR candidate detection","Environmental reconstruction","AIS spatial correlation","Lead assessment"].map((step, i) => (
                  <div className={`pipeline-step ${i < 2 ? "done" : i === 2 ? "active" : ""}`} key={step}>
                    <i>{i < 2 ? "✓" : String(i + 1).padStart(2, "0")}</i><span>{step}</span>
                  </div>
                ))}
              </div>
            )}

            {model && !loading && (
              <>
           <div className="sb-kpis">
  <Metric
    label="SAR SOURCE"
    value={model.satellite?.mission || "Sentinel-1"}
  />

  <Metric
    label="SAR SIGNALS"
    value={`${visibleCandidates.length} / ${model.candidates.length}`}
    accent
  />

  <Metric
    label="QUALIFIED LEADS"
    value={qualifiedLeads}
  />
</div>

{qualifiedLeads === 0 && vessels.length > 0 && (
  <div
    className="sb-inline-note"
    role="status"
    aria-live="polite"
  >
    <Icon name="alert" size={13} />
    <span>
      No vessel currently meets the high-priority investigation criteria
      for the selected candidate. Nearby AIS records remain correlation
      evidence for analyst review.
    </span>
  </div>
)}

                <div className="sb-tabs">
                  <button className={activeTab === "overview" ? "active" : ""} onClick={() => setActiveTab("overview")}>OVERVIEW</button>
                  <button className={activeTab === "vessel" ? "active" : ""} onClick={() => setActiveTab("vessel")}>LEAD VESSEL</button>
                  <button className={activeTab === "method" ? "active" : ""} onClick={() => setActiveTab("method")}>METHOD</button>
                </div>

                {activeTab === "overview" && (
                  <div className="tab-body">
                    <div className="candidate-head">
                      <div><span>DETECTED REGION</span><strong>Candidate #{candidateIndex + 1}</strong></div>
                      <select value={candidateIndex} onChange={(e) => selectCandidate(Number(e.target.value))}>
                        {filteredCandidates.length ? filteredCandidates.map((c) => {
                          const visibleIndex = visibleCandidates.findIndex((x) => x.index === c.index);
                          return <option key={c.index} value={visibleIndex}>Candidate #{c.index} · {fmt(c.contrast,2," dB")}</option>;
                        }) : <option>No matches</option>}
                      </select>
                    </div>

                    <div className="candidate-search">
                      <Icon name="search" size={14}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter candidates..."/>
                    </div>

                    <div className="signal-hero">
                      <div><span>SAR SIGNAL</span><strong>{fmt(candidate?.contrast,2," dB")}</strong></div>
                      <em>#{candidateIndex + 1}</em>
                    </div>

                    <div className="sar-preview-card">
                      <div className="sar-preview-head">
                        <div><span>SENTINEL-1 EVIDENCE</span><strong>Actual analysis image</strong></div>
                        {sarPreviewUrl && (
                          <a href={sarPreviewUrl} target="_blank" rel="noreferrer">OPEN FULL</a>
                        )}
                      </div>
                      {sarPreviewUrl && !sarImageFailed ? (
                        <img
                          key={sarPreviewUrl}
                          src={sarPreviewUrl}
                          alt="Sentinel-1 analysis image returned for this investigation"
                          loading="eager"
                          decoding="async"
                          onError={() => {
                            if (sarPreviewIndex + 1 < sarPreviewCandidates.length) {
                              setSarPreviewIndex((i) => i + 1);
                            } else {
                              setSarImageFailed(true);
                            }
                          }}
                        />
                      ) : (
                        <div className="sar-preview-empty">
                          <Icon name="alert" size={18}/>
                          <span>
                            {sarImageFailed
                              ? "Sentinel-1 evidence image could not be loaded from the analysis service."
                              : sarPreviewCandidates.length
                                ? "Loading Sentinel-1 evidence image..."
                                : "No analysis-specific Sentinel-1 image was returned."}
                          </span>
                        </div>
                      )}
                      <small>Generated by the backend analysis pipeline for this investigation · not a generic basemap.</small>
                    </div>

                    <div className="metric-grid four">
                      <Metric label="LATITUDE" value={fmt(candidate?.lat,5)} />
                      <Metric label="LONGITUDE" value={fmt(candidate?.lon,5)} />
                      <Metric label="AREA" value={fmt(candidate?.area,0," px")} />
                      <Metric label="THRESHOLD" value={fmt(model.detection?.adaptive_threshold_db,2," dB")} />
                    </div>

                   <div className="section-heading">
  <span>VESSEL CORRELATION</span>
  <b>{vessels.length} CORRELATED</b>
</div>
                    <div className="vessel-list">
                      {vessels.length ? vessels.slice(0, 8).map((v, i) => (
                        <button className={`vessel-row ${i === vesselIndex ? "selected" : ""}`} key={`${v.mmsi}-${i}`} onClick={() => { setVesselIndex(i); setActiveTab("vessel"); }}>
                          <span className="rank">{String(i + 1).padStart(2, "0")}</span>
                          <span className="vessel-name"><strong>{v.name}</strong><small>MMSI {v.mmsi}</small></span>
                          <span className="vessel-score">{fmt(v.score,1)}</span>
                          <Icon name="chevron" size={13}/>
                        </button>
                      )) : <div className="no-vessels">No vessel records were returned for this candidate.</div>}
                    </div>
                  </div>
                )}

                {activeTab === "vessel" && (
                  <div className="tab-body">
                    {!vessel ? <div className="no-vessels">Select a vessel lead from the overview.</div> : (
                      <>
                        <div className="lead-identity">
                          <div>
  <span>SELECTED VESSEL</span>
  <h3>{vessel.name}</h3>
  <small>MMSI {vessel.mmsi}</small>
</div>
                          <div className="lead-priority"><span>PRIORITY</span><strong>{fmt(vessel.score,1)}</strong></div>
                        </div>
                        <span className={`priority-badge ${assessmentTone(vessel.assessment)}`}>{vessel.priority}</span>

                        <div className="metric-grid three">
                          <Metric label="AIS CORRELATION" value={fmt(vessel.correlation,3)} />
                          <Metric label="DISTANCE" value={fmt(vessel.distance,1," km")} />
                          <Metric label="RELIABILITY" value={fmt(vessel.reliability,2)} />
                          <Metric label="AIS GAP" value={fmt(vessel.gap,1," h")} />
                          <Metric label="SOURCE DISTANCE" value={fmt(vessel.sourceDistance,1," km")} />
                          <Metric label="EVIDENCE" value={fmt(vessel.evidence,1)} />
                        </div>

                        <div className="fusion-card"><div className="fusion-title">
  <span>EVIDENCE FUSION</span>
  <b>WHY THIS VESSEL?</b>
</div>
                          <EvidenceBar label="AIS correlation" value={(vessel.correlation || 0) * 100}/>
                          <EvidenceBar label="Investigation evidence" value={(vessel.evidence || 0) * 10}/>
                          <EvidenceBar label="Priority score" value={((vessel.score || 0) / maxScore) * 100} note={fmt(vessel.score,1)}/>
                        </div>

                        <div className="evidence-list">
                          <div className={vessel.trajectory ? "positive" : ""}><i>{vessel.trajectory ? "✓" : "○"}</i><span><strong>Historical trajectory</strong><small>{vessel.trajectory ? "Compatible trajectory signal returned." : "No compatible trajectory signal returned."}</small></span></div>
                          <div className={vessel.gap > 0 ? "warning" : ""}><i>{vessel.gap > 0 ? "!" : "○"}</i><span><strong>AIS continuity</strong><small>{vessel.gap > 0 ? `Historical gap: ${fmt(vessel.gap,1," h")}. Missing information requires review.` : "No AIS gap flagged."}</small></span></div>
                          <div className={vessel.reachable ? "positive" : ""}><i>{vessel.reachable ? "✓" : "○"}</i><span><strong>Physical reachability</strong><small>{vessel.reachable ? "Motion estimate can reach the source region." : "Motion estimate does not support reachability."}</small></span></div>
                          {vessel.anomaly && <div className="warning"><i>!</i><span><strong>Kinematic anomaly</strong><small>An anomalous movement signal was returned for review.</small></span></div>}
                        </div>

                        {vessel.flags?.length > 0 && <div className="flag-chips">{vessel.flags.map((f) => <span key={f}>{f}</span>)}</div>}
                      </>
                    )}
                  </div>
                )}

                {activeTab === "method" && (
                  <div className="tab-body method-list">
                    {[
                      ["01","SENTINEL-1 DETECTION","Dark SAR regions are extracted and measured. A candidate is a signal requiring confirmation."],
                      ["02","ENVIRONMENTAL RECONSTRUCTION","Wind/current context supports a backward reconstruction of the likely source region."],
                      ["03","AIS CORRELATION","Nearby vessels are ranked using spatial correlation, reliability and movement evidence."],
                      ["04","TEMPORAL REWIND","Historical AIS timestamps and gaps are inspected around the observation time."],
                      ["05","HUMAN VERIFICATION","The final priority is an investigation lead, not an autonomous accusation."],
                    ].map(([n,title,body]) => (
                      <div className="method-step" key={n}><b>{n}</b><div><strong>{title}</strong><span>{body}</span></div></div>
                    ))}
                  </div>
                )}

                <div className="sb-disclaimer"><Icon name="alert" size={13}/><span>Investigation indicators are not legal proof of responsibility. AIS gaps represent missing information requiring review.</span></div>
                <button className="sb-report" onClick={exportReport}><Icon name="download" size={14}/> EXPORT INVESTIGATION DOSSIER <Icon name="arrow" size={13}/></button>
              </>
            )}
          </aside>
        </section>

        <section className="sb-bottom">
         <div>
  <span>SAR DETECTION</span>

  <strong>
    {model
      ? Math.min(MAX_VISIBLE_CANDIDATES, model.candidates.length)
      : "—"}
  </strong>

  <small>
    {model
      ? `highest-priority of ${model.candidates.length} returned`
      : "surfaced candidates"}
  </small>

  <em>{model?.satellite?.mission || "Sentinel-1"}</em>
</div>
          <div><span>AIS CORRELATION</span><strong>{vessels.length || "—"}</strong><small>nearby vessel records</small><em>{hours}H window</em></div>
          <div>
  <span>TOP VESSEL SCORE</span>

  <strong>
    {vessel ? fmt(vessel.score, 1) : "—"}
  </strong>

  <small>
    {vessel?.name || "No vessel selected"}
  </small>

  <em>
    {vessel ? "CORRELATION REVIEW" : "WAITING"}
  </em>
</div>
          <div><span>RECONSTRUCTION</span><strong>{vessel?.gap != null ? fmt(vessel.gap,1,"H") : "—"}</strong><small>AIS continuity gap</small><em>{vessel?.trajectory ? "TRAJECTORY OK" : "REVIEW"}</em></div>
        </section>

        <footer className="sb-footer">
          <span>SLICKBACK · MARITIME INTELLIGENCE PLATFORM</span>
          <span>Detection → Reconstruction → Correlation → Evidence Fusion → Ranking → Human Verification</span>
          <span>INDICATORS ≠ LEGAL PROOF</span>
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
