import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { Turn } from "../../tunerStrings";

// Epiphone Les Paul Standard '50s, Cardinal Red: built from code, no model file.
// Units are centimetres. Guitar frame: +y toward the headstock, +z out of the top, bass side at -x
// (front view, headstock up). The saddles sit at y = 0 and the nut at y = SCALE (24.75").
// Real dimensions: 43.8 cm body, 13" lower bout, 1.69" nut, 2 1/16" string spread at the bridge, 22 frets,
// 17 degree headstock, Kalamazoo "open book" headstock, Epiphone Deluxe tuners with Keystone buttons.
//
// Which way a key tightens: the strings leave a 3+3 post on its inner side, so the bass posts turn
// counter-clockwise and the treble posts clockwise (seen from the headstock face) to wind string on.
// The buttons follow the usual rule (bass side counter-clockwise, treble side clockwise, seen end-on);
// in this frame both sides then turn the same way about +x: BUTTON_TIGHTEN.

export const SCALE = 62.865;
const Y_NUT = SCALE;
const BUTTON_TIGHTEN = -1;
const HEAD_ANGLE = THREE.MathUtils.degToRad(17);

const C = {
  cardinal: "#8C0D17", cream: "#EDE0BF", nickel: "#D8D8D2", laurel: "#3B2519", black: "#0C0C0E",
  gold: "#C99A3A", pearl: "#D9D2BE", keystone: "#E8DDBF", plain: "#E4E4E0", wound: "#B9B1A1",
};

export type PegShow = { turn: Turn; offset: number; color: THREE.Color };

type Arrow = { group: THREE.Group; spin: THREE.Group };
type Peg = {
  string: number;
  side: -1 | 1;
  postSpin: THREE.Group;
  buttonSpin: THREE.Group;
  button: THREE.Mesh;
  buttonMat: THREE.MeshPhysicalMaterial;
  postArrow: Arrow;
  buttonArrow: Arrow;
  ring: THREE.Mesh;
  anchor: THREE.Object3D;   // where a label points: the button tip
  postAxis: THREE.Vector3;  // head frame
  buttonAxis: THREE.Vector3;
};
type GString = { mesh: THREE.Mesh; mat: THREE.MeshStandardMaterial; glow: THREE.Mesh; glowMat: THREE.MeshBasicMaterial };

export type LesPaul = {
  root: THREE.Group;
  head: THREE.Group;
  headFocus: THREE.Object3D;
  /** Guitar-frame y range, for framing. */
  span: [number, number];
  pickables: THREE.Object3D[];
  pegAnchor(string: number): THREE.Object3D | undefined;
  /** Show these strings (others go quiet); call every frame. */
  update(dt: number, shows: Map<number, PegShow>, motion: boolean): void;
  dispose(): void;
};

// ------------------------------------------------------------------ helpers
const v2 = (x: number, y: number) => new THREE.Vector2(x, y);
const fretY = (n: number) => Y_NUT - SCALE * (1 - 2 ** (-n / 12));
const smooth = (e0: number, e1: number, x: number) => { const t = THREE.MathUtils.clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };

/** Rows of points (each closed or open) -> one indexed surface. Normal = rowStep x tangent; flip if inside out. */
function loft(rows: THREE.Vector3[][], { closed = true, flip = false }: { closed?: boolean; flip?: boolean } = {}) {
  const n = rows[0].length;
  const pos: number[] = [];
  rows.forEach((row) => row.forEach((p) => pos.push(p.x, p.y, p.z)));
  const idx: number[] = [];
  const segs = closed ? n : n - 1;
  for (let r = 0; r < rows.length - 1; r++) {
    for (let i = 0; i < segs; i++) {
      const a = r * n + i, a1 = r * n + ((i + 1) % n), b = (r + 1) * n + i, b1 = (r + 1) * n + ((i + 1) % n);
      if (flip) idx.push(a, b1, b, a, a1, b1);
      else idx.push(a, b, b1, a, b1, a1);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** Flat polygon (counter-clockwise) -> triangulated, subdivided surface at z = h(x, y). Normals come from the height
 *  field itself, so a glossy finish stays smooth whatever shape the triangles have. */
function heightField(poly: THREE.Vector2[], levels: number, h: (x: number, y: number) => number) {
  const xy: number[] = poly.flatMap((p) => [p.x, p.y]);
  let faces = THREE.ShapeUtils.triangulateShape(poly, []);
  for (let l = 0; l < levels; l++) {
    const mids = new Map<number, number>();
    const mid = (a: number, b: number) => {
      const key = a < b ? a * 1e6 + b : b * 1e6 + a;
      let m = mids.get(key);
      if (m === undefined) { m = xy.length / 2; xy.push((xy[2 * a] + xy[2 * b]) / 2, (xy[2 * a + 1] + xy[2 * b + 1]) / 2); mids.set(key, m); }
      return m;
    };
    faces = faces.flatMap(([a, b, c]) => { const ab = mid(a, b), bc = mid(b, c), ca = mid(c, a); return [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]; });
  }
  const n = xy.length / 2, e = 0.05;
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const x = xy[2 * i], y = xy[2 * i + 1], z = h(x, y);
    const dx = (h(x + e, y) - z) / e, dy = (h(x, y + e) - z) / e, len = Math.hypot(dx, dy, 1);
    pos.set([x, y, z], 3 * i);
    nor.set([-dx / len, -dy / len, 1 / len], 3 * i);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  g.setIndex(faces.flat());
  return g;
}

function flipFaces(g: THREE.BufferGeometry) {
  const index = g.getIndex()!;
  for (let i = 0; i < index.count; i += 3) { const b = index.getX(i + 1); index.setX(i + 1, index.getX(i + 2)); index.setX(i + 2, b); }
  const nrm = g.getAttribute("normal");
  for (let i = 0; i < nrm.count; i++) nrm.setXYZ(i, -nrm.getX(i), -nrm.getY(i), -nrm.getZ(i));
  return g;
}

/** A cylinder from a to b. */
function rod(a: THREE.Vector3, b: THREE.Vector3, r: number, mat: THREE.Material, seg = 8) {
  const d = b.clone().sub(a);
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), seg, 1), mat);
  m.position.copy(a).addScaledVector(d, 0.5);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  return m;
}

/** BoxGeometry whose width follows w(y): the fretboard and its binding. */
function taperedBox(y0: number, y1: number, w: (y: number) => number, z0: number, z1: number) {
  const g = new THREE.BoxGeometry(1, y1 - y0, z1 - z0, 1, 1, 1);
  g.translate(0, (y0 + y1) / 2, (z0 + z1) / 2);
  const p = g.getAttribute("position");
  for (let i = 0; i < p.count; i++) p.setX(i, p.getX(i) * w(p.getY(i)));
  g.computeVertexNormals();
  return g;
}

/** Smooth closed outline through the points, counter-clockwise, evenly spaced. */
function outline(points: [number, number][], count: number) {
  const curve = new THREE.CatmullRomCurve3(points.map(([x, y]) => new THREE.Vector3(x, y, 0)), true, "centripetal");
  const pts = curve.getSpacedPoints(count).slice(0, count).map((p) => v2(p.x, p.y));
  if (THREE.ShapeUtils.area(pts) < 0) pts.reverse();
  return pts;
}

/** Outward unit normals of a counter-clockwise outline. */
const normalsOf = (pts: THREE.Vector2[]) => pts.map((_, i) => {
  const a = pts[(i - 1 + pts.length) % pts.length], b = pts[(i + 1) % pts.length];
  return v2(b.y - a.y, a.x - b.x).normalize();
});

function canvasTexture(w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) {
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  draw(cv.getContext("2d")!);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// Curved arrow in the XY plane, pointing counter-clockwise about +Z; `spin` turns it the same way.
const ARC = Math.PI * 1.45;
function arrowGeometries() {
  const arc = new THREE.TorusGeometry(1, 0.085, 8, 48, ARC);
  const head = new THREE.ConeGeometry(0.24, 0.55, 16);
  head.rotateZ(ARC);
  head.translate(Math.cos(ARC), Math.sin(ARC), 0);
  return { arc, head };
}

// ------------------------------------------------------------------ the body outline
// Les Paul body outline from cho2/guitar-shape "les-paul.svg" (CC BY-SA 4.0, https://github.com/cho2/guitar-shape),
// scaled to the real 43.8 cm length (it then measures 33.06 cm = 13" across, as the real body) and placed so the
// neck leaves the body at the 16th fret. cm, saddles at y = 0, treble cutaway on +x; the waists sit at y = 10
// (the treble one rests on the leg), the flat top edge is where the neck leaves the body.
const BODY: [number, number][] = [
  [3.00, 24.95], [2.24, 24.95], [1.49, 24.94], [0.74, 24.94], [-0.02, 24.94], [-0.77, 24.94],
  [-1.53, 24.93], [-2.28, 24.93], [-3.04, 24.93], [-3.79, 24.83], [-4.53, 24.73], [-5.28, 24.62],
  [-6.02, 24.46], [-6.73, 24.23], [-7.43, 23.95], [-8.11, 23.62], [-8.75, 23.23], [-9.34, 22.75],
  [-9.88, 22.23], [-10.38, 21.66], [-10.82, 21.05], [-11.18, 20.39], [-11.43, 19.68], [-11.58, 18.94],
  [-11.66, 18.19], [-11.65, 17.43], [-11.56, 16.69], [-11.38, 15.95], [-11.13, 15.24], [-10.81, 14.56],
  [-10.47, 13.88], [-10.14, 13.21], [-9.82, 12.52], [-9.52, 11.83], [-9.28, 11.12], [-9.16, 10.37],
  [-9.13, 9.62], [-9.20, 8.87], [-9.45, 8.16], [-9.86, 7.53], [-10.30, 6.91], [-10.76, 6.32],
  [-11.26, 5.75], [-11.77, 5.20], [-12.24, 4.61], [-12.71, 4.02], [-13.17, 3.42], [-13.62, 2.82],
  [-14.03, 2.18], [-14.42, 1.54], [-14.79, 0.88], [-15.14, 0.21], [-15.45, -0.48], [-15.67, -1.19],
  [-15.86, -1.93], [-16.02, -2.66], [-16.13, -3.41], [-16.20, -4.16], [-16.22, -4.92], [-16.22, -5.67],
  [-16.17, -6.42], [-16.10, -7.17], [-15.97, -7.92], [-15.80, -8.65], [-15.58, -9.37], [-15.33, -10.08],
  [-15.04, -10.78], [-14.71, -11.46], [-14.35, -12.12], [-13.95, -12.76], [-13.50, -13.37], [-13.02, -13.95],
  [-12.50, -14.50], [-11.96, -15.02], [-11.38, -15.51], [-10.77, -15.95], [-10.14, -16.37], [-9.50, -16.76],
  [-8.84, -17.12], [-8.16, -17.45], [-7.47, -17.75], [-6.76, -18.01], [-6.04, -18.23], [-5.30, -18.40],
  [-4.55, -18.50], [-3.81, -18.59], [-3.06, -18.69], [-2.31, -18.77], [-1.55, -18.82], [-0.80, -18.85],
  [-0.05, -18.85], [0.71, -18.84], [1.46, -18.83], [2.22, -18.82], [2.97, -18.78], [3.72, -18.70],
  [4.47, -18.60], [5.21, -18.47], [5.95, -18.31], [6.68, -18.13], [7.40, -17.91], [8.11, -17.65],
  [8.81, -17.37], [9.50, -17.05], [10.16, -16.69], [10.80, -16.29], [11.41, -15.85], [11.99, -15.37],
  [12.55, -14.86], [13.10, -14.35], [13.64, -13.82], [14.15, -13.26], [14.62, -12.67], [15.03, -12.04],
  [15.40, -11.38], [15.71, -10.70], [16.00, -10.00], [16.24, -9.28], [16.45, -8.56], [16.61, -7.82],
  [16.73, -7.08], [16.80, -6.33], [16.83, -5.57], [16.83, -4.82], [16.79, -4.06], [16.71, -3.31],
  [16.58, -2.57], [16.42, -1.84], [16.21, -1.11], [15.96, -0.40], [15.66, 0.30], [15.33, 0.97],
  [14.97, 1.63], [14.58, 2.28], [14.15, 2.90], [13.70, 3.51], [13.22, 4.09], [12.72, 4.65],
  [12.24, 5.23], [11.75, 5.81], [11.24, 6.37], [10.71, 6.90], [10.24, 7.49], [9.82, 8.12],
  [9.48, 8.79], [9.29, 9.52], [9.29, 10.27], [9.42, 11.01], [9.65, 11.73], [9.91, 12.44],
  [10.22, 13.13], [10.56, 13.80], [10.91, 14.47], [11.21, 15.16], [11.47, 15.87], [11.68, 16.59],
  [11.81, 17.34], [11.86, 18.09], [11.84, 18.84], [11.65, 19.57], [11.25, 20.20], [10.60, 20.53],
  [9.97, 20.17], [9.54, 19.55], [9.08, 18.95], [8.52, 18.45], [7.86, 18.07], [7.15, 17.83],
  [6.40, 17.79], [5.65, 17.88], [4.93, 18.09], [4.31, 18.52], [3.80, 19.07], [3.39, 19.70],
  [3.20, 20.43], [3.10, 21.18], [3.04, 21.93], [3.03, 22.68], [3.02, 23.44], [3.01, 24.19]
];
const RIM = 0.06;      // carve height at the binding
const DOME = 1.25;     // maple cap rise in the middle
const BACK = -4.3;     // mahogany back
const BIND_W = 0.28;   // single-ply cream binding on the top
const BIND_H = 0.38;

// Gibson Les Paul headstock outline (Epiphone's "60s Kalamazoo" is the same open book) from Wikimedia Commons
// "Gibson-headstock-LP.svg" by GreyCat (CC BY-SA 3.0). Scaled to the 4.29 cm nut, which gives the real 17.9 cm
// length; widened 10% above the throat to the measured 73 mm middle width (the drawing runs narrow). cm, v = 0 at
// the nut end, symmetric about u = 0; two humps and a small V notch at the top.
const HEAD: [number, number][] = [
  [-2.15, 0.01], [-1.75, 0.01], [-1.35, 0.01], [-0.95, 0.01], [-0.55, 0.00], [-0.16, 0.00],
  [0.24, -0.00], [0.64, -0.00], [1.04, -0.01], [1.43, -0.01], [1.83, -0.01], [2.15, 0.07],
  [2.22, 0.46], [2.34, 0.85], [2.52, 1.23], [2.71, 1.60], [2.94, 1.96], [3.17, 2.31],
  [3.41, 2.66], [3.65, 3.00], [3.69, 3.38], [3.66, 3.78], [3.64, 4.18], [3.62, 4.57],
  [3.60, 4.97], [3.59, 5.37], [3.56, 5.77], [3.55, 6.16], [3.55, 6.56], [3.54, 6.96],
  [3.54, 7.36], [3.54, 7.75], [3.54, 8.15], [3.54, 8.55], [3.55, 8.95], [3.56, 9.34],
  [3.58, 9.74], [3.60, 10.14], [3.62, 10.53], [3.64, 10.93], [3.66, 11.33], [3.70, 11.72],
  [3.73, 12.12], [3.77, 12.52], [3.82, 12.91], [3.86, 13.31], [3.92, 13.70], [3.97, 14.10],
  [4.04, 14.49], [4.10, 14.88], [4.17, 15.28], [4.25, 15.67], [4.32, 16.06], [4.41, 16.45],
  [4.50, 16.84], [4.27, 16.97], [3.83, 16.97], [3.40, 17.00], [2.97, 17.08], [2.55, 17.19],
  [2.15, 17.34], [1.76, 17.54], [1.39, 17.74], [0.97, 17.85], [0.54, 17.85], [0.12, 17.72],
  [-0.25, 17.77], [-0.67, 17.87], [-1.10, 17.85], [-1.51, 17.69], [-1.87, 17.47], [-2.25, 17.29],
  [-2.67, 17.16], [-3.09, 17.07], [-3.53, 17.02], [-3.96, 17.00], [-4.40, 17.01], [-4.49, 16.74],
  [-4.43, 16.35], [-4.37, 15.95], [-4.31, 15.56], [-4.27, 15.16], [-4.21, 14.77], [-4.17, 14.37],
  [-4.11, 13.98], [-4.07, 13.58], [-4.03, 13.19], [-3.99, 12.79], [-3.95, 12.40], [-3.92, 12.00],
  [-3.88, 11.60], [-3.85, 11.21], [-3.82, 10.81], [-3.80, 10.41], [-3.76, 10.02], [-3.74, 9.62],
  [-3.73, 9.22], [-3.71, 8.83], [-3.70, 8.43], [-3.69, 8.03], [-3.67, 7.63], [-3.67, 7.24],
  [-3.67, 6.84], [-3.67, 6.44], [-3.69, 6.04], [-3.70, 5.65], [-3.71, 5.25], [-3.73, 4.85],
  [-3.75, 4.45], [-3.78, 4.06], [-3.82, 3.66], [-3.86, 3.27], [-3.66, 2.94], [-3.41, 2.61],
  [-3.16, 2.26], [-2.92, 1.91], [-2.70, 1.54], [-2.52, 1.17], [-2.36, 0.79], [-2.23, 0.40]
];
/** Widest u of a closed outline at height v. */
const halfWidth = (pts: THREE.Vector2[], v: number) => {
  let m = 0;
  pts.forEach((a, i) => {
    const b = pts[(i + 1) % pts.length];
    if ((a.y - v) * (b.y - v) <= 0 && a.y !== b.y) m = Math.max(m, a.x + (b.x - a.x) * ((v - a.y) / (b.y - a.y)));
  });
  return m;
};

export function buildLesPaul(): LesPaul {
  const root = new THREE.Group();
  const geos = new Set<THREE.BufferGeometry>();
  const mats = new Set<THREE.Material>();
  const texs: THREE.Texture[] = [];
  const track = <T extends THREE.Material>(m: T) => { mats.add(m); return m; };

  // ---- materials (shared)
  const paint = track(new THREE.MeshPhysicalMaterial({ color: C.cardinal, roughness: 0.34, clearcoat: 1, clearcoatRoughness: 0.05 }));
  const cream = track(new THREE.MeshPhysicalMaterial({ color: C.cream, roughness: 0.38, clearcoat: 0.8, clearcoatRoughness: 0.1 }));
  const nickel = track(new THREE.MeshStandardMaterial({ color: C.nickel, metalness: 1, roughness: 0.24, envMapIntensity: 1.6 }));
  const darkNickel = track(new THREE.MeshStandardMaterial({ color: "#8C8C88", metalness: 1, roughness: 0.35 }));
  const laurel = track(new THREE.MeshStandardMaterial({ color: C.laurel, roughness: 0.72 }));
  const black = track(new THREE.MeshPhysicalMaterial({ color: C.black, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.05 }));
  const gold = track(new THREE.MeshPhysicalMaterial({ color: C.gold, metalness: 0.55, roughness: 0.28, clearcoat: 0.6 }));
  const pearl = track(new THREE.MeshPhysicalMaterial({ color: C.pearl, roughness: 0.25, iridescence: 0.6, iridescenceIOR: 1.6 }));
  const hole = track(new THREE.MeshStandardMaterial({ color: "#050505", roughness: 0.9 }));
  const nutMat = track(new THREE.MeshStandardMaterial({ color: "#F1ECDF", roughness: 0.45 }));

  // ---- body: carved cap, binding, sides and back
  const N = 240;
  const edge = outline(BODY, N);
  const nrm = normalsOf(edge);
  const bindIn = edge.map((p, i) => p.clone().addScaledVector(nrm[i], -BIND_W));
  const bodyTop = Math.max(...edge.map((p) => p.y));
  // the carve follows the distance from the edge: flat at the binding, a recurve, then up to the plateau
  const ex = Float64Array.from(edge, (p) => p.x), ey = Float64Array.from(edge, (p) => p.y);
  const edgeDist = (x: number, y: number) => {
    let m = Infinity;
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N, ax = ex[i], ay = ey[i], dx = ex[j] - ax, dy = ey[j] - ay;
      const t = THREE.MathUtils.clamp(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy), 0, 1);
      const qx = ax + t * dx - x, qy = ay + t * dy - y;
      m = Math.min(m, qx * qx + qy * qy);
    }
    return Math.sqrt(m);
  };
  const topZ = (x: number, y: number) => RIM + DOME * smooth(BIND_W + 0.2, 7.5, edgeDist(x, y));
  root.add(new THREE.Mesh(heightField(bindIn, 4, topZ), paint));
  root.add(new THREE.Mesh(loft([bindIn.map((p) => new THREE.Vector3(p.x, p.y, topZ(p.x, p.y))), edge.map((p) => new THREE.Vector3(p.x, p.y, RIM))]), cream));
  root.add(new THREE.Mesh(loft([edge.map((p) => new THREE.Vector3(p.x, p.y, RIM)), edge.map((p) => new THREE.Vector3(p.x, p.y, -BIND_H))]), cream));
  const inset = (d: number, z: number) => edge.map((p, i) => new THREE.Vector3(p.x - nrm[i].x * (0.02 + d), p.y - nrm[i].y * (0.02 + d), z));
  const sideRows = [inset(0, -BIND_H + 0.05), inset(0, BACK + 0.45)];
  for (let k = 1; k <= 5; k++) { const a = (k / 5) * Math.PI / 2; sideRows.push(inset(0.45 * (1 - Math.cos(a)), BACK + 0.45 * (1 - Math.sin(a)))); }
  root.add(new THREE.Mesh(loft(sideRows), paint));
  const backShape = new THREE.Shape(inset(0.45, 0).map((p) => v2(p.x, p.y)));
  const back = flipFaces(new THREE.ShapeGeometry(backShape, 1));
  back.translate(0, 0, BACK);
  root.add(new THREE.Mesh(back, paint));

  // ---- string plane, fretboard, frets, inlays, nut
  const zStr = topZ(0, 0) + 1.35;
  const fbTop = zStr - 0.2;
  const fbBot = fbTop - 0.62;
  const fbEnd = fretY(22) - 0.55;
  const fbW = (y: number) => 4.29 + (5.65 - 4.29) * (Y_NUT - y) / (Y_NUT - fretY(22));
  root.add(new THREE.Mesh(taperedBox(fbEnd, Y_NUT, (y) => fbW(y) + 0.22, fbBot, fbTop - 0.004), cream));
  root.add(new THREE.Mesh(taperedBox(fbEnd + 0.001, Y_NUT - 0.001, fbW, fbBot + 0.01, fbTop), laurel));
  for (let n = 1; n <= 22; n++) {
    const y = fretY(n);
    const f = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, fbW(y) + 0.1, 8), nickel);
    f.rotation.z = Math.PI / 2;
    f.position.set(0, y, fbTop + 0.02);
    root.add(f);
  }
  for (const n of [3, 5, 7, 9, 12, 15, 17, 19, 21]) {
    const y0 = fretY(n - 1), y1 = fretY(n), w = fbW((y0 + y1) / 2);
    const len = (y0 - y1) * 0.62, mid = (y0 + y1) / 2;
    const shape = new THREE.Shape([v2(-w * 0.32, mid - len / 2), v2(w * 0.32, mid - len / 2), v2(w * 0.26, mid + len / 2), v2(-w * 0.26, mid + len / 2)]);
    const inl = new THREE.Mesh(new THREE.ShapeGeometry(shape), pearl);
    inl.position.z = fbTop + 0.003;
    root.add(inl);
  }
  const nut = new THREE.Mesh(new RoundedBoxGeometry(4.3, 0.5, 1.1, 2, 0.08), nutMat);
  nut.position.set(0, Y_NUT + 0.25, fbTop - 0.35);
  root.add(nut);

  // ---- headstock frame: u = x, v along the headstock, w = face normal; face at w = 0
  const head = new THREE.Group();
  const headOrigin = new THREE.Vector3(0, Y_NUT + 0.5, fbTop - 0.9);
  head.position.copy(headOrigin);
  head.rotation.x = -HEAD_ANGLE;
  root.add(head);
  const faceZ = (y: number) => headOrigin.z - (y - headOrigin.y) * Math.tan(HEAD_ANGLE);

  // ---- neck: C profile under the fretboard, into the body at the heel, tapering into the headstock
  const neckRows: THREE.Vector3[][] = [];
  const Y_HEEL = 21, Y_END = Y_NUT + 2.2;
  for (let k = 0; k <= 40; k++) {
    const y = Y_HEEL + (Y_END - Y_HEEL) * (k / 40);
    const w = y > Y_NUT ? 4.35 - (y - Y_NUT) * 0.1 : fbW(Math.max(y, fretY(22)));
    const top = y > Y_NUT - 0.3 ? Math.min(fbBot, faceZ(y) - 0.05) : fbBot;
    let depth = THREE.MathUtils.lerp(2.05, 2.4, smooth(Y_NUT, fretY(12), y));
    if (y < bodyTop - 0.3) depth = Math.max(depth, fbBot - topZ(0, y) + 0.5);
    if (y > Y_NUT) depth = THREE.MathUtils.lerp(2.05, 1.3, (y - Y_NUT) / (Y_END - Y_NUT));
    const row: THREE.Vector3[] = [];
    for (let j = 0; j <= 22; j++) { const a = (j / 22) * Math.PI; row.push(new THREE.Vector3((w / 2) * Math.cos(a), y, top - depth * Math.sin(a))); }
    neckRows.push(row);
  }
  root.add(new THREE.Mesh(loft(neckRows, { flip: true }), paint));

  // ---- headstock wood, black face, logo, truss rod cover
  const headPts = outline(HEAD, 200);
  const headShape = new THREE.Shape(headPts);
  const wood = new THREE.ExtrudeGeometry(headShape, { depth: 1.19, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelOffset: -0.08, bevelSegments: 3, curveSegments: 4 });
  wood.translate(0, 0, -1.45 + 0.08);
  head.add(new THREE.Mesh(wood, paint));
  const veneer = new THREE.ExtrudeGeometry(headShape, { depth: 0.1, bevelEnabled: false });
  veneer.translate(0, 0, -0.1);
  head.add(new THREE.Mesh(veneer, black));
  const hw = (v: number) => halfWidth(headPts, v);
  // decals: Epiphone logo in mother of pearl, "Les Paul Model" in gold silkscreen, as the spec sheet says
  const decal = (tex: THREE.Texture, mat: THREE.Material, w: number, h: number, v: number, z = 0.012) => {
    texs.push(tex);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    m.position.set(0, v, z);
    head.add(m);
  };
  const logoTex = canvasTexture(1024, 300, (g) => {
    g.fillStyle = "#ffffff"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = "italic 700 200px 'Baskerville', 'Big Caslon', Georgia, serif";
    g.fillText("Epiphone", 512, 160);
  });
  decal(logoTex, track(new THREE.MeshPhysicalMaterial({ color: "#F3EFE6", map: logoTex, transparent: true, depthWrite: false, roughness: 0.18, iridescence: 1, iridescenceIOR: 1.45, iridescenceThicknessRange: [200, 600] })), 5.2, 1.52, 15.2);
  const modelTex = canvasTexture(1024, 360, (g) => {
    g.fillStyle = "#ffffff"; g.textAlign = "center"; g.textBaseline = "alphabetic";
    g.font = "italic 700 250px 'Snell Roundhand', 'Brush Script MT', 'Segoe Script', cursive";
    g.fillText("Les Paul", 500, 215);
    g.font = "700 82px 'Futura', 'Century Gothic', 'Trebuchet MS', sans-serif";
    g.letterSpacing = "20px";
    g.fillText("MODEL", 650, 330);
  });
  decal(modelTex, track(new THREE.MeshStandardMaterial({ color: "#E3B864", emissive: "#3A2A08", map: modelTex, transparent: true, depthWrite: false, metalness: 0.45, roughness: 0.4 })), 4.0, 1.41, 11.2);
  // 2-ply black bell truss rod cover (white under black shows as the edge), "Standard", three screws
  const BELL: [number, number][] = [[0.48, 0.55], [0.56, 1.2], [0.66, 1.9], [0.86, 2.6], [1.2, 3.2], [1.55, 3.75], [1.62, 4.05], [1.45, 4.3], [1.05, 4.38], [0.55, 4.4], [0.2, 4.5], [0, 4.62]];
  const bellPts = outline([...BELL, ...BELL.slice(0, -1).reverse().map(([x, y]) => [-x, y] as [number, number])], 90);
  const bellAt = (grow: number) => new THREE.Shape(bellPts.map((p) => v2(p.x * (1 + grow / 1.6), 2.6 + (p.y - 2.6) * (1 + grow / 2))));
  const trcEdge = new THREE.Mesh(new THREE.ExtrudeGeometry(bellAt(0), { depth: 0.05, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.06, bevelSegments: 2 }), track(new THREE.MeshPhysicalMaterial({ color: "#F2F0EA", roughness: 0.3, clearcoat: 1 })));
  const trc = new THREE.Mesh(new THREE.ExtrudeGeometry(bellAt(-0.1), { depth: 0.04, bevelEnabled: false }), black);
  trcEdge.position.z = 0.01; trc.position.z = 0.09;
  head.add(trcEdge, trc);
  const stdTex = canvasTexture(512, 160, (g) => {
    g.fillStyle = "#ffffff"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = "italic 700 128px 'Snell Roundhand', 'Brush Script MT', 'Segoe Script', cursive";
    g.fillText("Standard", 256, 88);
  });
  decal(stdTex, track(new THREE.MeshBasicMaterial({ color: "#EDEBE4", map: stdTex, transparent: true, depthWrite: false })), 2.6, 0.81, 3.25, 0.14);
  const screwGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.06, 12);
  screwGeo.rotateX(Math.PI / 2);
  for (const [u, v] of [[0, 0.95], [-1.15, 3.95], [1.15, 3.95]]) {
    const screw = new THREE.Mesh(screwGeo, nickel);
    screw.position.set(u, v, 0.15);
    head.add(screw);
  }

  // ---- tuners
  const arrowGeo = arrowGeometries();
  const coil = new THREE.TorusGeometry(0.34, 0.05, 6, 20);
  const buttonShape = new THREE.Shape();
  buttonShape.moveTo(0, -0.5); buttonShape.lineTo(1.6, -0.95);
  buttonShape.quadraticCurveTo(2.05, -0.95, 2.05, -0.55); buttonShape.lineTo(2.05, 0.55);
  buttonShape.quadraticCurveTo(2.05, 0.95, 1.6, 0.95); buttonShape.lineTo(0, 0.5); buttonShape.lineTo(0, -0.5);
  const buttonGeo = new THREE.ExtrudeGeometry(buttonShape, { depth: 0.42, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.1, bevelSegments: 3, curveSegments: 8 });
  buttonGeo.translate(0.25, 0, -0.21);
  const keystone = new THREE.MeshPhysicalMaterial({ color: C.keystone, roughness: 0.32, clearcoat: 0.6, transmission: 0.12, thickness: 0.4 });
  const pegs = new Map<number, Peg>();
  const strings = new Map<number, GString>();
  const pickables: THREE.Object3D[] = [];
  const POST_V = [5.6, 9.3, 13.0];
  const postTip = new Map<number, THREE.Vector3>();

  const makeArrow = (radius: number): Arrow => {
    const group = new THREE.Group();
    const spin = new THREE.Group();
    group.add(spin);
    spin.scale.setScalar(radius);
    group.visible = false;
    return { group, spin };
  };

  for (const s of [6, 5, 4, 3, 2, 1]) {
    const side: -1 | 1 = s >= 4 ? -1 : 1;
    const v = POST_V[side < 0 ? s - 4 : 3 - s];
    const u = side * (hw(v) - 1.4);
    const post = new THREE.Group();
    post.position.set(u, v, 0);
    head.add(post);
    const bushing = new THREE.Mesh(new THREE.CylinderGeometry(0.44, 0.47, 0.16, 20), nickel);
    bushing.rotation.x = Math.PI / 2; bushing.position.z = 0.08;
    post.add(bushing);
    const postSpin = new THREE.Group();
    post.add(postSpin);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.29, 0.3, 1.3, 16), nickel);
    shaft.rotation.x = Math.PI / 2; shaft.position.z = 0.65;
    const bore = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 0.62, 8), hole);
    bore.rotation.z = Math.PI / 2; bore.position.z = 1.05;
    postSpin.add(shaft, bore);
    const wraps = s >= 4 ? 2 : 3;
    for (let k = 0; k < wraps; k++) {
      const c = new THREE.Mesh(coil, s >= 4 ? darkNickel : nickel);
      c.position.z = 0.42 + k * 0.11;
      postSpin.add(c);
    }
    postSpin.userData.string = s;
    shaft.userData.string = s;
    pickables.push(shaft);

    // Kluson-style housing on the back, shaft out of the side, Keystone button
    const housing = new THREE.Mesh(new RoundedBoxGeometry(1.5, 1.7, 0.85, 2, 0.18), nickel);
    housing.position.set(u + side * 0.35, v, -1.45 - 0.42);
    head.add(housing);
    const shaftStart = side * (Math.abs(u) + 1.0);
    const shaftEnd = side * (hw(v) + 0.75);
    const stem = rod(new THREE.Vector3(shaftStart, v, -1.9), new THREE.Vector3(shaftEnd, v, -1.9), 0.13, nickel);
    const collar = rod(new THREE.Vector3(shaftEnd - side * 0.25, v, -1.9), new THREE.Vector3(shaftEnd, v, -1.9), 0.24, nickel, 16);
    head.add(stem, collar);
    const buttonSpin = new THREE.Group();
    buttonSpin.position.set(shaftEnd, v, -1.9);
    head.add(buttonSpin);
    const buttonMat = keystone.clone();
    track(buttonMat);
    const button = new THREE.Mesh(buttonGeo, buttonMat);
    if (side < 0) button.rotation.z = Math.PI;
    button.userData.string = s;
    buttonSpin.add(button);
    pickables.push(button);
    const anchor = new THREE.Object3D();
    anchor.position.set(shaftEnd + side * 3.9, v, -1.9);
    head.add(anchor);

    const postArrow = makeArrow(1.0);
    postArrow.group.position.set(u, v, 0.35);
    const buttonArrow = makeArrow(1.45);
    buttonArrow.group.position.set(shaftEnd + side * 1.2, v, -1.9);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.09, 8, 48), new THREE.MeshBasicMaterial({ toneMapped: false }));
    ring.position.set(u, v, 0.35);
    ring.visible = false;
    track(ring.material as THREE.Material);
    head.add(postArrow.group, buttonArrow.group, ring);

    const postAxis = new THREE.Vector3(0, 0, side < 0 ? 1 : -1);
    const buttonAxis = new THREE.Vector3(BUTTON_TIGHTEN, 0, 0);
    pegs.set(s, { string: s, side, postSpin, buttonSpin, button, buttonMat, postArrow, buttonArrow, ring, anchor, postAxis, buttonAxis });
    // where the string leaves the post (inner side), in the head frame
    postTip.set(s, new THREE.Vector3(u - side * 0.32, v, 0.42 + (wraps - 1) * 0.11 + 0.06));
  }

  // arrow meshes, one material per arrow so each can take its own colour
  for (const peg of pegs.values()) {
    for (const a of [peg.postArrow, peg.buttonArrow]) {
      const m = track(new THREE.MeshBasicMaterial({ toneMapped: false, transparent: true, opacity: 0.95 }));
      a.spin.add(new THREE.Mesh(arrowGeo.arc, m), new THREE.Mesh(arrowGeo.head, m));
    }
  }

  // ---- bridge, tailpiece, pickups, pickguard, knobs, switch
  const tuneOMatic = new THREE.Mesh(new RoundedBoxGeometry(8.3, 1.0, 0.55, 2, 0.12), nickel);
  tuneOMatic.position.set(0, 0, zStr - 0.48);
  root.add(tuneOMatic);
  for (const x of [-3.9, 3.9]) {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.22, 20), nickel);
    wheel.rotation.x = Math.PI / 2; wheel.position.set(x, 0, topZ(x, 0) + 0.25);
    const pin = rod(new THREE.Vector3(x, 0, topZ(x, 0)), new THREE.Vector3(x, 0, zStr - 0.5), 0.16, nickel);
    root.add(wheel, pin);
  }
  const xBridge = (k: number) => -2.6 + 1.04 * k;  // k = 0 for string 6
  const xNut = (k: number) => -1.75 + 0.7 * k;
  for (let k = 0; k < 6; k++) {
    const saddle = new THREE.Mesh(new RoundedBoxGeometry(0.62, 0.5, 0.3, 1, 0.06), nickel);
    saddle.position.set(xBridge(k), 0.05, zStr - 0.17);
    root.add(saddle);
  }
  const yTail = -6.3, zTail = topZ(0, yTail) + 1.0;
  const tail = new THREE.Mesh(new RoundedBoxGeometry(8.6, 1.3, 1.0, 3, 0.35), nickel);
  tail.position.set(0, yTail, zTail);
  root.add(tail);
  for (const x of [-4.3, 4.3]) {
    const stud = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.5, 20), nickel);
    stud.rotation.x = Math.PI / 2; stud.position.set(x, yTail, topZ(x, yTail) + 0.25);
    root.add(stud);
  }
  for (const [y, lift] of [[14.3, 0.75], [4.6, 0.62]] as const) {
    const cover = new THREE.Mesh(new RoundedBoxGeometry(7.0, 3.85, 0.9, 3, 0.25), nickel);
    const zc = zStr - lift - 0.45;
    cover.position.set(0, y, zc);
    const ringH = zc - topZ(0, y) + 0.1;
    const ringM = new THREE.Mesh(new RoundedBoxGeometry(8.6, 4.75, ringH, 2, 0.2), cream);
    ringM.position.set(0, y, topZ(0, y) + ringH / 2 - 0.15);
    root.add(cover, ringM);
    for (let k = 0; k < 6; k++) {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 12), darkNickel);
      pole.rotation.x = Math.PI / 2; pole.position.set(xBridge(k) * 1.0 * (y > 10 ? 0.92 : 0.98), y + 0.95, zc + 0.46);
      root.add(pole);
    }
  }
  const guard = new THREE.Shape(outline([[4.6, 16.9], [5.8, 17.1], [7.4, 16.8], [8.9, 15.8], [9.4, 13.8], [8.4, 11.0], [7.9, 8.8], [7.4, 6.6], [6.4, 4.6], [5.0, 3.9], [4.5, 6.5], [4.5, 12.5]], 64));
  const guardMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(guard, { depth: 0.12, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.05, bevelSegments: 2 }), cream);
  guardMesh.position.z = zStr - 1.25;
  root.add(guardMesh);
  // parts that sit on the carved top follow its slope
  const zAxis0 = new THREE.Vector3(0, 0, 1);
  const topNormal = (x: number, y: number) => {
    const e = 0.05, z = topZ(x, y);
    return new THREE.Vector3(-(topZ(x + e, y) - z) / e, -(topZ(x, y + e) - z) / e, 1).normalize();
  };
  const onTop = <T extends THREE.Object3D>(o: T, x: number, y: number, lift = 0) => {
    const n = topNormal(x, y);
    o.position.set(x, y, topZ(x, y)).addScaledVector(n, lift);
    o.quaternion.setFromUnitVectors(zAxis0, n);
    root.add(o);
    return o;
  };
  // gold top hat knobs with a dial pointer and the VOLUME / TONE insert
  const knobProfile = [v2(0, 0), v2(1.05, 0), v2(1.05, 0.22), v2(0.88, 0.28), v2(0.84, 1.45), v2(0.7, 1.6), v2(0, 1.6)];
  const knobGeo = new THREE.LatheGeometry(knobProfile, 32);
  knobGeo.rotateX(Math.PI / 2);
  const capGeo = new THREE.CircleGeometry(0.62, 32);
  const pointerGeo = new THREE.BoxGeometry(0.06, 0.32, 0.05);
  const insert = (word: string) => {
    const t = canvasTexture(256, 256, (g) => {
      g.fillStyle = "#C9C9C4"; g.beginPath(); g.arc(128, 128, 128, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#1A1A1A"; g.textAlign = "center"; g.textBaseline = "middle";
      g.font = `700 ${word.length > 4 ? 44 : 58}px 'Futura', 'Century Gothic', 'Trebuchet MS', sans-serif`;
      g.fillText(word, 128, 132);
    });
    texs.push(t);
    return track(new THREE.MeshStandardMaterial({ map: t, metalness: 0.8, roughness: 0.3 }));
  };
  const volume = insert("VOLUME"), tone = insert("TONE");
  ([[8.4, -4.6, volume], [12.4, -2.9, volume], [9.4, -9.6, tone], [13.2, -7.9, tone]] as const).forEach(([x, y, mat], k) => {
    const knob = new THREE.Group();
    knob.add(new THREE.Mesh(knobGeo, gold));
    const cap = new THREE.Mesh(capGeo, mat);
    cap.position.z = 1.61;
    cap.rotation.z = Math.PI / 2;
    const pointer = new THREE.Mesh(pointerGeo, nickel);
    pointer.position.set(0, 1.0, 0.25);
    knob.add(cap, pointer);
    onTop(knob, x, y, -0.03).rotateZ(-0.6 + k * 0.35);
  });

  // toggle switch: cream washer with gold RHYTHM / TREBLE lying on the carve, nickel nut, cream tip
  const SW = v2(-8.6, 19.0);
  const washerTex = canvasTexture(512, 512, (g) => {
    g.fillStyle = "#EDE0BF"; g.fillRect(0, 0, 512, 512);
    g.fillStyle = "#94661A"; g.textAlign = "center"; g.textBaseline = "middle";
    g.font = "800 56px 'Futura', 'Century Gothic', 'Trebuchet MS', sans-serif";
    const arc = (word: string, top: boolean) => {
      const step = 0.2, r = 168, span = step * (word.length - 1);
      [...word].forEach((ch, i) => {
        const a = top ? -Math.PI / 2 - span / 2 + i * step : Math.PI / 2 + span / 2 - i * step;
        g.save();
        g.translate(256 + r * Math.cos(a), 256 + r * Math.sin(a));
        g.rotate(top ? a + Math.PI / 2 : a - Math.PI / 2);
        g.fillText(ch, 0, 0);
        g.restore();
      });
    };
    arc("RHYTHM", true);
    arc("TREBLE", false);
  });
  texs.push(washerTex);
  const washerGeo = new THREE.RingGeometry(0.45, 1.75, 64, 6);
  washerGeo.rotateZ(Math.PI / 2); // RHYTHM toward the bass edge (up when playing), TREBLE toward the strings
  washerGeo.translate(SW.x, SW.y, 0);
  const wp = washerGeo.getAttribute("position");
  for (let i = 0; i < wp.count; i++) wp.setZ(i, topZ(wp.getX(i), wp.getY(i)) + 0.035);
  washerGeo.computeVertexNormals();
  root.add(new THREE.Mesh(washerGeo, track(new THREE.MeshPhysicalMaterial({ map: washerTex, roughness: 0.55, clearcoat: 0.25, clearcoatRoughness: 0.4 }))));
  const sw = new THREE.Group();
  const swNut = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.22, 24), nickel);
  swNut.rotation.x = Math.PI / 2; swNut.position.z = 0.14;
  const swBush = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.3, 16), nickel);
  swBush.rotation.x = Math.PI / 2; swBush.position.z = 0.38;
  const lever = rod(new THREE.Vector3(0, 0, 0.4), new THREE.Vector3(0, 0, 2.55), 0.085, nickel);
  const tipGeo = new THREE.LatheGeometry([v2(0, 0), v2(0.24, 0), v2(0.29, 0.25), v2(0.3, 0.6), v2(0.24, 0.82), v2(0, 0.88)], 20);
  tipGeo.rotateX(Math.PI / 2);
  const tip = new THREE.Mesh(tipGeo, cream);
  tip.position.z = 2.45;
  sw.add(swNut, swBush, lever, tip);
  onTop(sw, SW.x, SW.y);

  // strap buttons (bottom and upper bout), cream square jack plate on the treble side
  const strapGeo = new THREE.LatheGeometry([v2(0, 0), v2(0.32, 0), v2(0.32, 0.45), v2(0.2, 0.55), v2(0.2, 0.8), v2(0.48, 0.88), v2(0.5, 1.0), v2(0, 1.05)], 20);
  const strap = new THREE.Mesh(strapGeo, nickel);
  strap.rotation.z = Math.PI; strap.position.set(0, Math.min(...edge.map((p) => p.y)) + 0.02, -2.0);
  const strap2 = new THREE.Mesh(strapGeo, nickel);
  strap2.rotation.x = -Math.PI / 2; strap2.position.set(-7.4, 22.0, BACK);
  root.add(strap, strap2);
  const jackAt = edge.reduce((best, p, i) => (p.x > 0 && Math.abs(p.y + 10.6) < Math.abs(edge[best].y + 10.6) ? i : best), 0);
  const jack = new THREE.Group();
  const plate = new THREE.Mesh(new RoundedBoxGeometry(2.6, 2.6, 0.14, 2, 0.12), cream);
  const socket = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.3, 24), nickel);
  socket.rotation.x = Math.PI / 2; socket.position.z = 0.18;
  const socketHole = new THREE.Mesh(new THREE.CircleGeometry(0.33, 20), hole);
  socketHole.position.z = 0.34;
  jack.add(plate, socket, socketHole);
  const jn = nrm[jackAt];
  jack.position.set(edge[jackAt].x + jn.x * 0.08, edge[jackAt].y + jn.y * 0.08, BACK / 2);
  jack.quaternion.setFromUnitVectors(zAxis0, new THREE.Vector3(jn.x, jn.y, 0));
  root.add(jack);
  // black control cavity covers on the back
  const coverMat = track(new THREE.MeshPhysicalMaterial({ color: "#0D0D0F", roughness: 0.35, clearcoat: 0.6 }));
  const backCover = (pts: THREE.Vector2[]) => {
    const g = flipFaces(new THREE.ShapeGeometry(new THREE.Shape(pts), 1));
    g.translate(0, 0, BACK - 0.02);
    root.add(new THREE.Mesh(g, coverMat));
  };
  backCover(outline([[7.0, -1.6], [13.6, -0.4], [15.0, -6.4], [14.0, -11.2], [8.6, -12.4], [6.8, -7.0]], 64));
  backCover(Array.from({ length: 40 }, (_, i) => v2(SW.x + 2.1 * Math.cos((i / 40) * Math.PI * 2), SW.y + 2.1 * Math.sin((i / 40) * Math.PI * 2))));

  // ---- strings: tailpiece -> saddle -> nut -> post
  root.updateMatrixWorld(true);
  const headM = head.matrix;
  for (let k = 0; k < 6; k++) {
    const s = 6 - k;
    const r = [0.066, 0.053, 0.041, 0.031, 0.021, 0.016][k];
    const mat = track(new THREE.MeshStandardMaterial({ color: s >= 4 ? C.wound : C.plain, metalness: 1, roughness: s >= 4 ? 0.42 : 0.18, emissive: "#000000" }));
    const saddleP = new THREE.Vector3(xBridge(k), 0.05, zStr);
    const nutP = new THREE.Vector3(xNut(k), Y_NUT + 0.25, zStr - 0.02);
    const tailP = new THREE.Vector3(xBridge(k) * 0.95, yTail + 0.4, zTail + 0.25);
    const postP = postTip.get(s)!.clone().applyMatrix4(headM);
    const mesh = rod(saddleP, nutP, r, mat, 6);
    root.add(mesh, rod(tailP, saddleP, r, mat, 6), rod(nutP, postP, r, mat, 6));
    const glowMat = track(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, toneMapped: false }));
    const glow = rod(saddleP, nutP, r + 0.07, glowMat, 8);
    glow.visible = false;
    root.add(glow);
    mesh.userData.string = s;
    pickables.push(mesh);
    strings.set(s, { mesh, mat, glow, glowMat });
  }

  const headFocus = new THREE.Object3D();
  headFocus.position.set(0, 9.6, 0);
  head.add(headFocus);

  root.traverse((o) => { if ((o as THREE.Mesh).isMesh) geos.add((o as THREE.Mesh).geometry); });

  // ---- animation state
  let t = 0;
  const qTmp = new THREE.Quaternion();
  const zAxis = new THREE.Vector3(0, 0, 1);
  const axTmp = new THREE.Vector3();
  const orient = (a: Arrow, axis: THREE.Vector3, sign: number) => {
    axTmp.copy(axis).multiplyScalar(sign);
    a.group.quaternion.copy(qTmp.setFromUnitVectors(zAxis, axTmp));
  };

  function update(dt: number, shows: Map<number, PegShow>, motion: boolean) {
    t += dt;
    for (const [s, peg] of pegs) {
      const show = shows.get(s);
      const str = strings.get(s)!;
      const turning = !!show && show.turn !== "hold";
      peg.postArrow.group.visible = turning;
      peg.buttonArrow.group.visible = turning;
      peg.ring.visible = !!show && show.turn === "hold";
      str.glow.visible = !!show;
      if (!show) {
        peg.buttonMat.emissive.setRGB(0, 0, 0);
        str.mat.emissive.setRGB(0, 0, 0);
        continue;
      }
      peg.buttonMat.emissive.copy(show.color).multiplyScalar(0.35);
      str.mat.emissive.copy(show.color).multiplyScalar(0.25);
      str.glowMat.color.copy(show.color);
      str.glowMat.opacity = 0.28 + (motion ? 0.12 * Math.sin(t * 9) : 0);
      // a plucked string: a fast shimmer across the string plane
      str.glow.position.x = motion ? str.mesh.position.x + Math.sin(t * 61 + s) * 0.03 : str.mesh.position.x;
      if (show.turn === "hold") {
        (peg.ring.material as THREE.MeshBasicMaterial).color.copy(show.color);
        peg.ring.scale.setScalar(motion ? 1 + 0.06 * Math.sin(t * 4) : 1);
        continue;
      }
      const sign = show.turn === "tighten" ? 1 : -1;
      orient(peg.postArrow, peg.postAxis, sign);
      orient(peg.buttonArrow, peg.buttonAxis, sign);
      for (const a of [peg.postArrow, peg.buttonArrow]) (a.spin.children[0] as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>).material.color.copy(show.color);
      if (!motion) continue;
      // further off -> faster; the button turns ~4x the post (14:1 gears, slowed down to stay readable)
      const w = THREE.MathUtils.clamp(Math.abs(show.offset) / 50, 0.35, 1) * 2.2;
      peg.postArrow.spin.rotation.z += w * dt;
      peg.buttonArrow.spin.rotation.z += w * dt;
      peg.postSpin.rotateOnAxis(peg.postAxis, sign * w * 0.5 * dt);
      peg.buttonSpin.rotateOnAxis(peg.buttonAxis, sign * w * 2 * dt);
    }
  }

  function dispose() {
    geos.forEach((g) => g.dispose());
    arrowGeo.arc.dispose(); arrowGeo.head.dispose(); coil.dispose(); buttonGeo.dispose();
    mats.forEach((m) => m.dispose());
    keystone.dispose();
    texs.forEach((x) => x.dispose());
  }

  return {
    root, head, headFocus, span: [-19.4, headOrigin.y + 18.4 * Math.cos(HEAD_ANGLE)], pickables,
    pegAnchor: (s) => pegs.get(s)?.anchor,
    update, dispose,
  };
}
