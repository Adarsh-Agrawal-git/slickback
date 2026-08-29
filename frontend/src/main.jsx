
const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { jsPDF } from "jspdf";

import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";
import "./styles.css";

const DEFAULT_LAT = 18.75;
const DEFAULT_LON = 72.65;


/* ============================================================
   HELPERS
============================================================ */

function number(value, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const n = Number(value);

  if (Number.isNaN(n)) {
    return "—";
  }

  return n.toFixed(digits);
}


function assessmentTone(assessment) {
  const value = String(assessment || "").toUpperCase();

  if (value.includes("INTENTIONAL")) {
    return "critical";
  }

  if (value.includes("INVESTIGATION")) {
    return "warning";
  }

  if (value.includes("ACCIDENTAL")) {
    return "info";
  }

  return "neutral";
}


function assessmentShort(assessment) {
  const value = String(
    assessment || "INSUFFICIENT EVIDENCE"
  ).toUpperCase();

  if (value.includes("INTENTIONAL")) {
    return "INTENTIONAL INDICATORS";
  }

  if (value.includes("INVESTIGATION")) {
    return "REQUIRES INVESTIGATION";
  }

  if (value.includes("ACCIDENTAL")) {
    return "POSSIBLE ACCIDENT";
  }

  return "INSUFFICIENT EVIDENCE";
}


/* ============================================================
   MAP CONTROLLER
============================================================ */

function MapController({ position }) {
  const map = useMap();

  useEffect(() => {
    if (!position) {
      return;
    }

    map.flyTo(
      [
        Number(position.latitude),
        Number(position.longitude),
      ],
      11,
      {
        duration: 0.8,
      }
    );
  }, [position, map]);

  return null;
}


/* ============================================================
   MAP LEGEND
============================================================ */

function Legend() {
  return (
    <div className="map-legend">

      <div className="legend-row">
        <span className="legend-symbol spill-symbol" />
        <span>Spill candidate</span>
      </div>

      <div className="legend-row">
        <span className="legend-symbol vessel-symbol" />
        <span>Current AIS position</span>
      </div>

      <div className="legend-row">
        <span className="legend-symbol history-symbol" />
        <span>Historical position</span>
      </div>

      <div className="legend-row">
        <span className="legend-line" />
        <span>Historical movement</span>
      </div>

    </div>
  );
}


/* ============================================================
   METRIC
============================================================ */

function Metric({ label, value }) {
  return (
    <div className="metric">

      <div className="metric-label">
        {label}
      </div>

      <div className="metric-value">
        {value}
      </div>

    </div>
  );
}


/* ============================================================
   STATUS DOT
============================================================ */

function StatusDot({ type = "online" }) {
  return (
    <span
      className={`status-dot ${type}`}
    />
  );
}


/* ============================================================
   VESSEL CARD
============================================================ */

function VesselCard({
  vessel,
  index,
  selected,
  onSelect,
}) {
  const investigation =
    vessel?.investigation || {};

  const assessment =
    investigation?.assessment ||
    "INSUFFICIENT EVIDENCE";

  const tone =
    assessmentTone(assessment);

  return (
    <button
      className={`vessel-card ${
        selected ? "selected" : ""
      }`}
      onClick={() => onSelect(vessel)}
    >

      <div className="vessel-card-top">

        <div className="vessel-rank">
          {String(index + 1).padStart(2, "0")}
        </div>

        <div className="vessel-main">

          <div className="vessel-name">
            {vessel?.name || "Unknown vessel"}
          </div>

          <div className="vessel-mmsi">
            MMSI {vessel?.mmsi || "—"}
          </div>

        </div>

        <div className="priority-block">

          <div className="priority-label">
            PRIORITY
          </div>

          <div className="priority-value">
            {number(
              vessel?.responsibility_score,
              1
            )}
          </div>

        </div>

      </div>


      <div className="vessel-metrics">

        <Metric
          label="AIS correlation"
          value={number(
            vessel?.correlation_score,
            3
          )}
        />

        <Metric
          label="Distance"
          value={`${number(
            vessel?.distance_km,
            1
          )} km`}
        />

        <Metric
          label="AIS reliability"
          value={number(
            vessel?.ais_reliability,
            2
          )}
        />

        <Metric
          label="Evidence"
          value={number(
            investigation?.evidence_score,
            1
          )}
        />

      </div>


      <div className="vessel-bottom">

        <div className="mini-status">

          <span
            className={
              investigation?.ais_gap_hours > 0
                ? "mini-dot warning"
                : "mini-dot"
            }
          />

          AIS gap{" "}
          {number(
            investigation?.ais_gap_hours,
            1
          )}
          {" "}hrs

        </div>


        <div
          className={`assessment-badge ${tone}`}
        >
          {assessmentShort(assessment)}
        </div>

      </div>

    </button>
  );
}


/* ============================================================
   MAIN APP
============================================================ */


function generatePDFReport({
  data,
  candidate,
  activeVessel,
  observationTime,
  hoursBack,
}) {
  if (!data || !candidate) {
    alert("Run the incident analysis first.");
    return;
  }

  try {
    const doc = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 16;
    const width = pageWidth - margin * 2;

    const vessel = activeVessel || null;
    const investigation = vessel?.investigation || {};

    const spillLat = Number(candidate.latitude);
    const spillLon = Number(candidate.longitude);

    const currentLat =
      vessel?.latitude !== undefined
        ? Number(vessel.latitude)
        : null;

    const currentLon =
      vessel?.longitude !== undefined
        ? Number(vessel.longitude)
        : null;

    const historical =
      investigation?.estimated_historical_position || null;

    const assessment =
      investigation?.assessment ||
      "INSUFFICIENT EVIDENCE";

    let y = 18;

    function text(label, value, x, yy, size = 9, bold = false) {
      doc.setFont("helvetica", bold ? "bold" : "normal");
      doc.setFontSize(size);
      doc.setTextColor(35, 45, 52);
      doc.text(`${label}: ${value ?? "—"}`, x, yy);
    }

    function heading(title) {
      y += 7;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(11);
      doc.setTextColor(18, 125, 125);
      doc.text(title, margin, y);
      y += 7;
    }

    function line() {
      doc.setDrawColor(190, 200, 205);
      doc.line(margin, y, pageWidth - margin, y);
      y += 5;
    }

    // Header
    doc.setFillColor(7, 22, 30);
    doc.rect(0, 0, pageWidth, 32, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(20);
    doc.setTextColor(255, 255, 255);
    doc.text("SLICK", margin, 14);

    doc.setTextColor(24, 200, 189);
    doc.text("BACK", margin + 20, 14);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(170, 190, 198);
    doc.text(
      "MARITIME INTELLIGENCE CONSOLE",
      margin,
      21
    );

    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.setTextColor(255, 255, 255);
    doc.text(
      "OIL-SPILL INVESTIGATION REPORT",
      pageWidth - margin,
      14,
      { align: "right" }
    );

    y = 42;

    doc.setFont("helvetica", "bold");
    doc.setFontSize(15);
    doc.setTextColor(25, 32, 38);
    doc.text("Incident Investigation", margin, y);

    y += 7;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(90, 100, 110);
    doc.text(
      `Observation: ${observationTime}   |   AIS window: ${hoursBack} hours`,
      margin,
      y
    );

    line();

    // Spill candidate
    heading("1. PRIMARY SPILL CANDIDATE");

    doc.setFillColor(240, 247, 248);
    doc.roundedRect(margin, y, width, 35, 2, 2, "F");

    text(
      "Latitude",
      spillLat.toFixed(6),
      margin + 5,
      y + 9,
      9,
      true
    );

    text(
      "Longitude",
      spillLon.toFixed(6),
      margin + 75,
      y + 9,
      9,
      true
    );

    text(
      "SAR contrast",
      `${number(candidate.local_contrast_db, 2)} dB`,
      margin + 135,
      y + 9,
      8,
      true
    );

    text(
      "Detected area",
      `${candidate.area_pixels ?? "—"} px`,
      margin + 5,
      y + 22,
      9
    );

    text(
      "Candidate rank",
      "#1",
      margin + 75,
      y + 22,
      9
    );

    text(
      "Satellite",
      data?.satellite?.mission || "Sentinel-1",
      margin + 135,
      y + 22,
      8
    );

    y += 43;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(75, 85, 95);
    doc.text(
      "This is the highest-ranked SAR spill candidate returned by the current analysis.",
      margin,
      y
    );

    // Vessel
    heading("2. LEADING VESSEL");

    if (vessel) {
      doc.setFillColor(247, 248, 249);
      doc.roundedRect(margin, y, width, 49, 2, 2, "F");

      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.setTextColor(25, 32, 38);
      doc.text(
        vessel.name || "Unknown vessel",
        margin + 5,
        y + 9
      );

      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(100, 110, 120);
      doc.text(
        `MMSI ${vessel.mmsi || "—"}`,
        margin + 5,
        y + 15
      );

      text(
        "Responsibility score",
        number(vessel.responsibility_score, 1),
        margin + 5,
        y + 27,
        8
      );

      text(
        "AIS correlation",
        number(vessel.correlation_score, 3),
        margin + 75,
        y + 27,
        8
      );

      text(
        "Distance",
        `${number(vessel.distance_km, 2)} km`,
        margin + 135,
        y + 27,
        8
      );

      text(
        "AIS reliability",
        number(vessel.ais_reliability, 2),
        margin + 5,
        y + 40,
        8
      );

      text(
        "AIS gap",
        `${number(investigation.ais_gap_hours, 2)} hrs`,
        margin + 75,
        y + 40,
        8
      );

      text(
        "Source distance",
        `${number(investigation.source_distance_km, 2)} km`,
        margin + 135,
        y + 40,
        8
      );

      y += 58;
    } else {
      doc.text(
        "No vessel lead is available.",
        margin,
        y
      );
      y += 12;
    }

    // Footer for page 1
    {
      const footerY = pageHeight - 10;
      doc.setDrawColor(190, 200, 205);
      doc.line(margin, footerY - 5, pageWidth - margin, footerY - 5);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(6.5);
      doc.setTextColor(110, 120, 130);
      doc.text(
        "SLICKBACK · Sentinel-1 SAR · AIS · Historical trajectory analysis",
        margin,
        footerY
      );
      doc.text(
        "Page 1",
        pageWidth - margin,
        footerY,
        { align: "right" }
      );
    }

    // Start page 2 here so the remaining investigation sections
    // never get clipped at the bottom of page 1.
    doc.addPage();

    // Page 2 header
    doc.setFillColor(7, 22, 30);
    doc.rect(0, 0, pageWidth, 32, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(20);
    doc.setTextColor(255, 255, 255);
    doc.text("SLICK", margin, 14);

    doc.setTextColor(24, 200, 189);
    doc.text("BACK", margin + 20, 14);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(170, 190, 198);
    doc.text(
      "MARITIME INTELLIGENCE CONSOLE",
      margin,
      21
    );

    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.setTextColor(255, 255, 255);
    doc.text(
      "OIL-SPILL INVESTIGATION REPORT",
      pageWidth - margin,
      14,
      { align: "right" }
    );

    y = 42;

    // Current position
    heading("3. CURRENT AIS POSITION");

    if (currentLat !== null && currentLon !== null) {
      doc.setFillColor(239, 245, 252);
      doc.roundedRect(margin, y, width, 28, 2, 2, "F");

      text(
        "Current latitude",
        currentLat.toFixed(6),
        margin + 5,
        y + 10,
        9,
        true
      );

      text(
        "Current longitude",
        currentLon.toFixed(6),
        margin + 75,
        y + 10,
        9,
        true
      );

      text(
        "Distance to candidate",
        `${number(vessel.distance_km, 2)} km`,
        margin + 135,
        y + 10,
        8,
        true
      );

      doc.setFont("helvetica", "normal");
      doc.setFontSize(7.5);
      doc.setTextColor(80, 100, 120);
      doc.text(
        "This represents the vessel's current AIS position in the analysis.",
        margin + 5,
        y + 21
      );

      y += 36;
    } else {
      doc.text(
        "Current AIS position unavailable.",
        margin,
        y
      );
      y += 12;
    }

    // Historical position
    heading("4. HISTORICAL POSITION / MOVEMENT");

    if (historical) {
      doc.setFillColor(250, 247, 239);
      doc.roundedRect(margin, y, width, 31, 2, 2, "F");

      text(
        "Historical latitude",
        Number(historical.latitude).toFixed(6),
        margin + 5,
        y + 10,
        9,
        true
      );

      text(
        "Historical longitude",
        Number(historical.longitude).toFixed(6),
        margin + 75,
        y + 10,
        9,
        true
      );

      text(
        "Historical source distance",
        `${number(investigation.source_distance_km, 2)} km`,
        margin + 135,
        y + 10,
        8,
        true
      );

      doc.setFont("helvetica", "bold");
      doc.setFontSize(7.5);
      doc.setTextColor(145, 95, 25);
      doc.text(
        "Historical position is an analytical estimate, NOT confirmed spill origin.",
        margin + 5,
        y + 23
      );

      y += 39;
    } else {
      doc.text(
        "No historical position estimate is available.",
        margin,
        y
      );
      y += 12;
    }

    // Assessment
    heading("5. INVESTIGATION ASSESSMENT");

    doc.setFillColor(242, 247, 248);
    doc.roundedRect(margin, y, width, 30, 2, 2, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(25, 80, 85);
    doc.text(
      assessmentShort(assessment),
      margin + 6,
      y + 10
    );

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(75, 85, 95);

    const assessmentLines = doc.splitTextToSize(
      "Composite indicator based on SAR proximity, AIS correlation, historical trajectory and AIS anomalies. This is an investigation lead, not legal proof of responsibility.",
      width - 12
    );

    doc.text(
      assessmentLines,
      margin + 6,
      y + 18
    );

    y += 40;

    // Conclusion
    heading("6. CONCLUSION");

    const conclusion = vessel
      ? `The primary detected spill candidate is located at ${spillLat.toFixed(6)}, ${spillLon.toFixed(6)}. The leading vessel is ${vessel.name || "Unknown vessel"} (MMSI ${vessel.mmsi || "—"}). Its current AIS position is ${currentLat !== null ? currentLat.toFixed(6) : "unavailable"}, ${currentLon !== null ? currentLon.toFixed(6) : "unavailable"}, approximately ${number(vessel.distance_km, 2)} km from the detected candidate.`
      : `The primary detected spill candidate is located at ${spillLat.toFixed(6)}, ${spillLon.toFixed(6)}. No vessel lead is currently available.`;

    const conclusionLines = doc.splitTextToSize(
      conclusion,
      width
    );

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(45, 55, 65);
    doc.text(conclusionLines, margin, y);

    y += conclusionLines.length * 5 + 8;

    // Disclaimer
    doc.setFillColor(250, 244, 244);
    doc.roundedRect(margin, y, width, 25, 2, 2, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.setTextColor(125, 55, 65);
    doc.text(
      "INVESTIGATION DISCLAIMER",
      margin + 5,
      y + 8
    );

    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(85, 70, 75);

    const disclaimerLines = doc.splitTextToSize(
      "The identified vessel is a lead for further investigation. The analysis does not establish legal responsibility or prove that the vessel caused the spill.",
      width - 10
    );

    doc.text(
      disclaimerLines,
      margin + 5,
      y + 15
    );

    // Footer on the final page
    const footerY = pageHeight - 10;

    doc.setDrawColor(190, 200, 205);
    doc.line(margin, footerY - 5, pageWidth - margin, footerY - 5);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(6.5);
    doc.setTextColor(110, 120, 130);
    doc.text(
      "SLICKBACK · Sentinel-1 SAR · AIS · Historical trajectory analysis",
      margin,
      footerY
    );

    doc.text(
      `Page 2 · ${new Date().toISOString()}`,
      pageWidth - margin,
      footerY,
      { align: "right" }
    );

    const vesselName = String(
      vessel?.name || "No_Vessel"
    ).replace(/[^a-z0-9]+/gi, "_");

    doc.save(
      `SlickBack_Investigation_${vesselName}.pdf`
    );
  } catch (error) {
    console.error("PDF generation failed:", error);
    alert(
      `PDF generation failed: ${error?.message || error}`
    );
  }
}

function App() {

  const [latitude, setLatitude] =
    useState(DEFAULT_LAT);

  const [longitude, setLongitude] =
    useState(DEFAULT_LON);

  const [observationTime, setObservationTime] =
    useState("2026-08-14T23:59:59Z");

  const [hoursBack, setHoursBack] =
    useState(48);

  const [data, setData] =
    useState(null);

  const [selectedCandidate, setSelectedCandidate] =
    useState(0);

  const [selectedVessel, setSelectedVessel] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState(null);


  /* ==========================================================
     ANALYZE
  ========================================================== */

  async function analyze() {

    setLoading(true);
    setError(null);
    setSelectedVessel(null);

    try {

      const response = await fetch(
        `${API}/analyze-spill`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            spill_lat: Number(latitude),
            spill_lon: Number(longitude),
            observation_time:
              observationTime,
            hours_back:
              Number(hoursBack),
          }),
        }
      );


      const result =
        await response.json();


      if (!response.ok) {
        throw new Error(
          result?.detail ||
          "Backend analysis failed."
        );
      }


      setData(result);
      setSelectedCandidate(0);

    } catch (err) {

      console.error(err);

      setError(
        err?.message ||
        "Unable to connect to backend."
      );

    } finally {

      setLoading(false);

    }
  }


  /* ==========================================================
     DATA
  ========================================================== */

  const candidates =
    data?.candidates || [];

  const current =
    candidates[selectedCandidate];

  const candidate =
    current?.candidate;

  const vessels =
    current?.nearby_vessels || [];


  /* ==========================================================
     MAP CENTER
  ========================================================== */

  const mapCenter = candidate
    ? [
        Number(candidate.latitude),
        Number(candidate.longitude),
      ]
    : [
        Number(latitude),
        Number(longitude),
      ];


  /* ==========================================================
     SELECTED VESSEL
  ========================================================== */

  const activeVessel =
    selectedVessel ||
    vessels[0] ||
    null;


  /* ==========================================================
     ANALYSIS SUMMARY
  ========================================================== */

  const investigationCount =
    useMemo(() => {

      return vessels.filter(
        (vessel) => {

          const assessment =
            String(
              vessel?.investigation
                ?.assessment || ""
            ).toUpperCase();

          return (
            assessment.includes(
              "INVESTIGATION"
            ) ||
            assessment.includes(
              "INTENTIONAL"
            )
          );

        }
      ).length;

    }, [vessels]);


  /* ==========================================================
     RENDER
  ========================================================== */

  return (

    <div className="app">


      {/* ======================================================
          HEADER
      ======================================================= */}

      <header className="topbar">

        <div className="brand-block">

          <div className="brand">
            SLICK<span>BACK</span>
          </div>

          <div className="product-name">
            MARITIME INTELLIGENCE CONSOLE
          </div>

        </div>


        <div className="system-status">

          <StatusDot />

          <span>
            SYSTEM OPERATIONAL
          </span>

        </div>

      </header>


      {/* ======================================================
          CONTROL BAR
      ======================================================= */}

      <section className="command-bar">

        <div className="command-title">

          <div className="eyebrow">
            INCIDENT ANALYSIS
          </div>

          <h1>
            Oil-spill investigation
          </h1>

        </div>


        <div className="controls">

          <div className="field">

            <label>
              LATITUDE
            </label>

            <input
              type="number"
              step="0.0001"
              value={latitude}
              onChange={(e) =>
                setLatitude(
                  e.target.value
                )
              }
            />

          </div>


          <div className="field">

            <label>
              LONGITUDE
            </label>

            <input
              type="number"
              step="0.0001"
              value={longitude}
              onChange={(e) =>
                setLongitude(
                  e.target.value
                )
              }
            />

          </div>


          <div className="field time-field">

            <label>
              OBSERVATION TIME
            </label>

            <input
              type="text"
              value={observationTime}
              onChange={(e) =>
                setObservationTime(
                  e.target.value
                )
              }
            />

          </div>


          <div className="field small-field">

            <label>
              AIS WINDOW
            </label>

            <div className="input-suffix">

              <input
                type="number"
                min="1"
                max="168"
                value={hoursBack}
                onChange={(e) =>
                  setHoursBack(
                    e.target.value
                  )
                }
              />

              <span>H</span>

            </div>

          </div>


          <button
            className="analyze-button"
            onClick={analyze}
            disabled={loading}
          >

            {loading ? (
              <>
                <span className="spinner" />
                ANALYZING
              </>
            ) : (
              <>
                ANALYZE INCIDENT
                <span className="button-arrow">
                  →
                </span>
              </>
            )}

          </button>

        </div>

      </section>


      {/* ======================================================
          ERROR
      ======================================================= */}

      {error && (

        <div className="error-banner">

          <strong>
            ANALYSIS ERROR
          </strong>

          <span>
            {error}
          </span>

        </div>

      )}


      {/* ======================================================
          MAIN WORKSPACE
      ======================================================= */}

      <main className="workspace">


        {/* ====================================================
            MAP
        ===================================================== */}

        <section className="map-section">

          <div className="map-header">

            <div>

              <div className="map-title">
                INCIDENT MAP
              </div>

              <div className="map-subtitle">
                Sentinel-1 SAR detection
                {" "}·{" "}
                AIS spatial correlation
              </div>

            </div>


            <div className="map-meta">

              <span>
                {data
                  ? `${candidates.length} candidates`
                  : "Awaiting analysis"}
              </span>

            </div>

          </div>


          <div className="map-wrapper">

            <MapContainer
              center={mapCenter}
              zoom={9}
              scrollWheelZoom={true}
              className="map"
            >

              <TileLayer
                attribution="© OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />


              <MapController
                position={candidate}
              />


              {/* ANALYSIS LOCATION */}

              <CircleMarker
                center={[
                  Number(latitude),
                  Number(longitude),
                ]}
                radius={7}
                pathOptions={{
                  color: "#18c8bd",
                  fillColor: "#18c8bd",
                  fillOpacity: 0.95,
                  weight: 2,
                }}
              >

                <Popup>

                  <strong>
                    Analysis location
                  </strong>

                  <br />

                  {latitude}, {longitude}

                </Popup>

              </CircleMarker>


              {/* ALL SPILL CANDIDATES */}

              {candidates.map(
                (item, index) => {

                  const c =
                    item?.candidate;

                  if (!c) {
                    return null;
                  }

                  const isSelected =
                    index ===
                    selectedCandidate;

                  return (

                    <CircleMarker
                      key={`candidate-${index}`}
                      center={[
                        Number(c.latitude),
                        Number(c.longitude),
                      ]}
                      radius={
                        isSelected
                          ? 12
                          : 7
                      }
                      pathOptions={{
                        color: isSelected
                          ? "#ff4655"
                          : "#e65b63",
                        fillColor: isSelected
                          ? "#ff4655"
                          : "#e65b63",
                        fillOpacity:
                          isSelected
                            ? 0.95
                            : 0.55,
                        weight:
                          isSelected
                            ? 3
                            : 1,
                      }}
                      eventHandlers={{
                        click: () =>
                          setSelectedCandidate(
                            index
                          ),
                      }}
                    >

                      <Popup>

                        <strong>
                          Spill candidate #
                          {index + 1}
                        </strong>

                        <br />

                        SAR contrast:{" "}
                        {number(
                          c.local_contrast_db,
                          2
                        )}
                        {" "}dB

                        <br />

                        Area:{" "}
                        {c.area_pixels}
                        {" "}px

                      </Popup>

                    </CircleMarker>

                  );

                }
              )}


              {/* VESSELS */}

              {vessels.map(
                (vessel, index) => {

                  if (
                    vessel?.latitude ===
                      undefined ||
                    vessel?.longitude ===
                      undefined
                  ) {
                    return null;
                  }

                  const investigation =
                    vessel?.investigation ||
                    {};

                  const isSelected =
                    activeVessel?.mmsi ===
                    vessel?.mmsi;

                  const historical =
                    investigation
                      ?.estimated_historical_position;


                  return (

                    <React.Fragment
                      key={
                        vessel?.mmsi ||
                        `vessel-${index}`
                      }
                    >

                      {/* CURRENT POSITION */}

                      <CircleMarker
                        center={[
                          Number(
                            vessel.latitude
                          ),
                          Number(
                            vessel.longitude
                          ),
                        ]}
                        radius={
                          isSelected
                            ? 9
                            : 6
                        }
                        pathOptions={{
                          color:
                            isSelected
                              ? "#ffffff"
                              : "#3978c9",
                          fillColor:
                            "#3978c9",
                          fillOpacity: 0.95,
                          weight:
                            isSelected
                              ? 3
                              : 1,
                        }}
                        eventHandlers={{
                          click: () =>
                            setSelectedVessel(
                              vessel
                            ),
                        }}
                      >

                        <Popup>

                          <strong>
                            {vessel?.name ||
                              "Unknown vessel"}
                          </strong>

                          <br />

                          MMSI:{" "}
                          {vessel?.mmsi}

                          <br />

                          Distance:{" "}
                          {number(
                            vessel?.distance_km,
                            1
                          )}
                          {" "}km

                        </Popup>

                      </CircleMarker>


                      {/* HISTORICAL POSITION */}

                      {historical && (

                        <>

                          <CircleMarker
                            center={[
                              Number(
                                historical.latitude
                              ),
                              Number(
                                historical.longitude
                              ),
                            ]}
                            radius={4}
                            pathOptions={{
                              color:
                                "#8bb5e8",
                              fillColor:
                                "#8bb5e8",
                              fillOpacity:
                                0.9,
                              weight: 1,
                            }}
                          />


                          <Polyline
                            positions={[
                              [
                                Number(
                                  vessel.latitude
                                ),
                                Number(
                                  vessel.longitude
                                ),
                              ],
                              [
                                Number(
                                  historical.latitude
                                ),
                                Number(
                                  historical.longitude
                                ),
                              ],
                            ]}
                            pathOptions={{
                              color:
                                "#6e9ed1",
                              weight: 1.5,
                              opacity: 0.65,
                              dashArray:
                                "5 6",
                            }}
                          />

                        </>

                      )}

                    </React.Fragment>

                  );

                }
              )}

            </MapContainer>


            <div className="map-overlay">

              <div className="overlay-title">
                LIVE INVESTIGATION VIEW
              </div>

              <div className="overlay-text">
                SAR candidate field
                {" "}·{" "}
                AIS vessel positions
                {" "}·{" "}
                historical movement
              </div>

            </div>


            <Legend />

          </div>

        </section>


        {/* ====================================================
            INVESTIGATION PANEL
        ===================================================== */}

        <aside className="investigation-panel">


          {/* PANEL HEADER */}

          <div className="panel-header">

            <div>

              <div className="eyebrow">
                INVESTIGATION
              </div>

              <h2>
                Evidence review
              </h2>

            </div>


            {data && (

              <div className="analysis-state">

                <StatusDot />

                COMPLETE

              </div>

            )}

          </div>


          {/* EMPTY STATE */}

          {!data && !loading && (

            <div className="empty-state">

              <div className="empty-icon">
                +
              </div>

              <h3>
                No active investigation
              </h3>

              <p>
                Enter an incident location
                and run the analysis to
                inspect SAR candidates and
                nearby AIS vessels.
              </p>

            </div>

          )}


          {/* LOADING */}

          {loading && (

            <div className="loading-state">

              <div className="loading-bar">
                <span />
              </div>

              <div className="loading-title">
                PROCESSING INCIDENT
              </div>

              <div className="loading-text">
                Retrieving Sentinel-1
                evidence and correlating
                AIS history.
              </div>

            </div>

          )}


          {/* RESULTS */}

          {data && !loading && (

            <>

              {/* SUMMARY */}

              <section className="summary-strip">

                <div className="summary-item">

                  <span>
                    SOURCE
                  </span>

                  <strong>
                    {data.satellite
                      ?.mission ||
                      "Sentinel-1"}
                  </strong>

                </div>


                <div className="summary-item">

                  <span>
                    CANDIDATES
                  </span>

                  <strong>
                    {data.detection
                      ?.candidate_count ??
                      candidates.length}
                  </strong>

                </div>


                <div className="summary-item">

                  <span>
                    INVESTIGATE
                  </span>

                  <strong>
                    {investigationCount}
                  </strong>

                </div>

              </section>


              {/* CANDIDATE SELECTOR */}

              {candidates.length > 0 && (

                <section className="section-block">

                  <div className="section-heading">

                    <span>
                      DETECTED SPILL
                    </span>

                    <span className="section-count">
                      {candidates.length}
                    </span>

                  </div>


                  <select
                    className="candidate-select"
                    value={selectedCandidate}
                    onChange={(e) => {

                      setSelectedCandidate(
                        Number(e.target.value)
                      );

                      setSelectedVessel(null);

                    }}
                  >

                    {candidates
                      .slice(0, 20)
                      .map(
                        (item, index) => (

                          <option
                            key={index}
                            value={index}
                          >
                            Candidate #
                            {index + 1}
                            {" · "}
                            {number(
                              item?.candidate
                                ?.local_contrast_db,
                              2
                            )}
                            {" "}dB
                          </option>

                        )
                      )}

                  </select>


                  {/* CANDIDATE DETAILS */}

                  {candidate && (

                    <div className="candidate-detail">

                      <div className="candidate-location">

                        <div>

                          <span>
                            LATITUDE
                          </span>

                          <strong>
                            {number(
                              candidate.latitude,
                              5
                            )}
                          </strong>

                        </div>


                        <div>

                          <span>
                            LONGITUDE
                          </span>

                          <strong>
                            {number(
                              candidate.longitude,
                              5
                            )}
                          </strong>

                        </div>

                      </div>


                      <div className="candidate-metrics">

                        <Metric
                          label="SAR contrast"
                          value={`${number(
                            candidate.local_contrast_db,
                            2
                          )} dB`}
                        />

                        <Metric
                          label="Detected area"
                          value={`${candidate.area_pixels} px`}
                        />

                        <Metric
                          label="Threshold"
                          value={`${number(
                            data.detection
                              ?.adaptive_threshold_db,
                            2
                          )} dB`}
                        />

                      </div>

                    </div>

                  )}

                </section>

              )}


              {/* VESSEL LIST */}

              <section className="section-block vessel-section">

                <div className="section-heading">

                  <span>
                    VESSEL LEADS
                  </span>

                  <span className="section-count">
                    {vessels.length}
                  </span>

                </div>


                {vessels.length === 0 ? (

                  <div className="no-vessels">
                    No nearby vessels found.
                  </div>

                ) : (

                  <div className="vessel-list">

                    {vessels.map(
                      (vessel, index) => (

                        <VesselCard
                          key={
                            vessel?.mmsi ||
                            index
                          }
                          vessel={vessel}
                          index={index}
                          selected={
                            activeVessel?.mmsi ===
                            vessel?.mmsi
                          }
                          onSelect={
                            setSelectedVessel
                          }
                        />

                      )
                    )}

                  </div>

                )}

              </section>


              {/* SELECTED VESSEL DETAIL */}

              {activeVessel && (

                <section className="selected-vessel">

                  <div className="selected-vessel-header">

                    <div>

                      <div className="eyebrow">
                        SELECTED LEAD
                      </div>

                      <h3>
                        {activeVessel.name ||
                          "Unknown vessel"}
                      </h3>

                      <div className="selected-mmsi">
                        MMSI{" "}
                        {activeVessel.mmsi}
                      </div>

                    </div>

                  </div>


                  <div className="detail-grid">

                    <Metric
                      label="Priority"
                      value={number(
                        activeVessel
                          .responsibility_score,
                        1
                      )}
                    />

                    <Metric
                      label="AIS correlation"
                      value={number(
                        activeVessel
                          .correlation_score,
                        3
                      )}
                    />

                    <Metric
                      label="Distance"
                      value={`${number(
                        activeVessel.distance_km,
                        1
                      )} km`}
                    />

                    <Metric
                      label="AIS reliability"
                      value={number(
                        activeVessel
                          .ais_reliability,
                        2
                      )}
                    />

                    <Metric
                      label="AIS gap"
                      value={`${number(
                        activeVessel
                          .investigation
                          ?.ais_gap_hours,
                        1
                      )} hrs`}
                    />

                    <Metric
                      label="Source distance"
                      value={`${number(
                        activeVessel
                          .investigation
                          ?.source_distance_km,
                        1
                      )} km`}
                    />

                  </div>


                  {/* FLAGS */}

                  {activeVessel
                    ?.investigation
                    ?.flags
                    ?.length > 0 && (

                    <div className="flag-list">

                      {activeVessel
                        .investigation
                        .flags
                        .map(
                          (flag, index) => (

                            <span
                              className="flag"
                              key={index}
                            >
                              {flag}
                            </span>

                          )
                        )}

                    </div>

                  )}


                  {/* ASSESSMENT */}

                  <div
                    className={`assessment-box ${
                      assessmentTone(
                        activeVessel
                          ?.investigation
                          ?.assessment
                      )
                    }`}
                  >

                    <div className="assessment-heading">

                      <span>
                        INVESTIGATION ASSESSMENT
                      </span>

                    </div>

                    <strong>
                      {assessmentShort(
                        activeVessel
                          ?.investigation
                          ?.assessment
                      )}
                    </strong>

                    <p>
                      Composite indicator based
                      on SAR proximity, AIS
                      correlation, historical
                      trajectory and AIS
                      anomalies. This is an
                      investigation lead, not
                      legal proof of responsibility.
                    </p>

                  </div>

                  <button
                    type="button"
                    className="report-button"
                    onClick={() =>
                      generatePDFReport({
                        data,
                        candidate,
                        activeVessel,
                        latitude,
                        longitude,
                        observationTime,
                        hoursBack,
                      })
                    }
                  >
                    GENERATE INVESTIGATION REPORT
                    <span>PDF →</span>
                  </button>

                </section>

              )}

            </>

          )}

        </aside>

      </main>


      {/* ======================================================
          FOOTER
      ======================================================= */}

      <footer className="footer">

        <span>
          SLICKBACK
        </span>

        <span>
          Sentinel-1 SAR · AIS ·
          Historical trajectory analysis
        </span>

        <span>
          Investigation indicators are
          not legal proof of responsibility.
        </span>

      </footer>

    </div>
  );
}


/* ============================================================
   START
============================================================ */

createRoot(
  document.getElementById("root")
).render(
  <App />
);