/**
 * ParkVoice Offline PWA - Application Logic
 * Integrates:
 * - Dual Input (Interactive Text Box + Microphone Dictation)
 * - Real-Time AudioContext Waveform Visualizer
 * - 100% Offline Faster-Whisper Speech-to-Text
 * - Qwen 3 (llama.cpp) Agent Orchestrator & Fallback
 * - OpenStreetMap MCP Server (100% Offline SQLite Spatial DB)
 * - Offline Piper Neural Text-to-Speech
 * - Interactive Leaflet Map with Routing, Custom Pins & Dynamic Filters
 */

// ==========================================
// 1. Application State
// ==========================================
const state = {
  latitude: 13.0827,
  longitude: 80.2707,
  radiusMeters: 5000,
  landmarkName: "Chennai Central",
  sttEngine: "whisper",
  ttsEngine: "piper",
  autoPlaySpeech: true,

  // Voice & Audio Recording
  isRecording: false,
  isProcessing: false,
  mediaRecorder: null,
  audioChunks: [],
  recordingStartTime: null,
  recordingInterval: null,
  audioContext: null,
  analyser: null,
  visualizerAnimId: null,

  // Audio Playback
  audioPlayer: new Audio(),
  playbackSpeed: 1.0,

  // Data & Results
  parkingSpots: [],
  activeFilter: "all",
  activeSort: "distance",
  showRadiusCircle: true,
  currentRoutePolyline: null,
  routeCasingLayer: null,
  routeLineLayer: null,
  originMarker: null,
  destinationMarker: null,
  pendingRouteDestination: null,
  activeRoute: null,
  navAudioBase64: null,
  isPickingOriginOnMap: false,
  offlineRegions: [],
  mcpTrace: [],
  searchedLocation: null
};

// ==========================================
// 2. DOM Elements Binding
// ==========================================
// Header & Status
const headerLocationPill = document.getElementById("headerLocationPill");
const locLandmarkName = document.getElementById("locLandmarkName");
const locCoordinatesText = document.getElementById("locCoordinatesText");
const statusPillLlm = document.getElementById("statusPillLlm");
const statusPillMcp = document.getElementById("statusPillMcp");
const statusPillStt = document.getElementById("statusPillStt");
const statusPillTts = document.getElementById("statusPillTts");
const badgeTotalSpots = document.getElementById("badgeTotalSpots");
const badgeTotalSpotsModal = document.getElementById("badgeTotalSpotsModal");
const btnClearChat = document.getElementById("btnClearChat");
const btnSettings = document.getElementById("btnSettings");

// Mobile Navigation Tabs
const tabBtnChat = document.getElementById("tabBtnChat");
const tabBtnMap = document.getElementById("tabBtnMap");
const panelLeft = document.getElementById("panelLeft");
const panelRight = document.getElementById("panelRight");
const mobileSpotsCount = document.getElementById("mobileSpotsCount");

// Dialogue & Session
const dialogueContainer = document.getElementById("dialogueContainer");
const welcomeCard = document.getElementById("welcomeCard");
const timingsBadge = document.getElementById("timingsBadge");
const sessionStatusBadge = document.getElementById("sessionStatusBadge");

// Initial Bubble Elements (for backward-compatibility)
const assistantText = document.getElementById("assistantText");
const assistantBubbleTime = document.getElementById("assistantBubbleTime");
const audioControlBar = document.getElementById("audioControlBar");
const btnPlayAudio = document.getElementById("btnPlayAudio");
const playIcon = document.getElementById("playIcon");
const audioProgressBarContainer = document.getElementById("audioProgressBarContainer");
const audioProgressFill = document.getElementById("audioProgressFill");
const audioDuration = document.getElementById("audioDuration");
const btnAudioSpeed = document.getElementById("btnAudioSpeed");
const btnReplayAudio = document.getElementById("btnReplayAudio");

// MCP Inspector
const btnToggleMcp = document.getElementById("btnToggleMcp");
const mcpInspectorContent = document.getElementById("mcpInspectorContent");
const mcpJsonTrace = document.getElementById("mcpJsonTrace");
const mcpCountBadge = document.getElementById("mcpCountBadge");
const btnCopyMcpTrace = document.getElementById("btnCopyMcpTrace");

// Voice Recording Overlay
const voiceRecordingOverlay = document.getElementById("voiceRecordingOverlay");
const voiceStateText = document.getElementById("voiceStateText");
const recordingTimer = document.getElementById("recordingTimer");
const visualizerCanvas = document.getElementById("visualizerCanvas");
const visualizerCtx = visualizerCanvas.getContext("2d");
const btnCancelRecording = document.getElementById("btnCancelRecording");
const btnFinishRecording = document.getElementById("btnFinishRecording");

// Unified Input Dock (Text Box + Inline Microphone)
const inputForm = document.getElementById("inputForm");
const queryInput = document.getElementById("queryInput");
const btnInputMic = document.getElementById("btnInputMic");
const btnSendQuery = document.getElementById("btnSendQuery");
const btnClearInput = document.getElementById("btnClearInput");
const sttModeIndicator = document.getElementById("sttModeIndicator");
const quickPromptsList = document.getElementById("quickPromptsList");

// Map & Parking Results
const mapContainer = document.getElementById("map");
const btnLocateMe = document.getElementById("btnLocateMe");
const btnFitMap = document.getElementById("btnFitMap");
const btnToggleRadius = document.getElementById("btnToggleRadius");
const btnSearchArea = document.getElementById("btnSearchArea");
const locationLabelPill = document.getElementById("locationLabelPill");
const resultsCountSubtitle = document.getElementById("resultsCountSubtitle");
const parkingList = document.getElementById("parkingList");
const selectSortBy = document.getElementById("selectSortBy");
const filterPillsContainer = document.getElementById("filterPillsContainer");

// Settings Modal Elements
const settingsModal = document.getElementById("settingsModal");
const btnCloseSettings = document.getElementById("btnCloseSettings");
const btnApplySettings = document.getElementById("btnApplySettings");
const btnResetSettings = document.getElementById("btnResetSettings");
const selectLocationPreset = document.getElementById("selectLocationPreset");
const inputLat = document.getElementById("inputLat");
const inputLon = document.getElementById("inputLon");
const inputRadius = document.getElementById("inputRadius");
const radiusVal = document.getElementById("radiusVal");
const selectSttEngine = document.getElementById("selectSttEngine");
const selectTtsEngine = document.getElementById("selectTtsEngine");
const checkboxAutoPlay = document.getElementById("checkboxAutoPlay");
const btnDownloadRegion = document.getElementById("btnDownloadRegion");
const selectDownloadRegion = document.getElementById("selectDownloadRegion");
const downloadStatusText = document.getElementById("downloadStatusText");
const toastContainer = document.getElementById("toastContainer");

// Dynamic Region Search & Mirror Checker
const inputSearchRegion = document.getElementById("inputSearchRegion");
const btnSearchRegion = document.getElementById("btnSearchRegion");
const regionSearchResultBox = document.getElementById("regionSearchResultBox");
const regionResultTitle = document.getElementById("regionResultTitle");
const regionResultCoords = document.getElementById("regionResultCoords");
const btnDownloadFoundRegion = document.getElementById("btnDownloadFoundRegion");
const btnSetAsMapPosition = document.getElementById("btnSetAsMapPosition");
const mirrorStatusAlert = document.getElementById("mirrorStatusAlert");

// Navigation HUD Elements
const navHudBanner = document.getElementById("navHudBanner");
const navHudIcon = document.getElementById("navHudIcon");
const navHudStep = document.getElementById("navHudStep");
const navHudDistance = document.getElementById("navHudDistance");
const navHudDuration = document.getElementById("navHudDuration");
const navSourceTag = document.getElementById("navSourceTag");
const btnNavVoice = document.getElementById("btnNavVoice");
const btnToggleNavSteps = document.getElementById("btnToggleNavSteps");
const btnCloseNav = document.getElementById("btnCloseNav");
const navStepsDrawer = document.getElementById("navStepsDrawer");
const navStepsList = document.getElementById("navStepsList");
const navTotalStepsBadge = document.getElementById("navTotalStepsBadge");

// Navigation Origin Selection Modal Elements
const modalPickOrigin = document.getElementById("modalPickOrigin");
const btnClosePickOrigin = document.getElementById("btnClosePickOrigin");
const btnCancelPickOrigin = document.getElementById("btnCancelPickOrigin");
const btnConfirmStartNav = document.getElementById("btnConfirmStartNav");
const navDestName = document.getElementById("navDestName");
const navDestAddress = document.getElementById("navDestAddress");
const navDestDistance = document.getElementById("navDestDistance");
const navCurrentOriginDesc = document.getElementById("navCurrentOriginDesc");
const selectOriginRegion = document.getElementById("selectOriginRegion");
const inputCustomOrigin = document.getElementById("inputCustomOrigin");
const checkboxNavVoice = document.getElementById("checkboxNavVoice");
const btnRefreshOfflineRegions = document.getElementById("btnRefreshOfflineRegions");
const btnUseGpsModal = document.getElementById("btnUseGpsModal");

// Leaflet Map Handles
let map = null;
let userMarker = null;
let radiusCircle = null;
let parkingMarkersLayer = null;

// ==========================================
// 3. Service Worker Registration
// ==========================================
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js")
      .then((reg) => {
        console.log("[PWA] Service Worker registered:", reg.scope);
        // Force check for fresh updates on every reload
        reg.update();
      })
      .catch((err) => console.warn("[PWA] Service Worker registration failed:", err));
  });
}

// ==========================================
// 4. Leaflet Map Initialization & Controls
// ==========================================
function initMap() {
  if (!mapContainer) return;

  map = L.map("map", {
    center: [state.latitude, state.longitude],
    zoom: 15,
    zoomControl: false
  });

  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Standard OpenStreetMap tiles (offline cached by Service Worker)
  const tileUrl = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  L.tileLayer(tileUrl, {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors (Offline Spatial DB)"
  }).addTo(map);

  // Custom User Location Pin
  const userIcon = L.divIcon({
    className: "custom-pin-user-wrapper",
    html: '<div class="custom-pin-user"></div>',
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  userMarker = L.marker([state.latitude, state.longitude], { icon: userIcon }).addTo(map);
  userMarker.bindPopup(`
    <div style="font-family: inherit; font-size: 13px; line-height: 1.4;">
      <b style="color: #3b82f6;">📍 Your Current Position</b><br>
      <span>${state.landmarkName}</span><br>
      <span style="color: #94a3b8; font-size: 11px;">${state.latitude.toFixed(4)}° N, ${state.longitude.toFixed(4)}° E</span>
    </div>
  `);

  // Search Radius Circle
  radiusCircle = L.circle([state.latitude, state.longitude], {
    radius: state.radiusMeters,
    color: "#3b82f6",
    fillColor: "#3b82f6",
    fillOpacity: 0.08,
    weight: 1.5,
    dashArray: "4, 6"
  }).addTo(map);

  parkingMarkersLayer = L.layerGroup().addTo(map);

  // Map click handler (supports both setting coordinates and picking route start point)
  map.on("click", (e) => {
    if (state.isPickingOriginOnMap && state.pendingRouteDestination) {
      state.isPickingOriginOnMap = false;
      const dest = state.pendingRouteDestination;
      showToast(`Selected origin point on map. Calculating road route to ${dest.name}...`, "info");
      executeRoadNavigation(
        e.latlng.lat,
        e.latlng.lng,
        dest.latitude,
        dest.longitude,
        "Custom Pickup Point",
        dest.name,
        checkboxNavVoice ? checkboxNavVoice.checked : true
      );
      return;
    }
    updateUserLocation(e.latlng.lat, e.latlng.lng, "Custom Map Pin");
    showToast(`Location set to ${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`, "info");
  });
}

function updateUserLocation(lat, lon, landmark = null) {
  state.latitude = parseFloat(lat.toFixed(5));
  state.longitude = parseFloat(lon.toFixed(5));
  if (landmark) {
    state.landmarkName = landmark;
  }

  if (userMarker) {
    userMarker.setLatLng([state.latitude, state.longitude]);
  }
  if (radiusCircle) {
    radiusCircle.setLatLng([state.latitude, state.longitude]);
  }
  if (map) {
    map.panTo([state.latitude, state.longitude]);
  }

  // Update Header & Inputs
  if (locLandmarkName) locLandmarkName.textContent = state.landmarkName;
  if (locCoordinatesText) locCoordinatesText.textContent = `${state.latitude}° N, ${state.longitude}° E`;
  if (locationLabelPill) locationLabelPill.textContent = `📍 ${state.latitude}° N, ${state.longitude}° E • ${state.landmarkName}`;
  if (inputLat) inputLat.value = state.latitude;
  if (inputLon) inputLon.value = state.longitude;

  // Clear existing route polyline
  clearRouteNavigation();
}

function renderParkingMarkers(spots) {
  if (!parkingMarkersLayer) return;
  parkingMarkersLayer.clearLayers();
  clearRouteNavigation();

  if (!spots || spots.length === 0) return;

  const bounds = [];
  bounds.push([state.latitude, state.longitude]);

  spots.forEach((spot, idx) => {
    const isFree = spot.fee === "free" || spot.fee === "no" || spot.fee === "0";
    let pinClass = "custom-pin-parking";
    if (spot.parking_type === "multi-storey" || spot.parking_type === "underground") {
      pinClass += " multilevel";
    } else if (isFree) {
      pinClass += " free";
    } else if (spot.fee !== "unknown") {
      pinClass += " paid";
    }

    const pinIcon = L.divIcon({
      className: "custom-pin-wrapper",
      html: `<div class="${pinClass}"><span>${idx + 1}</span></div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
      popupAnchor: [0, -28]
    });

    const marker = L.marker([spot.latitude, spot.longitude], { icon: pinIcon });
    bounds.push([spot.latitude, spot.longitude]);

    const feeText = isFree ? "Free" : (spot.fee || "Unknown fee");
    const feeColor = isFree ? "#10b981" : "#f59e0b";

    const popupHtml = `
      <div style="min-width: 220px; font-family: inherit; font-size: 12px; line-height: 1.4;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
          <h4 style="margin: 0; font-size: 14px; font-weight: 700; color: #f8fafc;">${idx + 1}. ${escapeHtml(spot.name)}</h4>
        </div>
        <div style="color: #94a3b8; margin-bottom: 6px;">
          📍 <b>${spot.distance_text}</b> away • <span style="text-transform: capitalize;">${spot.parking_type}</span>
        </div>
        <div style="display: flex; gap: 6px; margin-bottom: 8px;">
          <span style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; padding: 2px 6px; border-radius: 4px; font-size: 11px;">
            🚗 ${spot.capacity > 0 ? spot.capacity + ' spots' : 'Available'}
          </span>
          <span style="background: rgba(16, 185, 129, 0.15); color: ${feeColor}; padding: 2px 6px; border-radius: 4px; font-size: 11px;">
            💵 ${feeText}
          </span>
        </div>
        <div style="font-size: 11px; color: #64748b; margin-bottom: 10px;">
          🕒 Hours: ${spot.opening_hours || '24/7'} • ♿ ${spot.wheelchair || 'Standard'}
        </div>
        <div style="display: flex; gap: 6px;">
          <button onclick="window.routeToSpot(${idx})" style="
            flex: 1; padding: 6px 10px; background: #3b82f6; color: white;
            border: none; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer;
          ">🧭 Navigate / Route</button>
          <button onclick="window.focusSpot(${idx})" style="
            padding: 6px 10px; background: #1e293b; color: #cbd5e1;
            border: 1px solid #334155; border-radius: 6px; font-size: 11px; cursor: pointer;
          ">View Card</button>
        </div>
      </div>
    `;

    marker.bindPopup(popupHtml);
    marker.on("click", () => highlightSpotCard(idx));
    parkingMarkersLayer.addLayer(marker);
  });

  // Fit bounds to show exact radius circle and all parking markers
  if (map) {
    if (radiusCircle && bounds.length > 1) {
      try {
        const circleBounds = radiusCircle.getBounds();
        const combinedBounds = circleBounds.extend(L.latLngBounds(bounds));
        map.fitBounds(combinedBounds, { padding: [40, 40], maxZoom: 16 });
      } catch (e) {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
      }
    } else if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    } else if (radiusCircle) {
      map.fitBounds(radiusCircle.getBounds(), { padding: [40, 40], maxZoom: 16 });
    }
  }
}

window.focusSpot = function(index) {
  const spot = state.parkingSpots[index];
  if (spot && map) {
    map.flyTo([spot.latitude, spot.longitude], 17);
    highlightSpotCard(index);
    // Open corresponding Leaflet popup
    parkingMarkersLayer.eachLayer((layer) => {
      if (layer.getLatLng && 
          Math.abs(layer.getLatLng().lat - spot.latitude) < 0.0001 &&
          Math.abs(layer.getLatLng().lng - spot.longitude) < 0.0001) {
        layer.openPopup();
      }
    });
  }
};

function clearRouteNavigation() {
  if (state.currentRoutePolyline && map) {
    map.removeLayer(state.currentRoutePolyline);
    state.currentRoutePolyline = null;
  }
  if (state.routeCasingLayer && map) {
    map.removeLayer(state.routeCasingLayer);
    state.routeCasingLayer = null;
  }
  if (state.routeLineLayer && map) {
    map.removeLayer(state.routeLineLayer);
    state.routeLineLayer = null;
  }
  if (state.originMarker && map) {
    map.removeLayer(state.originMarker);
    state.originMarker = null;
  }
  if (state.destinationMarker && map) {
    map.removeLayer(state.destinationMarker);
    state.destinationMarker = null;
  }
  state.activeRoute = null;
}

function clearRouteLine() {
  clearRouteNavigation();
}

function getManeuverIcon(maneuver, modifier) {
  const m = (maneuver || "").toLowerCase();
  const mod = (modifier || "").toLowerCase();
  if (m === "arrive") return "🏁";
  if (m === "depart") return "🚗";
  if (mod.includes("left")) return "↰";
  if (mod.includes("right")) return "↱";
  if (mod.includes("u-turn") || mod.includes("uturn")) return "↩️";
  return "⬆️";
}

function updateOriginOptionCardStyles(selectedValue) {
  document.querySelectorAll(".origin-option-card").forEach((card) => {
    const radio = card.querySelector('input[type="radio"]');
    if (radio && radio.value === selectedValue) {
      card.classList.add("active");
    } else {
      card.classList.remove("active");
    }
  });
}

async function loadOfflineRegions() {
  try {
    const res = await fetch("/api/offline-regions");
    if (!res.ok) return;
    const data = await res.json();
    state.offlineRegions = data.regions || [];

    // Populate Settings Modal Select
    if (selectLocationPreset) {
      selectLocationPreset.innerHTML = "";
      if (state.offlineRegions.length === 0) {
        selectLocationPreset.innerHTML = '<option value="13.0827,80.2707">Chennai Central (Default)</option>';
      } else {
        state.offlineRegions.forEach((reg) => {
          const opt = document.createElement("option");
          opt.value = `${reg.latitude},${reg.longitude}`;
          opt.textContent = `${reg.city} (${reg.spot_count} spots in offline DB)`;
          selectLocationPreset.appendChild(opt);
        });
      }
    }

    // Populate ModalPickOrigin Select
    if (selectOriginRegion) {
      selectOriginRegion.innerHTML = "";
      if (state.offlineRegions.length === 0) {
        selectOriginRegion.innerHTML = '<option value="13.0827,80.2707">Chennai Central (13.0827, 80.2707)</option>';
      } else {
        state.offlineRegions.forEach((reg) => {
          const opt = document.createElement("option");
          opt.value = `${reg.latitude},${reg.longitude}`;
          opt.textContent = `${reg.city} (${reg.spot_count} spots in offline DB)`;
          selectOriginRegion.appendChild(opt);
        });
      }
    }
  } catch (err) {
    console.warn("Failed to load offline regions:", err);
  }
}

window.routeToSpot = function(index) {
  const spot = state.parkingSpots[index];
  if (!spot || !map) return;

  state.pendingRouteDestination = spot;

  // Open "From where should I pick you up?" Modal
  if (navDestName) navDestName.textContent = spot.name || "Parking Destination";
  if (navDestAddress) {
    const locParts = [spot.street, spot.city].filter(Boolean);
    const feePart = spot.fee && spot.fee !== "unknown" ? spot.fee : "Fee unknown";
    navDestAddress.textContent = `${locParts.join(", ") || "OpenStreetMap Location"} • ${feePart}`;
  }
  if (navDestDistance) navDestDistance.textContent = spot.distance_text || "Nearby";
  if (navCurrentOriginDesc) {
    navCurrentOriginDesc.textContent = `${state.landmarkName || 'Current Location'} (${state.latitude.toFixed(4)}° N, ${state.longitude.toFixed(4)}° E)`;
  }

  // Load latest offline regions into select dropdowns
  loadOfflineRegions();

  // Reset origin radio choice to current
  const radioCurrent = document.querySelector('input[name="originChoice"][value="current"]');
  if (radioCurrent) {
    radioCurrent.checked = true;
    updateOriginOptionCardStyles("current");
  }

  if (modalPickOrigin) {
    modalPickOrigin.style.display = "flex";
  }
};

async function executeRoadNavigation(startLat, startLon, endLat, endLon, startName, endName, speakAudio = true) {
  showToast(`Calculating road directions to ${endName}...`, "info");

  try {
    const res = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_lat: startLat,
        start_lon: startLon,
        end_lat: endLat,
        end_lon: endLon,
        start_name: startName,
        end_name: endName,
        synthesize_voice: speakAudio
      })
    });

    if (!res.ok) {
      throw new Error(`Routing failed with status HTTP ${res.status}`);
    }

    const data = await res.json();
    state.activeRoute = data;
    state.navAudioBase64 = data.audio_base64;

    clearRouteNavigation();

    // 1. Draw Google Maps style road line
    if (data.geometry && map) {
      const geoData = {
        type: "Feature",
        geometry: data.geometry,
        properties: {}
      };

      // Outer road casing/glow
      state.routeCasingLayer = L.geoJSON(geoData, {
        style: {
          color: "#1e3a8a",
          weight: 7,
          opacity: 0.9,
          lineCap: "round",
          lineJoin: "round"
        }
      }).addTo(map);

      // Inner road stroke
      state.routeLineLayer = L.geoJSON(geoData, {
        style: {
          color: "#38bdf8",
          weight: 4,
          opacity: 1.0,
          lineCap: "round",
          lineJoin: "round"
        }
      }).addTo(map);

      // Origin Pin Marker (Flag)
      const originIcon = L.divIcon({
        className: "custom-nav-pin-origin",
        html: '<div style="background: #2563eb; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.5);">🚩</div>',
        iconSize: [28, 28],
        iconAnchor: [14, 28]
      });
      state.originMarker = L.marker([startLat, startLon], { icon: originIcon }).addTo(map);
      state.originMarker.bindPopup(`<b>Start / Pickup Point</b><br>${startName}`);

      // Destination Pin Marker (Parking)
      const destIcon = L.divIcon({
        className: "custom-nav-pin-dest",
        html: '<div style="background: #10b981; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.5);">🅿️</div>',
        iconSize: [28, 28],
        iconAnchor: [14, 28]
      });
      state.destinationMarker = L.marker([endLat, endLon], { icon: destIcon }).addTo(map);
      state.destinationMarker.bindPopup(`<b>Destination Parking</b><br>${endName}`);

      // Fit map bounds to whole route
      map.fitBounds(state.routeLineLayer.getBounds(), { padding: [60, 60] });
    }

    // 2. Switch to Map tab on mobile
    if (tabBtnMap && panelRight && window.innerWidth <= 900) {
      tabBtnMap.click();
    }

    // 3. Update Turn-by-Turn HUD Banner
    if (navHudBanner) {
      const firstStep = data.steps && data.steps.length > 0 ? data.steps[0] : null;
      if (firstStep) {
        if (navHudIcon) navHudIcon.textContent = getManeuverIcon(firstStep.maneuver, firstStep.modifier);
        if (navHudStep) navHudStep.textContent = `${firstStep.instruction} (${firstStep.distance_text})`;
      } else {
        if (navHudIcon) navHudIcon.textContent = "🚗";
        if (navHudStep) navHudStep.textContent = `Head to ${endName}`;
      }

      if (navHudDistance) navHudDistance.textContent = data.distance_text || "0 km";
      if (navHudDuration) navHudDuration.textContent = data.duration_text || "0 mins";
      if (navSourceTag) {
        navSourceTag.textContent = data.source === "osrm" ? "OSM Road Route" : "100% Offline Route";
      }

      // Populate Steps Drawer
      if (navStepsList && data.steps) {
        navStepsList.innerHTML = "";
        data.steps.forEach((s) => {
          const item = document.createElement("div");
          item.className = "nav-step-item";
          item.innerHTML = `
            <span class="nav-step-icon">${getManeuverIcon(s.maneuver, s.modifier)}</span>
            <div class="nav-step-instruction">
              <div>${s.instruction}</div>
              <div style="font-size: 11px; color: #64748b;">${s.road_name || ''}</div>
            </div>
            <span class="nav-step-dist">${s.distance_text || ''}</span>
          `;
          navStepsList.appendChild(item);
        });
      }

      if (navTotalStepsBadge) {
        navTotalStepsBadge.textContent = `${(data.steps || []).length} Steps`;
      }

      navHudBanner.style.display = "block";
    }

    // 4. Play Spoken TTS Guidance if available
    if (speakAudio && data.audio_base64 && state.ttsEngine === "piper") {
      playSynthesizedAudio(data.audio_base64);
    } else if (speakAudio && state.ttsEngine === "webspeech" && data.spoken_narrative && "speechSynthesis" in window) {
      const utter = new SpeechSynthesisUtterance(data.spoken_narrative);
      window.speechSynthesis.speak(utter);
    }

    showToast(`Road directions to ${endName}: ${data.distance_text} (${data.duration_text})`, "success");

  } catch (err) {
    console.error("Navigation error:", err);
    showToast(`Could not calculate road route: ${err.message}`, "error");
  }
}

function highlightSpotCard(index) {
  const cards = document.querySelectorAll(".parking-card-item");
  cards.forEach((c, idx) => {
    if (idx === index) {
      c.classList.add("selected");
      c.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      c.classList.remove("selected");
    }
  });
}

// ==========================================
// 5. Unified Input & Query Dispatch
// ==========================================
// Handle Text Input Submission
function handleTextSubmit() {
  const text = queryInput.value.trim();
  if (!text || state.isProcessing) return;

  queryInput.value = "";
  autoResizeInput();
  btnClearInput.style.display = "none";
  sendTextPrompt(text);
}

// Send Text Query to Backend
async function sendTextPrompt(text) {
  if (!text) return;
  state.isProcessing = true;
  setProcessingState(true);

  // Hide Welcome Card if present
  if (welcomeCard) welcomeCard.style.display = "none";

  // 1. Add User Message to Dialogue
  appendUserMessage(text);

  // 2. Add Thinking Placeholder
  const thinkingBubbleId = appendThinkingBubble();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        latitude: state.latitude,
        longitude: state.longitude,
        radius_meters: state.radiusMeters,
        synthesize_tts: state.ttsEngine === "piper"
      })
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();
    removeBubble(thinkingBubbleId);
    handleAssistantResponse(data);
  } catch (err) {
    console.error("Chat error:", err);
    removeBubble(thinkingBubbleId);
    appendErrorMessage(`Could not reach offline assistant (${err.message}). If using browser cache, please hard refresh (Ctrl+Shift+R or Cmd+Shift+R).`);
    showToast("Error processing request: " + err.message, "error");
  } finally {
    state.isProcessing = false;
    setProcessingState(false);
  }
}

// Handle Audio Recording Completion
async function handleAudioRecorded(audioBlob) {
  state.isProcessing = true;
  setProcessingState(true);

  if (welcomeCard) welcomeCard.style.display = "none";

  // Temporary thinking bubble
  const thinkingBubbleId = appendThinkingBubble("Transcribing speech offline & querying OSM...");

  try {
    const formData = new FormData();
    formData.append("audio", audioBlob, "speech.webm");
    formData.append("latitude", state.latitude);
    formData.append("longitude", state.longitude);
    formData.append("radius_meters", state.radiusMeters);

    const response = await fetch("/api/voice-query", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Voice query returned HTTP ${response.status}`);
    }

    const data = await response.json();
    removeBubble(thinkingBubbleId);

    // Add User Message with transcribed voice text
    const transcription = data.transcription || data.user_query || "Voice search query";
    appendUserMessage(transcription, true);

    handleAssistantResponse(data);
  } catch (err) {
    console.error("Voice query failed:", err);
    removeBubble(thinkingBubbleId);
    appendErrorMessage("Speech recognition failed. Please try speaking closer to the microphone.");
    showToast("Voice error: " + err.message, "error");
  } finally {
    state.isProcessing = false;
    setProcessingState(false);
  }
}

// Process & Render Backend Response
function handleAssistantResponse(data) {
  // 1. Latency & Timings
  if (data.timings) {
    const parts = [];
    if (data.timings.stt) parts.push(`STT: ${data.timings.stt}s`);
    if (data.timings.llm_total) parts.push(`LLM: ${data.timings.llm_total}s`);
    if (data.timings.tts) parts.push(`TTS: ${data.timings.tts}s`);
    timingsBadge.textContent = parts.join(" | ") || `Total: ${data.timings.total || 0}s`;
    sessionStatusBadge.textContent = "Answered";
  }

  // 2. MCP Trace
  state.mcpTrace = data.tool_executions || [];
  mcpCountBadge.textContent = `${state.mcpTrace.length} Calls`;
  mcpJsonTrace.textContent = JSON.stringify(state.mcpTrace, null, 2);

  // 3. Parking Spots & Radius Sync
  state.parkingSpots = data.parking_spots || [];

  // Sync radius circle, slider, and toolbar chip if effective radius returned
  const returnedRadius = data.effective_radius || data.radius_meters;
  if (returnedRadius && Number(returnedRadius) > 0) {
    state.radiusMeters = Number(returnedRadius);
    if (radiusCircle) {
      radiusCircle.setRadius(state.radiusMeters);
    }
    if (inputRadius) inputRadius.value = state.radiusMeters;
    if (radiusVal) radiusVal.textContent = state.radiusMeters;

    // Update active radius chip in top toolbar
    document.querySelectorAll(".radius-chip").forEach((chip) => {
      const chipRadius = Number(chip.getAttribute("data-radius"));
      chip.classList.toggle("active", chipRadius === state.radiusMeters);
    });
  }

  // Sync target center if geocoded location returned (e.g. "nearby Redhills")
  if (data.target_location && data.target_location.latitude && data.target_location.longitude) {
    const tLat = Number(data.target_location.latitude);
    const tLon = Number(data.target_location.longitude);
    if (radiusCircle) {
      radiusCircle.setLatLng([tLat, tLon]);
    }

    // Move map to the target location requested by user
    if (map) {
      map.panTo([tLat, tLon]);
    }

    if (data.target_location.name && data.target_location.name !== "your location") {
      state.landmarkName = data.target_location.name;
      if (locLandmarkName) locLandmarkName.textContent = state.landmarkName;
      if (locCoordinatesText) locCoordinatesText.textContent = `${tLat.toFixed(4)}° N, ${tLon.toFixed(4)}° E`;
      if (locationLabelPill) locationLabelPill.textContent = `📍 ${state.landmarkName} • ${tLat.toFixed(4)}° N, ${tLon.toFixed(4)}° E`;
    }
  }

  const radiusKmText = state.radiusMeters >= 1000
    ? `${(state.radiusMeters / 1000).toFixed(state.radiusMeters % 1000 === 0 ? 0 : 1)}km`
    : `${state.radiusMeters}m`;
  resultsCountSubtitle.textContent = `${state.parkingSpots.length} spots found within ${radiusKmText}`;
  if (mobileSpotsCount) mobileSpotsCount.textContent = state.parkingSpots.length;

  renderParkingMarkers(state.parkingSpots);
  renderParkingList(state.parkingSpots);

  // 4. Append Assistant Response to Chat
  appendAssistantMessage(data.answer, data.audio_base64, state.mcpTrace);

  // 5. Voice Playback
  if (state.autoPlaySpeech && data.audio_base64 && state.ttsEngine === "piper") {
    playSynthesizedAudio(data.audio_base64);
  } else if (state.autoPlaySpeech && state.ttsEngine === "webspeech" && "speechSynthesis" in window) {
    const utter = new SpeechSynthesisUtterance(data.answer);
    window.speechSynthesis.speak(utter);
  }

  showToast(`Found ${state.parkingSpots.length} parking spots nearby!`, "success");
}

// ==========================================
// 6. Dialogue Bubble Management
// ==========================================
function appendUserMessage(text, isVoice = false) {
  const timeStr = getCurrentTime();
  const div = document.createElement("div");
  div.className = "message-bubble user-bubble";
  div.innerHTML = `
    <div class="bubble-header">
      <div class="bubble-sender-row">
        <span class="avatar-user">YOU</span>
        <span class="bubble-sender">You ${isVoice ? '(Voice 🎙️)' : '(Text ⌨️)'}</span>
      </div>
      <span class="bubble-time">${timeStr}</span>
    </div>
    <div class="bubble-content">${escapeHtml(text)}</div>
  `;
  dialogueContainer.appendChild(div);
  scrollToBottom();
}

function appendThinkingBubble(label = "Searching offline OSM database...") {
  const id = "bubble-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "message-bubble assistant-bubble";
  div.innerHTML = `
    <div class="bubble-header">
      <div class="bubble-sender-row">
        <span class="avatar-bot">PV</span>
        <span class="bubble-sender">ParkVoice Assistant</span>
        <span class="bubble-tag">Reasoning...</span>
      </div>
    </div>
    <div class="bubble-content" style="color: #94a3b8; display: flex; align-items: center; gap: 8px;">
      <span style="display: inline-block; animation: spin 1s linear infinite;">⏳</span>
      <span>${escapeHtml(label)}</span>
    </div>
  `;
  dialogueContainer.appendChild(div);
  scrollToBottom();
  return id;
}

function appendAssistantMessage(answerText, audioBase64, traces) {
  const timeStr = getCurrentTime();
  const bubbleId = "ast-" + Date.now();
  const div = document.createElement("div");
  div.className = "message-bubble assistant-bubble";
  div.id = bubbleId;

  let audioWidgetHtml = "";
  if (audioBase64) {
    audioWidgetHtml = `
      <div class="audio-control-bar" id="audioBar-${bubbleId}">
        <button class="btn-audio-play" onclick="window.playAudioTrack('${audioBase64}', '${bubbleId}')" title="Play Voice Answer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        </button>
        <div class="audio-progress-bar" onclick="window.seekAudio(event, '${bubbleId}')">
          <div class="audio-progress-fill" id="fill-${bubbleId}"></div>
        </div>
        <span class="audio-duration" id="dur-${bubbleId}">0:00</span>
        <button class="btn-audio-speed" onclick="window.toggleTrackSpeed('${bubbleId}')" id="speed-${bubbleId}">1.0x</button>
        <button class="btn-audio-icon" onclick="window.replayTrack('${audioBase64}', '${bubbleId}')" title="Replay">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
        </button>
      </div>
    `;
  }

  let traceCount = (traces && traces.length) || 0;
  let traceJson = JSON.stringify(traces || [], null, 2);

  div.innerHTML = `
    <div class="bubble-header">
      <div class="bubble-sender-row">
        <span class="avatar-bot">PV</span>
        <span class="bubble-sender">ParkVoice Assistant</span>
        <span class="bubble-tag">Qwen 3 + Piper</span>
      </div>
      <span class="bubble-time">${timeStr}</span>
    </div>
    <div class="bubble-content">${escapeHtml(answerText)}</div>
    ${audioWidgetHtml}
    <div class="mcp-inspector">
      <button class="mcp-inspector-toggle" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'; this.parentElement.classList.toggle('open');">
        <span class="mcp-toggle-icon">⚡</span>
        <span class="mcp-toggle-label">OpenStreetMap MCP Trace</span>
        <span class="mcp-count-badge">${traceCount} Calls</span>
        <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div class="mcp-inspector-content" style="display: none;">
        <pre style="font-family: monospace; font-size: 11px; color: #93c5fd; overflow-x: auto; max-height: 140px;">${escapeHtml(traceJson)}</pre>
      </div>
    </div>
  `;

  dialogueContainer.appendChild(div);
  scrollToBottom();
}

function appendErrorMessage(errorText) {
  const div = document.createElement("div");
  div.className = "message-bubble assistant-bubble";
  div.style.borderLeftColor = "#ef4444";
  div.innerHTML = `
    <div class="bubble-header">
      <div class="bubble-sender-row">
        <span class="avatar-bot" style="background: #ef4444;">!</span>
        <span class="bubble-sender">System Notice</span>
      </div>
      <span class="bubble-time">${getCurrentTime()}</span>
    </div>
    <div class="bubble-content" style="color: #fca5a5;">${escapeHtml(errorText)}</div>
  `;
  dialogueContainer.appendChild(div);
  scrollToBottom();
}

function removeBubble(bubbleId) {
  const el = document.getElementById(bubbleId);
  if (el) el.remove();
}

function scrollToBottom() {
  dialogueContainer.scrollTop = dialogueContainer.scrollHeight;
}

// ==========================================
// 7. Microphone Recording & Visualizer
// ==========================================
async function startRecording() {
  if (state.isProcessing) return;

  // Browser Web Speech API fallback
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (state.sttEngine === "webspeech" && SpeechRecognition) {
    startBrowserSpeechRecognition();
    return;
  }

  try {
    state.audioChunks = [];
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    // Audio Visualizer Setup
    state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = state.audioContext.createMediaStreamSource(stream);
    state.analyser = state.audioContext.createAnalyser();
    state.analyser.fftSize = 64;
    source.connect(state.analyser);
    startVisualizer();

    // MediaRecorder format selection
    let mimeType = "audio/webm;codecs=opus";
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    }
    if (!mimeType && MediaRecorder.isTypeSupported("audio/ogg")) {
      mimeType = "audio/ogg";
    }

    state.mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    state.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) state.audioChunks.push(e.data);
    };

    state.mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      stopVisualizer();
      clearInterval(state.recordingInterval);
      hideRecordingOverlay();

      const audioBlob = new Blob(state.audioChunks, { type: state.mediaRecorder.mimeType || "audio/webm" });
      if (audioBlob.size < 500) {
        showToast("Audio recording too short or empty.", "warning");
        return;
      }
      await handleAudioRecorded(audioBlob);
    };

    state.mediaRecorder.start();
    state.isRecording = true;

    // UI Updates
    btnInputMic.classList.add("recording");
    showRecordingOverlay();
    startRecordingTimer();
  } catch (err) {
    console.error("Microphone access error:", err);
    showToast("Microphone access denied: " + err.message, "error");
  }
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
    state.mediaRecorder.stop();
  }
  state.isRecording = false;
  btnInputMic.classList.remove("recording");
}

function cancelRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
    state.mediaRecorder.ondataavailable = null;
    state.mediaRecorder.onstop = null;
    state.mediaRecorder.stop();
  }
  state.isRecording = false;
  state.audioChunks = [];
  btnInputMic.classList.remove("recording");
  stopVisualizer();
  clearInterval(state.recordingInterval);
  hideRecordingOverlay();
  showToast("Voice recording canceled.", "info");
}

function showRecordingOverlay() {
  voiceRecordingOverlay.style.display = "flex";
  voiceStateText.textContent = "Listening... (Whisper STT)";
}

function hideRecordingOverlay() {
  voiceRecordingOverlay.style.display = "none";
}

function startRecordingTimer() {
  state.recordingStartTime = Date.now();
  recordingTimer.textContent = "00:00";
  clearInterval(state.recordingInterval);
  state.recordingInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.recordingStartTime) / 1000);
    const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const s = String(elapsed % 60).padStart(2, "0");
    recordingTimer.textContent = `${m}:${s}`;
  }, 1000);
}

function startVisualizer() {
  const bufferLength = state.analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    state.visualizerAnimId = requestAnimationFrame(draw);
    state.analyser.getByteFrequencyData(dataArray);

    visualizerCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    const barWidth = (visualizerCanvas.width / bufferLength) * 1.8;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * visualizerCanvas.height * 0.95;
      const gradient = visualizerCtx.createLinearGradient(0, visualizerCanvas.height, 0, 0);
      gradient.addColorStop(0, "#ef4444");
      gradient.addColorStop(1, "#3b82f6");

      visualizerCtx.fillStyle = gradient;
      visualizerCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth - 2, barHeight);
      x += barWidth;
    }
  }
  draw();
}

function stopVisualizer() {
  if (state.visualizerAnimId) {
    cancelAnimationFrame(state.visualizerAnimId);
    state.visualizerAnimId = null;
  }
  visualizerCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
}

function startBrowserSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    state.isRecording = true;
    btnInputMic.classList.add("recording");
    showRecordingOverlay();
    voiceStateText.textContent = "Listening via Browser Speech...";
    startRecordingTimer();
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    hideRecordingOverlay();
    clearInterval(state.recordingInterval);
    sendTextPrompt(transcript);
  };

  recognition.onerror = (event) => {
    hideRecordingOverlay();
    clearInterval(state.recordingInterval);
    showToast(`Speech error: ${event.error}`, "error");
  };

  recognition.onend = () => {
    state.isRecording = false;
    btnInputMic.classList.remove("recording");
    hideRecordingOverlay();
    clearInterval(state.recordingInterval);
  };

  recognition.start();
}

// ==========================================
// 8. Audio Playback Management
// ==========================================
function playSynthesizedAudio(base64Uri) {
  state.audioPlayer.src = base64Uri;
  state.audioPlayer.playbackRate = state.playbackSpeed;
  state.audioPlayer.play().catch((err) => console.log("Audio play error:", err));

  state.audioPlayer.onended = () => {
    updatePlayIconState(false);
  };

  state.audioPlayer.ontimeupdate = () => {
    if (state.audioPlayer.duration) {
      const pct = (state.audioPlayer.currentTime / state.audioPlayer.duration) * 100;
      if (audioProgressFill) audioProgressFill.style.width = `${pct}%`;
      const cur = formatTime(state.audioPlayer.currentTime);
      const total = formatTime(state.audioPlayer.duration);
      if (audioDuration) audioDuration.textContent = `${cur} / ${total}`;
    }
  };

  updatePlayIconState(true);
}

window.playAudioTrack = function(base64Uri, bubbleId) {
  if (state.audioPlayer.src === base64Uri && !state.audioPlayer.paused) {
    state.audioPlayer.pause();
    return;
  }
  playSynthesizedAudio(base64Uri);
};

window.seekAudio = function(e, bubbleId) {
  if (!state.audioPlayer.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const pct = Math.max(0, Math.min(1, clickX / rect.width));
  state.audioPlayer.currentTime = pct * state.audioPlayer.duration;
};

window.toggleTrackSpeed = function(bubbleId) {
  const speeds = [1.0, 1.25, 1.5, 2.0];
  const nextIdx = (speeds.indexOf(state.playbackSpeed) + 1) % speeds.length;
  state.playbackSpeed = speeds[nextIdx];
  state.audioPlayer.playbackRate = state.playbackSpeed;
  if (btnAudioSpeed) btnAudioSpeed.textContent = `${state.playbackSpeed}x`;
  const btn = document.getElementById(`speed-${bubbleId}`);
  if (btn) btn.textContent = `${state.playbackSpeed}x`;
  showToast(`Playback speed: ${state.playbackSpeed}x`, "info");
};

window.replayTrack = function(base64Uri, bubbleId) {
  state.audioPlayer.currentTime = 0;
  state.audioPlayer.play();
};

function updatePlayIconState(isPlaying) {
  if (!playIcon) return;
  if (isPlaying) {
    playIcon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  } else {
    playIcon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
  }
}

// ==========================================
// 9. Parking Cards & List Rendering
// ==========================================
function renderParkingList(spots) {
  parkingList.innerHTML = "";
  if (!spots || spots.length === 0) {
    parkingList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon-box">🅿️</div>
        <h4 class="empty-title">No Spots Matching Filter</h4>
        <p class="empty-desc">No parking spaces found matching "${state.activeFilter}" filter in the local offline database.</p>
      </div>
    `;
    return;
  }

  // Filter spots
  let filtered = [...spots];
  if (state.activeFilter === "free") {
    filtered = filtered.filter((s) => s.fee === "free" || s.fee === "no" || s.fee === "0");
  } else if (state.activeFilter === "covered") {
    filtered = filtered.filter((s) => s.parking_type === "multi-storey" || s.parking_type === "underground");
  } else if (state.activeFilter === "capacity") {
    filtered = filtered.filter((s) => s.capacity && s.capacity >= 15);
  }

  // Sort spots
  if (state.activeSort === "distance") {
    filtered.sort((a, b) => (a.distance_meters || 0) - (b.distance_meters || 0));
  } else if (state.activeSort === "capacity") {
    filtered.sort((a, b) => (b.capacity || 0) - (a.capacity || 0));
  } else if (state.activeSort === "free") {
    const isFree = (s) => (s.fee === "free" || s.fee === "no" || s.fee === "0") ? 1 : 0;
    filtered.sort((a, b) => isFree(b) - isFree(a));
  }

  if (filtered.length === 0) {
    parkingList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon-box">🔍</div>
        <h4 class="empty-title">No Matching Results</h4>
        <p class="empty-desc">Try selecting "All" or increasing your search radius.</p>
      </div>
    `;
    return;
  }

  filtered.forEach((spot, idx) => {
    const isFree = spot.fee === "free" || spot.fee === "no" || spot.fee === "0";
    const feeBadgeClass = isFree ? "badge-fee-free" : "badge-fee-paid";
    const feeLabel = isFree ? "Free Parking" : `Fee: ${spot.fee || "Paid"}`;

    const card = document.createElement("div");
    card.className = "parking-card-item";
    card.innerHTML = `
      <div class="parking-item-header">
        <div class="parking-item-title">${idx + 1}. ${escapeHtml(spot.name)}</div>
      </div>
      <div class="parking-badges">
        <span class="badge badge-distance">📍 ${spot.distance_text}</span>
        <span class="badge ${feeBadgeClass}">💵 ${feeLabel}</span>
        <span class="badge badge-type">🏢 ${spot.parking_type}</span>
        ${spot.capacity > 0 ? `<span class="badge badge-distance">🚗 ${spot.capacity} slots</span>` : ""}
      </div>
      <div class="parking-card-footer">
        <span>🕒 ${spot.opening_hours || "24/7"} • ♿ ${spot.wheelchair || "standard"}</span>
        <div style="display: flex; gap: 8px;">
          <span class="parking-action-link" onclick="event.stopPropagation(); window.routeToSpot(${idx})">🧭 Route</span>
          <span class="parking-action-link">View →</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      window.focusSpot(idx);
    });

    parkingList.appendChild(card);
  });
}

// ==========================================
// 10. Event Listeners & Interactive Handlers
// ==========================================
// Input auto-grow and clear button visibility
queryInput.addEventListener("input", () => {
  autoResizeInput();
  btnClearInput.style.display = queryInput.value.length > 0 ? "flex" : "none";
});

// Clear input button
btnClearInput.addEventListener("click", () => {
  queryInput.value = "";
  autoResizeInput();
  btnClearInput.style.display = "none";
  queryInput.focus();
});

// Form submit & Enter key
inputForm.addEventListener("submit", (e) => {
  e.preventDefault();
  handleTextSubmit();
});

queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleTextSubmit();
  }
});

// Global keyboard shortcut ('/' focuses query input)
window.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== queryInput && !settingsModal.matches(":focus-within")) {
    e.preventDefault();
    queryInput.focus();
  } else if (e.key === "Escape") {
    if (state.isRecording) {
      cancelRecording();
    } else if (settingsModal.style.display !== "none") {
      settingsModal.style.display = "none";
    }
  }
});

// Microphone dock button toggle
btnInputMic.addEventListener("click", () => {
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// Voice overlay finish & cancel
btnFinishRecording.addEventListener("click", () => {
  stopRecording();
});

btnCancelRecording.addEventListener("click", () => {
  cancelRecording();
});

// Quick prompt suggestions
document.querySelectorAll(".btn-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const promptText = chip.getAttribute("data-prompt");
    sendTextPrompt(promptText);
  });
});

// Radius selector chips
document.querySelectorAll(".radius-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".radius-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    state.radiusMeters = Number(chip.getAttribute("data-radius"));
    if (radiusCircle) radiusCircle.setRadius(state.radiusMeters);
    if (inputRadius) inputRadius.value = state.radiusMeters;
    if (radiusVal) radiusVal.textContent = state.radiusMeters;
    showToast(`Search radius updated to ${state.radiusMeters}m`, "info");
    sendTextPrompt("Find parking within " + state.radiusMeters + " meters");
  });
});

// Category filter pills
document.querySelectorAll(".filter-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    document.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    state.activeFilter = pill.getAttribute("data-filter");
    renderParkingList(state.parkingSpots);
  });
});

// Sort select
selectSortBy.addEventListener("change", (e) => {
  state.activeSort = e.target.value;
  renderParkingList(state.parkingSpots);
});

// Map controls
btnLocateMe.addEventListener("click", () => {
  if (navigator.geolocation) {
    showToast("Detecting GPS position...", "info");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        updateUserLocation(pos.coords.latitude, pos.coords.longitude, "My GPS Position");
        showToast("GPS position acquired!", "success");
        sendTextPrompt("Find parking near my location");
      },
      (err) => {
        showToast("Geolocation unavailable: " + err.message, "warning");
      }
    );
  }
});

btnFitMap.addEventListener("click", () => {
  if (state.parkingSpots.length > 0) {
    renderParkingMarkers(state.parkingSpots);
  } else if (map) {
    map.setView([state.latitude, state.longitude], 15);
  }
});

btnToggleRadius.addEventListener("click", () => {
  state.showRadiusCircle = !state.showRadiusCircle;
  btnToggleRadius.classList.toggle("active", state.showRadiusCircle);
  if (radiusCircle) {
    if (state.showRadiusCircle) {
      radiusCircle.addTo(map);
    } else {
      map.removeLayer(radiusCircle);
    }
  }
});

btnSearchArea.addEventListener("click", () => {
  if (!map) return;
  const center = map.getCenter();
  updateUserLocation(center.lat, center.lng, "Map Center");
  sendTextPrompt("Find parking in this map area");
});

// Mobile view tabs
tabBtnChat.addEventListener("click", () => {
  tabBtnChat.classList.add("active");
  tabBtnMap.classList.remove("active");
  panelLeft.classList.remove("hidden");
  panelRight.classList.remove("active");
});

tabBtnMap.addEventListener("click", () => {
  tabBtnMap.classList.add("active");
  tabBtnChat.classList.remove("active");
  panelLeft.classList.add("hidden");
  panelRight.classList.add("active");
  if (map) setTimeout(() => map.invalidateSize(), 150);
});

// Clear conversation chat
btnClearChat.addEventListener("click", () => {
  if (confirm("Clear conversation history and reset view?")) {
    dialogueContainer.innerHTML = "";
    if (welcomeCard) dialogueContainer.appendChild(welcomeCard);
    welcomeCard.style.display = "flex";
    state.parkingSpots = [];
    resultsCountSubtitle.textContent = "0 spots";
    if (parkingMarkersLayer) parkingMarkersLayer.clearLayers();
    clearRouteNavigation();
    renderParkingList([]);
    showToast("Conversation cleared.", "info");
  }
});

// Copy MCP JSON trace
if (btnCopyMcpTrace) {
  btnCopyMcpTrace.addEventListener("click", () => {
    navigator.clipboard.writeText(JSON.stringify(state.mcpTrace, null, 2))
      .then(() => showToast("MCP trace JSON copied to clipboard!", "success"));
  });
}

// Settings modal interactions
headerLocationPill.addEventListener("click", () => {
  settingsModal.style.display = "flex";
  switchSettingsTab("tab-location");
});

btnSettings.addEventListener("click", () => {
  settingsModal.style.display = "flex";
  fetchStatus();
});

btnCloseSettings.addEventListener("click", () => {
  settingsModal.style.display = "none";
});

btnApplySettings.addEventListener("click", () => {
  settingsModal.style.display = "none";
});

settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) settingsModal.style.display = "none";
});

// Settings tab switching
document.querySelectorAll(".modal-nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tabId = btn.getAttribute("data-tab");
    switchSettingsTab(tabId);
  });
});

function switchSettingsTab(tabId) {
  document.querySelectorAll(".modal-nav-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".modal-tab-pane").forEach((p) => p.style.display = "none");
  const targetBtn = document.querySelector(`[data-tab="${tabId}"]`);
  const targetPane = document.getElementById(tabId);
  if (targetBtn) targetBtn.classList.add("active");
  if (targetPane) targetPane.style.display = "flex";
}

selectLocationPreset.addEventListener("change", (e) => {
  const [lat, lon] = e.target.value.split(",").map(Number);
  const name = selectLocationPreset.options[selectLocationPreset.selectedIndex].text.split("(")[0].trim();
  updateUserLocation(lat, lon, name);
  showToast(`Location set to preset: ${name}`, "success");
});

inputLat.addEventListener("change", (e) => updateUserLocation(Number(e.target.value), state.longitude));
inputLon.addEventListener("change", (e) => updateUserLocation(state.latitude, Number(e.target.value)));

inputRadius.addEventListener("input", (e) => {
  state.radiusMeters = Number(e.target.value);
  radiusVal.textContent = state.radiusMeters;
  if (radiusCircle) radiusCircle.setRadius(state.radiusMeters);
});

selectSttEngine.addEventListener("change", (e) => {
  state.sttEngine = e.target.value;
  sttModeIndicator.textContent = state.sttEngine === "whisper" ? "Whisper Offline" : "WebSpeech API";
});

selectTtsEngine.addEventListener("change", (e) => {
  state.ttsEngine = e.target.value;
});

checkboxAutoPlay.addEventListener("change", (e) => {
  state.autoPlaySpeech = e.target.checked;
});

btnResetSettings.addEventListener("click", () => {
  updateUserLocation(13.0827, 80.2707, "Chennai Central");
  state.radiusMeters = 5000;
  inputRadius.value = 5000;
  radiusVal.textContent = 5000;
  if (radiusCircle) radiusCircle.setRadius(5000);
  document.querySelectorAll(".radius-chip").forEach((c) => {
    c.classList.toggle("active", Number(c.getAttribute("data-radius")) === 5000);
  });
  state.sttEngine = "whisper";
  selectSttEngine.value = "whisper";
  state.ttsEngine = "piper";
  selectTtsEngine.value = "piper";
  state.autoPlaySpeech = true;
  checkboxAutoPlay.checked = true;
  showToast("Settings reset to defaults (5km radius).", "info");
});

// ==========================================
// Dynamic Location Search & Mirror Downloader
// ==========================================
async function performRegionSearch() {
  const query = inputSearchRegion.value.trim();
  if (!query) {
    showToast("Please enter a location or city name to search.", "warning");
    return;
  }

  btnSearchRegion.disabled = true;
  btnSearchRegion.innerHTML = "<span>Searching...</span>";
  mirrorStatusAlert.style.display = "none";
  regionSearchResultBox.style.display = "none";

  try {
    const res = await fetch(`/api/search-region?query=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (data.found) {
      state.searchedLocation = data;
      regionResultTitle.textContent = data.display_name;
      regionResultCoords.textContent = `📍 ${data.latitude}° N, ${data.longitude}° E`;
      regionSearchResultBox.style.display = "flex";
      showToast(`Location found: ${data.short_name}`, "success");
    } else {
      state.searchedLocation = null;
      regionSearchResultBox.style.display = "none";
      mirrorStatusAlert.className = "region-alert-box warning";
      mirrorStatusAlert.style.display = "flex";
      mirrorStatusAlert.innerHTML = `⚠️ <span>${escapeHtml(data.message || "Location not found in OpenStreetMap.")}</span>`;
      showToast("Location not found in OpenStreetMap.", "warning");
    }
  } catch (err) {
    console.error("Region search error:", err);
    mirrorStatusAlert.className = "region-alert-box error";
    mirrorStatusAlert.style.display = "flex";
    mirrorStatusAlert.innerHTML = `✕ <span>Search error: ${escapeHtml(err.message)}</span>`;
    showToast("Search failed: " + err.message, "error");
  } finally {
    btnSearchRegion.disabled = false;
    btnSearchRegion.innerHTML = "<span>🔍 Search</span>";
  }
}

async function performDownloadSearchedRegion() {
  if (!state.searchedLocation) return;

  const loc = state.searchedLocation;
  btnDownloadFoundRegion.disabled = true;
  btnDownloadFoundRegion.innerHTML = "<span>Connecting to Mirrors...</span>";

  mirrorStatusAlert.className = "region-alert-box info";
  mirrorStatusAlert.style.display = "flex";
  mirrorStatusAlert.innerHTML = `⏳ <span>Querying OpenStreetMap Overpass mirrors for <b>${escapeHtml(loc.short_name)}</b>...</span>`;

  try {
    const url = `/api/download-region?city=${encodeURIComponent(loc.short_name)}&south=${loc.bbox.south}&west=${loc.bbox.west}&north=${loc.bbox.north}&east=${loc.bbox.east}`;
    const res = await fetch(url, { method: "POST" });
    const data = await res.json();

    if (data.success && data.downloaded_spots > 0) {
      mirrorStatusAlert.className = "region-alert-box success";
      mirrorStatusAlert.innerHTML = `✓ <span>Successfully downloaded <b>${data.downloaded_spots} parking spots</b> for ${escapeHtml(loc.short_name)} from mirror! Total in offline DB: ${data.total_spots_in_db}</span>`;
      badgeTotalSpots.textContent = `${data.total_spots_in_db} Spots`;
      if (badgeTotalSpotsModal) badgeTotalSpotsModal.textContent = `${data.total_spots_in_db} Spots`;
      loadOfflineRegions();
      showToast(`Downloaded ${data.downloaded_spots} spots for ${loc.short_name}!`, "success");
    } else if (data.success && data.downloaded_spots === 0) {
      mirrorStatusAlert.className = "region-alert-box warning";
      mirrorStatusAlert.innerHTML = `ℹ️ <span>Mirrors connected, but <b>0 parking spots</b> were found in this bounding box for ${escapeHtml(loc.short_name)}.</span>`;
      showToast(`0 parking spots found for ${loc.short_name}.`, "warning");
    } else {
      // Mirror failed / timeout
      mirrorStatusAlert.className = "region-alert-box error";
      mirrorStatusAlert.innerHTML = `⚠️ <span><b>No map was found in mirrors.</b> ${escapeHtml(data.message || "All Overpass mirrors timed out or were unreachable.")}</span>`;
      showToast("No map was found in mirrors.", "error");
    }
  } catch (err) {
    console.error("Mirror download error:", err);
    mirrorStatusAlert.className = "region-alert-box error";
    mirrorStatusAlert.innerHTML = `✕ <span><b>No map was found in mirrors:</b> ${escapeHtml(err.message)}</span>`;
    showToast("No map was found in mirrors: " + err.message, "error");
  } finally {
    btnDownloadFoundRegion.disabled = false;
    btnDownloadFoundRegion.innerHTML = "<span>📥 Download Offline Map</span>";
  }
}

if (btnSearchRegion) {
  btnSearchRegion.addEventListener("click", performRegionSearch);
}

if (inputSearchRegion) {
  inputSearchRegion.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      performRegionSearch();
    }
  });
}

if (btnDownloadFoundRegion) {
  btnDownloadFoundRegion.addEventListener("click", performDownloadSearchedRegion);
}

if (btnSetAsMapPosition) {
  btnSetAsMapPosition.addEventListener("click", () => {
    if (!state.searchedLocation) return;
    const loc = state.searchedLocation;
    updateUserLocation(loc.latitude, loc.longitude, loc.short_name);
    settingsModal.style.display = "none";
    showToast(`Map location centered to ${loc.short_name}!`, "success");
    sendTextPrompt(`Find parking near ${loc.short_name}`);
  });
}

// Preset Regions Downloader
btnDownloadRegion.addEventListener("click", async () => {
  const region = selectDownloadRegion.value;
  downloadStatusText.textContent = `Querying OpenStreetMap mirrors for ${region}...`;
  btnDownloadRegion.disabled = true;

  try {
    const res = await fetch(`/api/download-region?city=${encodeURIComponent(region)}`, { method: "POST" });
    const data = await res.json();
    if (data.success && data.downloaded_spots > 0) {
      downloadStatusText.textContent = `✓ Successfully downloaded ${data.downloaded_spots} spots from mirror! Total in DB: ${data.total_spots_in_db}`;
      badgeTotalSpots.textContent = `${data.total_spots_in_db} Spots`;
      if (badgeTotalSpotsModal) badgeTotalSpotsModal.textContent = `${data.total_spots_in_db} Spots`;
      loadOfflineRegions();
      showToast(`Downloaded ${data.downloaded_spots} spots for ${region}!`, "success");
    } else if (data.success && data.downloaded_spots === 0) {
      downloadStatusText.textContent = `ℹ️ Mirrors reached, but 0 parking spots found in ${region}.`;
    } else {
      downloadStatusText.textContent = `⚠️ No map was found in mirrors: ${data.message}`;
      showToast("No map was found in mirrors.", "error");
    }
  } catch (err) {
    downloadStatusText.textContent = `Download error: ${err.message}`;
    showToast("Download failed: " + err.message, "error");
  } finally {
    btnDownloadRegion.disabled = false;
  }
});

// ==========================================
// 11. Subsystem Health Monitoring
// ==========================================
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (res.ok) {
      const data = await res.json();
      const subs = data.subsystems;

      // LLM status
      if (subs.llm && subs.llm.status === "online") {
        statusPillLlm.classList.remove("offline");
        statusPillLlm.title = "Qwen 3 on llama.cpp (Online)";
      } else {
        statusPillLlm.classList.add("offline");
        statusPillLlm.title = "llama.cpp offline - using offline OSM direct reasoning";
      }

      // MCP status
      if (subs.mcp_server) {
        statusPillMcp.classList.remove("offline");
      }

      // STT status
      if (subs.speech_to_text) {
        statusPillStt.classList.remove("offline");
      }

      // TTS status
      if (subs.text_to_speech) {
        statusPillTts.classList.remove("offline");
      }

      // DB total spots
      if (subs.osm_database) {
        const count = subs.osm_database.total_parking_spots;
        badgeTotalSpots.textContent = `${count} Spots`;
        if (badgeTotalSpotsModal) badgeTotalSpotsModal.textContent = `${count} Spots`;
      }
    }
  } catch (err) {
    console.warn("Status fetch failed:", err);
  }
}

// ==========================================
// 12. Helper Utilities
// ==========================================
function setProcessingState(isProc) {
  if (isProc) {
    btnInputMic.classList.add("processing");
    btnSendQuery.disabled = true;
    sessionStatusBadge.textContent = "Processing...";
  } else {
    btnInputMic.classList.remove("processing");
    btnSendQuery.disabled = false;
    sessionStatusBadge.textContent = "Ready";
  }
}

function autoResizeInput() {
  queryInput.style.height = "auto";
  queryInput.style.height = Math.min(queryInput.scrollHeight, 80) + "px";
}

function formatTime(secs) {
  if (isNaN(secs)) return "0:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function getCurrentTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message, type = "info", duration = 3500) {
  if (!toastContainer) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: "✓",
    info: "ℹ",
    warning: "⚠",
    error: "✕"
  };

  toast.innerHTML = `
    <span style="font-weight: 700;">${iconMap[type] || "ℹ"}</span>
    <span>${escapeHtml(message)}</span>
  `;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ==========================================
// 12. Turn-by-Turn Road Navigation & Origin Modal Handlers
// ==========================================
// Close modalPickOrigin when clicking backdrop or close buttons
if (modalPickOrigin) {
  modalPickOrigin.addEventListener("click", (e) => {
    if (e.target === modalPickOrigin) modalPickOrigin.style.display = "none";
  });
}
if (btnClosePickOrigin) {
  btnClosePickOrigin.addEventListener("click", () => {
    if (modalPickOrigin) modalPickOrigin.style.display = "none";
  });
}
if (btnCancelPickOrigin) {
  btnCancelPickOrigin.addEventListener("click", () => {
    if (modalPickOrigin) modalPickOrigin.style.display = "none";
  });
}

// Origin radio choice changes
document.querySelectorAll('input[name="originChoice"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    updateOriginOptionCardStyles(e.target.value);
  });
});

// Clicking origin card activates its radio button
document.querySelectorAll(".origin-option-card").forEach((card) => {
  card.addEventListener("click", (e) => {
    if (e.target.tagName === "SELECT" || (e.target.tagName === "INPUT" && e.target.type === "text")) return;
    const radio = card.querySelector('input[type="radio"]');
    if (radio && !radio.checked) {
      radio.checked = true;
      updateOriginOptionCardStyles(radio.value);
    }
  });
});

// Confirm Start Navigation Button
if (btnConfirmStartNav) {
  btnConfirmStartNav.addEventListener("click", async () => {
    if (!state.pendingRouteDestination) return;

    const dest = state.pendingRouteDestination;
    const selectedChoice = document.querySelector('input[name="originChoice"]:checked')?.value || "current";
    const speakAudio = checkboxNavVoice ? checkboxNavVoice.checked : true;

    if (modalPickOrigin) modalPickOrigin.style.display = "none";

    if (selectedChoice === "current") {
      executeRoadNavigation(
        state.latitude,
        state.longitude,
        dest.latitude,
        dest.longitude,
        state.landmarkName || "Current Location",
        dest.name,
        speakAudio
      );
    } else if (selectedChoice === "offline_region") {
      const val = selectOriginRegion ? selectOriginRegion.value : "";
      if (val && val.includes(",")) {
        const [latStr, lonStr] = val.split(",");
        const selName = selectOriginRegion.selectedOptions[0]?.text.split("(")[0].trim() || "Offline Region";
        executeRoadNavigation(
          parseFloat(latStr),
          parseFloat(lonStr),
          dest.latitude,
          dest.longitude,
          selName,
          dest.name,
          speakAudio
        );
      } else {
        showToast("Please select a downloaded region", "warning");
      }
    } else if (selectedChoice === "pick_map") {
      state.isPickingOriginOnMap = true;
      if (tabBtnMap && panelRight && window.innerWidth <= 900) {
        tabBtnMap.click();
      }
      showToast("Tap anywhere on the map to set your pickup location", "info");
    } else if (selectedChoice === "custom_landmark") {
      const query = inputCustomOrigin ? inputCustomOrigin.value.trim() : "";
      if (!query) {
        showToast("Please enter a landmark or area name", "warning");
        return;
      }
      showToast(`Searching offline landmark '${query}'...`, "info");
      try {
        const geoRes = await fetch(`/api/search-region?query=${encodeURIComponent(query)}`);
        const geoData = await geoRes.json();
        if (geoData.found && geoData.latitude && geoData.longitude) {
          executeRoadNavigation(
            geoData.latitude,
            geoData.longitude,
            dest.latitude,
            dest.longitude,
            geoData.display_name || query,
            dest.name,
            speakAudio
          );
        } else {
          showToast(`Landmark '${query}' not found. Routing from current position instead.`, "warning");
          executeRoadNavigation(
            state.latitude,
            state.longitude,
            dest.latitude,
            dest.longitude,
            state.landmarkName,
            dest.name,
            speakAudio
          );
        }
      } catch (err) {
        showToast(`Error looking up landmark: ${err.message}`, "error");
      }
    }
  });
}

// Exit Navigation Button
if (btnCloseNav) {
  btnCloseNav.addEventListener("click", () => {
    clearRouteNavigation();
    if (navHudBanner) navHudBanner.style.display = "none";
    if (navStepsDrawer) navStepsDrawer.style.display = "none";
    showToast("Exited road navigation", "info");
  });
}

// Replay Spoken Driving Directions Button
if (btnNavVoice) {
  btnNavVoice.addEventListener("click", () => {
    if (state.navAudioBase64) {
      playSynthesizedAudio(state.navAudioBase64);
      showToast("Replaying spoken driving directions", "info");
    } else if (state.activeRoute && state.activeRoute.spoken_narrative && "speechSynthesis" in window) {
      const utter = new SpeechSynthesisUtterance(state.activeRoute.spoken_narrative);
      window.speechSynthesis.speak(utter);
    } else {
      showToast("No spoken audio available for this route", "info");
    }
  });
}

// Toggle Turn-by-Turn Steps Drawer Button
if (btnToggleNavSteps) {
  btnToggleNavSteps.addEventListener("click", () => {
    if (!navStepsDrawer) return;
    const isVisible = navStepsDrawer.style.display === "block";
    navStepsDrawer.style.display = isVisible ? "none" : "block";
  });
}

// Refresh Offline Regions Button in Settings Modal
if (btnRefreshOfflineRegions) {
  btnRefreshOfflineRegions.addEventListener("click", () => {
    loadOfflineRegions();
    showToast("Refreshed offline regions from database", "success");
  });
}

// GPS Centering in Settings Modal
if (btnUseGpsModal) {
  btnUseGpsModal.addEventListener("click", () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          updateUserLocation(pos.coords.latitude, pos.coords.longitude, "Device GPS");
          showToast("Centered on your device GPS position", "success");
        },
        (err) => {
          showToast("GPS access unavailable: " + err.message, "warning");
        },
        { timeout: 8000 }
      );
    }
  });
}

// ==========================================
// 13. Initialization Lifecycle
// ==========================================
window.addEventListener("DOMContentLoaded", () => {
  initMap();
  fetchStatus();
  loadOfflineRegions();
  setInterval(fetchStatus, 15000);
});
