import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode } from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n } from "../i18n";
import { PLACES, type Place } from "../places";
import { PlaceNote } from "../components/Bits";
import { Icon } from "../components/Icon";
import { bboxOfRing, closeRing } from "../geo";

export interface PlotMapHandle {
  undo: () => void;
  finish: () => void;
  clear: () => void;
  flyTo: (lat: number, lon: number, zoom: number) => void;
}

export type DrawPhase = "loading" | "drawing" | "editing";

interface Props {
  center: { lat: number; lon: number } | null;
  initialRing: number[][] | null;
  onRing: (ring: number[][] | null, corners: number, phase: DrawPhase) => void;
}

const MAIZE = "#FFE08A" as const;
const INK = "#1E1913" as const;

function polygonOf(draw: TerraDraw) {
  return draw.getSnapshot().find((f) => f.geometry.type === "Polygon" && !f.properties.closingPoint);
}

const PlotMap = forwardRef<PlotMapHandle, Props>(function PlotMap({ center, initialRing, onRing }, ref) {
  const { t, lang } = useI18n();
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const polyMode = useRef<TerraDrawPolygonMode | null>(null);
  const onRingRef = useRef(onRing);
  onRingRef.current = onRing;
  const phaseRef = useRef<DrawPhase>("loading");
  const [tileError, setTileError] = useState(false);
  const [broken] = useState(() => !canRunMap());
  const [initError, setInitError] = useState(false);
  const [place, setPlace] = useState<Place | null>(null);

  const emit = () => {
    const draw = drawRef.current;
    if (!draw) return;
    const f = polygonOf(draw);
    if (!f) {
      onRingRef.current(null, 0, phaseRef.current);
      return;
    }
    const ring = (f.geometry.coordinates as number[][][])[0];
    if (phaseRef.current === "drawing") {
      // While drawing, the ring holds [...corners, floating point, first corner].
      const unique = new Set(ring.slice(0, -1).map((c) => `${c[0]},${c[1]}`));
      onRingRef.current(ring, unique.size, "drawing");
    } else {
      onRingRef.current(ring, ring.length - 1, "editing");
    }
  };

  const toEditing = (id: string | number) => {
    const draw = drawRef.current;
    if (!draw) return;
    phaseRef.current = "editing";
    draw.setMode("select");
    draw.selectFeature(id);
    emit();
  };

  useImperativeHandle(ref, () => ({
    undo() {
      const m = polyMode.current;
      if (m && phaseRef.current === "drawing" && m.undoSize() > 0) {
        m.undo();
        emit();
      }
    },
    finish() {
      // Touch screens have no Enter key, and this is the mode's own finish path.
      polyMode.current?.onKeyUp({ key: "Enter", heldKeys: [], preventDefault: () => {} } as never);
    },
    clear() {
      const draw = drawRef.current;
      if (!draw) return;
      draw.clear();
      phaseRef.current = "drawing";
      draw.setMode("polygon");
      emit();
    },
    flyTo(lat, lon, zoom) {
      mapRef.current?.jumpTo({ center: [lon, lat], zoom });
    },
  }));

  useEffect(() => {
    if (broken || !host.current) return;
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: host.current,
        style: satelliteStyle(),
        center: center ? [center.lon, center.lat] : [79.5, 22.5],
        zoom: center ? 15.5 : 4,
        maxZoom: 19,
        dragRotate: false,
        pitchWithRotate: false,
        attributionControl: { compact: false },
      });
    } catch {
      setInitError(true);
      return;
    }
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("error", (e: unknown) => {
      // Tile failures are survivable: the plot can still be drawn. Say so without blocking.
      if ((e as unknown as { sourceId?: string }).sourceId) setTileError(true);
    });
    mapRef.current = map;
    if (import.meta.env.DEV) (window as unknown as { __fsMap?: unknown }).__fsMap = map;

    // Not "load": that waits for every satellite tile, and on a slow network drawing must not.
    map.once("style.load", () => {
      const polygon = new TerraDrawPolygonMode({
        pointerDistance: 36,
        styles: {
          fillColor: MAIZE,
          fillOpacity: 0.22,
          outlineColor: MAIZE,
          outlineWidth: 3,
          closingPointColor: "#FFFFFF",
          closingPointWidth: 13,
          closingPointOutlineColor: INK,
          closingPointOutlineWidth: 3,
          coordinatePointColor: "#FFFFFF",
          coordinatePointWidth: 9,
          coordinatePointOutlineColor: INK,
          coordinatePointOutlineWidth: 2,
        },
        showCoordinatePoints: true,
      });
      polyMode.current = polygon;
      const select = new TerraDrawSelectMode({
        pointerDistance: 36,
        flags: {
          polygon: {
            feature: {
              draggable: false,
              coordinates: { midpoints: true, draggable: true, deletable: true },
            },
          },
        },
        styles: {
          selectedPolygonColor: MAIZE,
          selectedPolygonFillOpacity: 0.22,
          selectedPolygonOutlineColor: MAIZE,
          selectedPolygonOutlineWidth: 3,
          selectionPointColor: "#FFFFFF",
          selectionPointWidth: 13,
          selectionPointOutlineColor: INK,
          selectionPointOutlineWidth: 3,
          midPointColor: MAIZE,
          midPointWidth: 9,
          midPointOutlineColor: INK,
          midPointOutlineWidth: 2,
        },
      });
      const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map, coordinatePrecision: 8 }),
        modes: [polygon, select],
      });
      draw.start();
      drawRef.current = draw;
      draw.setMode("polygon");
      phaseRef.current = "drawing";

      draw.on("change", () => emit());
      draw.on("finish", (id, ctx) => {
        if (ctx.mode === "polygon") toEditing(id);
        else emit();
      });
      // An already-saved field reopens ready to adjust.
      if (initialRing && initialRing.length >= 4) {
        const added = draw.addFeatures([
          {
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [closeRing(initialRing)] },
            properties: { mode: "polygon" },
          },
        ]);
        const firstId = added[0]?.id;
        if (added[0]?.valid && firstId !== undefined) {
          const [w, s, e, n] = bboxOfRing(initialRing);
          map.fitBounds([[w, s], [e, n]], { padding: 60, duration: 0, maxZoom: 18 });
          toEditing(firstId);
          return;
        }
      }
      emit();
    });

    return () => {
      try { drawRef.current?.stop(); } catch { /* map is going away regardless */ }
      drawRef.current = null;
      polyMode.current = null;
      map.remove();
      mapRef.current = null;
    };
    // Center and ring only seed the map once; they arrive before mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [broken]);

  if (broken || initError) {
    return <div className="plot-canvas plot-canvas-off"><p className="notice">{t("map.no_webgl")}</p></div>;
  }

  return (
    <div className="plot-canvas">
      <div ref={host} className="map-host" />
      <div className="places places-over" role="group" aria-label={t("map.places")}>
        {PLACES.map((p) => (
          <button key={p.id} className="chip" onClick={() => { mapRef.current?.jumpTo({ center: [p.lon, p.lat], zoom: p.zoom }); setPlace(p); }}>
            <Icon name="pin" size={16} /> {p.label[lang]}
          </button>
        ))}
      </div>
      {place && <PlaceNote place={place} over />}
      {tileError && <p className="map-note" role="status">{t("map.tiles_failed")}</p>}
    </div>
  );
});

export default PlotMap;
