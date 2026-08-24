import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MapContainer, TileLayer, Circle, Marker, Popup, Polyline} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './styles.css';

const API='http://localhost:8000';

function App(){
  const [data,setData]=useState(null);
  const [loading,setLoading]=useState(false);
  const [hours,setHours]=useState(6);

  async function analyze(){
    setLoading(true);
    const res=await fetch(`${API}/analyze-spill`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({spill_lat:18.75,spill_lon:72.65,observation_time:'2026-08-24T10:00:00',hours_back:hours})});
    setData(await res.json());
    setLoading(false);
  }

  const center=[18.75,72.65];
  return <div className="app">
    <header><div><div className="brand">SLICK<span>BACK</span></div><div className="tag">MARITIME OIL-SPILL INVESTIGATION</div></div><button onClick={analyze}>{loading?'ANALYZING...':'RUN INVESTIGATION'}</button></header>
    <main>
      <section className="map-panel">
        <MapContainer center={center} zoom={8} scrollWheelZoom className="map">
          <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Circle center={center} radius={8000} pathOptions={{color:'#ff4d4d'}} />
          {data && <>
            <Circle center={[data.source_reconstruction.source_lat,data.source_reconstruction.source_lon]} radius={data.source_reconstruction.uncertainty_radius_km*1000} pathOptions={{color:'#00e5ff',fillOpacity:.12}} />
            <Marker position={[data.source_reconstruction.source_lat,data.source_reconstruction.source_lon]}><Popup>Probable source region</Popup></Marker>
          </>}
        </MapContainer>
        <div className="map-overlay"><b>INCIDENT MAP</b><br/><span>Red = observed slick · Cyan = source probability</span></div>
      </section>
      <aside>
        <div className="control card"><label>Temporal Rewind</label><input type="range" min="1" max="24" value={hours} onChange={e=>setHours(+e.target.value)}/><div className="range"><span>-{hours}h</span><span>NOW</span></div></div>
        {!data ? <div className="card empty"><h2>Awaiting investigation</h2><p>Run the baseline pipeline first. Then we'll deliberately break it with look-alikes, AIS gaps and spoofing.</p></div> : <>
          <div className="card"><div className="eyebrow">DETECTION</div><div className="big">{data.incident.slick.detection_confidence}%</div><div>Probable oil · {data.incident.slick.area_km2} km²</div></div>
          <div className="card"><div className="eyebrow">SOURCE RECONSTRUCTION</div><div className="coords">{data.source_reconstruction.source_lat}, {data.source_reconstruction.source_lon}</div><div>± {data.source_reconstruction.uncertainty_radius_km} km · {data.source_reconstruction.particle_count} particles</div></div>
          <div className="card"><div className="eyebrow">CANDIDATE VESSELS</div>{data.candidates.map((v,i)=><div className="vessel" key={v.mmsi}><div><b>#{i+1} {v.name}</b><small>{v.distance_km} km · AIS trust {v.ais_trust}%</small>{v.flags.map(f=><em key={f}>{f}</em>)}</div><strong>{v.overall_score}</strong></div>)}</div>
          <div className="card warning">{data.disclaimer}</div>
        </>}
      </aside>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App/>);
