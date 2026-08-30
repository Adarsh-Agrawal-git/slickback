import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Circle,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";
import jsPDF from "jspdf";
import "leaflet/dist/leaflet.css";
import "./styles.css";

const API =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const DEFAULTS = {
  lat: 18.75,
  lon: 72.65,
  time: "2026-08-14T23:59:59Z",
  hours: 48,
};

const WINDOW_PRESETS = [24, 48, 72, 120, 168];

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
  };
  return <svg {...p}>{paths[name] || paths.target}</svg>;
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
    map.flyTo([Number(point.lat), Number(point.lon)], Math.max(map.getZoom(), 9), {
      duration: 0.55,
    });
  }, [point?.lat, point?.lon, map]);
  return null;
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

  const model = useMemo(() => (data ? normalize(data) : null), [data]);
  const candidate = model?.candidates?.[candidateIndex] || null;
  const vessels = candidate?.vessels || [];
  const vessel = vessels[vesselIndex] || null;

  const filteredCandidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return model?.candidates || [];
    return (model?.candidates || []).filter((c) =>
      `${c.index} ${c.lat} ${c.lon} ${c.contrast}`.toLowerCase().includes(q)
    );
  }, [model, search]);

  const investigationLeads = useMemo(
    () =>
      vessels.filter((v) => {
        const a = String(v.assessment || "").toUpperCase();
        return a.includes("INVESTIGATION") || a.includes("INTENTIONAL");
      }).length,
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
    const cleanHours = Math.max(1, Math.min(168, Number(nextHours) || 48));
    setHours(cleanHours);
    setLoading(true);
    setError("");
    setActiveTab("overview");
    setCandidateIndex(0);
    setVesselIndex(0);
    setRewindHour(cleanHours);
    setPlaying(false);

    try {
      const response = await fetch(`${API}/analyze-spill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spill_lat: Number(lat),
          spill_lon: Number(lon),
          observation_time: time,
          hours_back: cleanHours,
        }),
      });
      let json = null;
      try {
        json = await response.json();
      } catch {
        throw new Error(`Backend returned ${response.status} without valid JSON.`);
      }
      if (!response.ok) {
        throw new Error(json?.detail || `Backend returned ${response.status}`);
      }
      if (json?.status && json.status !== "success") {
        throw new Error(json?.detail || "Analysis did not complete successfully.");
      }
      setData(json);
    } catch (e) {
      console.error(e);
      setError(e?.message || "Unable to reach the analysis service.");
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
    setCandidateIndex(0);
    setVesselIndex(0);
    setRewindHour(0);
    setPlaying(false);
  }

  function focusIncident() {
    setFocusPoint(
      candidate
        ? { lat: candidate.lat, lon: candidate.lon }
        : { lat: Number(lat), lon: Number(lon) }
    );
  }

  function exportReport() {
    if (!model || !candidate) return;
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const margin = 42;
    let y = 48;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(20);
    doc.text("SLICKBACK — INVESTIGATION DOSSIER", margin, y);
    y += 26;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(90);
    doc.text(`Generated ${new Date().toISOString()}`, margin, y);
    y += 25;
    doc.setTextColor(20);
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.text("Incident", margin, y);
    y += 17;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    [
      `Observed point: ${fmt(candidate.lat, 6)}, ${fmt(candidate.lon, 6)}`,
      `SAR contrast: ${fmt(candidate.contrast, 2, " dB")}`,
      `Detected area: ${fmt(candidate.area, 0, " px")}`,
      `Observation time: ${utc(time)}`,
      `AIS window: ${hours} hours`,
      `Candidate vessels: ${vessels.length}`,
    ].forEach((line) => { doc.text(line, margin, y); y += 14; });

    y += 10;
    doc.setFont("helvetica", "bold");
    doc.text("Leading investigation candidate", margin, y);
    y += 17;
    doc.setFont("helvetica", "normal");
    if (vessel) {
      [
        `Vessel: ${vessel.name}`,
        `MMSI: ${vessel.mmsi}`,
        `Investigation priority: ${fmt(vessel.score, 1)}`,
        `AIS correlation: ${fmt(vessel.correlation, 3)}`,
        `Distance: ${fmt(vessel.distance, 1, " km")}`,
        `AIS reliability: ${fmt(vessel.reliability, 2)}`,
        `AIS gap: ${fmt(vessel.gap, 1, " h")}`,
        `Source distance: ${fmt(vessel.sourceDistance, 1, " km")}`,
        `Trajectory compatible: ${vessel.trajectory ? "Yes" : "No"}`,
      ].forEach((line) => { doc.text(line, margin, y); y += 14; });
    }
    y += 12;
    doc.setFont("helvetica", "bold");
    doc.text("Interpretation", margin, y);
    y += 16;
    doc.setFont("helvetica", "normal");
    doc.text(
      doc.splitTextToSize(
        "This report presents ranked investigation indicators. AIS gaps and priority scores require human review and do not establish legal responsibility.",
        510
      ),
      margin,
      y
    );
    doc.save(`SlickBack_Investigation_${vessel?.name || "Incident"}.pdf`);
  }

  return (
    <div className="sb-shell">
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
              <div><span>GEOSPATIAL INVESTIGATION</span><strong>{model ? `${model.candidates.length} detected regions` : "Investigation field"}</strong></div>
              <div className="sb-map-head-actions">
                <span className="live-map"><i className="dot live"/> LIVE MAP</span>
                <button onClick={() => setLayersOpen((v) => !v)}><Icon name="layers" size={14}/> LAYERS</button>
                <button onClick={focusIncident}><Icon name="target" size={14}/> FOCUS</button>
              </div>
            </div>

            <div className="sb-map-wrap">
              <MapContainer center={mapCenter} zoom={8} className="sb-map" scrollWheelZoom>
                <TileLayer
                  attribution='&copy; Esri'
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                />
                <MapFocus point={focusPoint || (candidate ? { lat: candidate.lat, lon: candidate.lon } : { lat: Number(lat), lon: Number(lon) })}/>

                {layers.source && (
                  <CircleMarker
                    center={[Number(lat), Number(lon)]}
                    radius={7}
                    pathOptions={{ color: "#ffffff", fillColor: "#25d4c7", fillOpacity: .95, weight: 2 }}
                  >
                    <Popup><strong>Investigation location</strong><br/>{fmt(lat,5)}, {fmt(lon,5)}</Popup>
                  </CircleMarker>
                )}

                {layers.candidates && model?.candidates?.map((c, i) => c.lat != null && (
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
                    <CircleMarker
                      center={
                        i === vesselIndex && rewindPoint
                          ? [rewindPoint.lat, rewindPoint.lon]
                          : [v.lat, v.lon]
                      }
                      radius={i === vesselIndex ? 9 : 5}
                      pathOptions={{
                        color: i === vesselIndex ? "#ffffff" : "#5ba7ef",
                        fillColor: "#5ba7ef",
                        fillOpacity: .95,
                        weight: i === vesselIndex ? 3 : 1,
                      }}
                      eventHandlers={{ click: () => { setVesselIndex(i); setActiveTab("vessel"); } }}
                    >
                      <Popup><strong>{v.name}</strong><br/>MMSI {v.mmsi}<br/>Priority {fmt(v.score,1)}</Popup>
                    </CircleMarker>
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

              {!model && !loading && (
                <div className="map-empty">
                  <div className="radar-orbit"><i/><b/></div>
                  <strong>Ready for investigation</strong>
                  <span>Enter the incident parameters and run the evidence pipeline.</span>
                  <button onClick={() => runAnalysis()}>START ANALYSIS <Icon name="arrow" size={13}/></button>
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
                  <Metric label="SAR SOURCE" value={model.satellite?.mission || "Sentinel-1"} />
                  <Metric label="SIGNALS" value={model.detection?.candidate_count ?? model.candidates.length} accent />
                  <Metric label="LEADS" value={investigationLeads} />
                </div>

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
                        {filteredCandidates.length ? filteredCandidates.map((c) => <option key={c.index} value={c.index - 1}>Candidate #{c.index} · {fmt(c.contrast,2," dB")}</option>) : <option>No matches</option>}
                      </select>
                    </div>

                    <div className="candidate-search">
                      <Icon name="search" size={14}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter candidates..."/>
                    </div>

                    <div className="signal-hero">
                      <div><span>SAR SIGNAL</span><strong>{fmt(candidate?.contrast,2," dB")}</strong></div>
                      <em>#{candidateIndex + 1}</em>
                    </div>
                    <div className="metric-grid four">
                      <Metric label="LATITUDE" value={fmt(candidate?.lat,5)} />
                      <Metric label="LONGITUDE" value={fmt(candidate?.lon,5)} />
                      <Metric label="AREA" value={fmt(candidate?.area,0," px")} />
                      <Metric label="THRESHOLD" value={fmt(model.detection?.adaptive_threshold_db,2," dB")} />
                    </div>

                    <div className="section-heading"><span>VESSEL LEADS</span><b>{vessels.length} CORRELATED</b></div>
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
                          <div><span>SELECTED LEAD</span><h3>{vessel.name}</h3><small>MMSI {vessel.mmsi}</small></div>
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

                        <div className="fusion-card">
                          <div className="fusion-title"><span>EVIDENCE FUSION</span><b>WHY THIS LEAD?</b></div>
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
          <div><span>SAR DETECTION</span><strong>{model?.candidates?.length ?? "—"}</strong><small>candidate regions</small><em>{model?.satellite?.mission || "Sentinel-1"}</em></div>
          <div><span>AIS CORRELATION</span><strong>{vessels.length || "—"}</strong><small>nearby vessel records</small><em>{hours}H window</em></div>
          <div><span>LEAD PRIORITY</span><strong>{vessel ? fmt(vessel.score,1) : "—"}</strong><small>{vessel?.name || "No lead selected"}</small><em>{vessel ? "REVIEW" : "WAITING"}</em></div>
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
