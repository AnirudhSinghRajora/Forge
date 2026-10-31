// Only this indirection touches the map chunk, so the verdict page stays small until a map is near.
export type LoadedMap = { project: (ll: [number, number]) => { x: number; y: number } };

export function loadMap() {
  return import("./base");
}

export function canRunMapLazy(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}
