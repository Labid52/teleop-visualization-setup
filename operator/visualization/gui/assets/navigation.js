/* MapLibre runs in a separate Qt WebEngine renderer. Only position/course cross
 * this bridge: no source credentials or other telemetry enter this document. */
"use strict";
const demo = location.hash === "#demo";
const state = document.getElementById("state");
let map, marker, pending=null, first=true, following=true, lastCourse=0, animation=0;
let displayedPosition=null;
const FOLLOW_DISTANCE_M=2;
window.navigationStatus = {loaded:false, tilesLoaded:false, errors:0, updates:0,
    follow:true, pitch:48, marker:"triangle", demo:demo, cameraMoves:0, missingImages:0};

function distanceMeters(a,b) {
    const rad=Math.PI/180, dlat=(b[1]-a[1])*rad, dlon=(b[0]-a[0])*rad;
    const h=Math.sin(dlat/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dlon/2)**2;
    return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));
}

function numericFilter(expression) {
    if(!Array.isArray(expression))return expression;
    const [op,field,bound]=expression;
    if(["<","<=",">",">="].includes(op) && Array.isArray(field) && field[0]==="get" && typeof bound==="number") {
        // Missing numeric properties must fail this comparison, not warn or
        // manufacture a label/shield. Retain the existing filter otherwise.
        const outside=op.startsWith("<")?bound+1:bound-1;
        // to-number(null) is zero, so coalesce null before numeric conversion.
        return [op,["to-number",["coalesce",field,outside],outside],bound];
    }
    return expression.map(numericFilter);
}

function demoStyle() {
    // Fictional geometry near the configurable mock origin. Never used in WAN mode.
    const roads=[], blocks=[];
    for (let i=-12; i<=12; i++) {
        const offset=i*.001;
        roads.push({type:"Feature",geometry:{type:"LineString",coordinates:[[-97.015,35+offset],[-96.985,35+offset]]}});
        roads.push({type:"Feature",geometry:{type:"LineString",coordinates:[[-97+offset,34.985],[-97+offset,35.015]]}});
        for(let j=-12;j<12;j++) {
            const x=-97+j*.001+.00016, y=35+offset+.00016;
            blocks.push({type:"Feature",properties:{height:6+(i+j+24)%5*3},geometry:{type:"Polygon",coordinates:[[[x,y],[x+.00065,y],[x+.00065,y+.00065],[x,y+.00065],[x,y]]]}});
        }
    }
    return {version:8,sources:{roads:{type:"geojson",data:{type:"FeatureCollection",features:roads}},
      blocks:{type:"geojson",data:{type:"FeatureCollection",features:blocks}}},layers:[
      {id:"background",type:"background",paint:{"background-color":"#eeece7"}},
      {id:"roads-casing",type:"line",source:"roads",paint:{"line-color":"#8a98a3","line-width":9}},
      {id:"roads",type:"line",source:"roads",paint:{"line-color":"#ffffff","line-width":6}},
      {id:"blocks",type:"fill-extrusion",source:"blocks",paint:{"fill-extrusion-color":"#c5cbd0","fill-extrusion-height":["get","height"],"fill-extrusion-opacity":.85}}
    ]};
}

function finishStatus() {
    window.navigationStatus.tilesLoaded=map.areTilesLoaded();
    state.textContent = !pending ? "WAITING FOR POSITION" : pending.stale ? "LAST KNOWN POSITION" : demo ? "SIMULATION" : "";
    state.style.display=state.textContent ? "block" : "none";
}

try {
    // Positron has no fill-pattern dependencies or dynamic POI icons. The dark
    // style requests a wood-pattern texture absent from its declared atlas.
    map = new maplibregl.Map({container:"map", style:demo ? demoStyle() : "https://tiles.openfreemap.org/styles/positron",
        center: demo ? [-97,35] : [0,0], zoom:demo?16.4:1, pitch:48, bearing:0,
        attributionControl:true, antialias:true, maxPitch:60, refreshExpiredTiles:true});
    const arrow=document.createElement("div");arrow.className="vehicle";
    arrow.innerHTML='<svg viewBox="0 0 42 52" xmlns="http://www.w3.org/2000/svg"><path d="M21 3 L38 46 L21 36 L4 46 Z" fill="#69cff9" stroke="#d2f3ff" stroke-width="2"/><path d="M21 9 L21 34 L8 42 Z" fill="#318ab3"/></svg>';
    marker = new maplibregl.Marker({element:arrow,rotationAlignment:"map",pitchAlignment:"map",subpixelPositioning:true});
    map.on("style.load",()=>{
        if(demo)return;
        // Operator-only navigation palette: stronger roads, restrained land and
        // water. Preserve the provider's geometry, labels and road hierarchy.
        const colors=[
            ["background","background-color","#eeece7"],
            ["water","fill-color","#b6d7e8"],
            ["waterway","line-color","#a6cbdc"],
            ["park","fill-color","#dce6d1"],
            ["landcover_wood","fill-color","#d3dfc8"],
            ["building","fill-color","#d4d7d7"],
            ["building","fill-outline-color","#b7c0c5"],
            ["highway_minor","line-color","#8d9da8"],
            ["highway_major_casing","line-color","#8a9ca6"],
            ["highway_motorway_casing","line-color","#b7a58a"],
            ["highway_motorway_inner","line-color","#f8e3b7"]
        ];
        colors.forEach(([id,property,color])=>{if(map.getLayer(id))map.setPaintProperty(id,property,color);});
        // Provider filters assume ref_length/rank/admin_level always exist;
        // unnumbered roads and other features legitimately omit these fields.
        for(const layer of map.getStyle().layers) {
            if(layer.filter)map.setFilter(layer.id,numericFilter(layer.filter));
        }
    });
    map.on("load",()=>{
        window.navigationStatus.loaded=true;
        if (pending) applyPosition(pending);
        finishStatus();
    });
    map.on("idle",finishStatus);
    map.on("error",()=>{window.navigationStatus.errors++;state.textContent="MAP CONNECTION INTERRUPTED";state.style.display="block";});
    map.on("styleimagemissing",()=>{window.navigationStatus.missingImages++;});
    map.on("moveend",()=>{window.navigationStatus.center=map.getCenter().toArray();});
    // Only an actual user pan suspends follow, never a programmatic camera move.
    map.on("dragstart",event=>{if(event.originalEvent){following=false;window.navigationStatus.follow=false;}});
    window.recenter=()=>{following=true;window.navigationStatus.follow=true;if(pending) applyPosition(pending,true);};
    window.zoomMap=(delta)=>map.easeTo({zoom:Math.max(3,Math.min(19,map.getZoom()+delta)),duration:250});
    window.setPerspective=(enabled)=>{map.easeTo({pitch:enabled?48:0,duration:450});window.navigationStatus.pitch=enabled?48:0;};
    window.receivePosition=(value)=>{pending=value;window.navigationStatus.updates++;if(window.navigationStatus.loaded) applyPosition(value);};
    function applyPosition(value,force=false) {
        const target=[value.lon,value.lat];
        window.navigationStatus.position=target;window.navigationStatus.course=value.course;
        marker.getElement().classList.toggle("stale",value.stale);
        // Retain the last known marker on stale updates; never chase cached data.
        if(value.stale) { finishStatus();return; }
        const moved=displayedPosition===null || distanceMeters(displayedPosition,target)>=FOLLOW_DISTANCE_M;
        // Compare against the last DISPLAYED position so slow motion accumulates.
        // Heading-only noise must not rotate a stationary marker or the map.
        if(!first && !moved && !force) { finishStatus();return; }
        if (Number.isFinite(value.course)) lastCourse=value.course;
        displayedPosition=target;
        if(first) { marker.setLngLat(target).setRotation(lastCourse).addTo(map);map.jumpTo({center:target,zoom:16.4,bearing:lastCourse,pitch:48});first=false;window.navigationStatus.cameraMoves++; }
        else {
            const from=marker.getLngLat(), rotation=marker.getRotation(), turn=((lastCourse-rotation+540)%360)-180;
            const started=performance.now();cancelAnimationFrame(animation);
            const animate=(now)=>{const t=Math.min(1,(now-started)/180);
                marker.setLngLat([from.lng+(target[0]-from.lng)*t,from.lat+(target[1]-from.lat)*t]).setRotation(rotation+turn*t);
                if(t<1) animation=requestAnimationFrame(animate);};
            animation=requestAnimationFrame(animate);
            // Complete before the next 200 ms bridge update, avoiding perpetual
            // easing restarts that can leave the camera trailing the marker.
            if(following) {map.easeTo({center:target,bearing:lastCourse,duration:180,essential:true});window.navigationStatus.cameraMoves++;}
        }
        finishStatus();
    }
    window.addEventListener("resize",()=>map.resize());
} catch(error) {
    window.navigationStatus.errors++; state.textContent="MAP UNAVAILABLE";
}
