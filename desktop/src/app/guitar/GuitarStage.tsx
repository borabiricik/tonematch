import * as React from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { buildLesPaul, type PegShow } from "./lesPaul";
import { TURN_TEXT, toneOf, type StringState, type Tone } from "../../tunerStrings";

// The tuner's 3D stage: the player's guitar, drag to turn it all the way round, wheel to zoom.
// When the tuner opens the camera flies to the headstock; the string being tuned lights up and its key
// shows which way to turn (arrows around the post and the button, both spinning that way). The close-up leans
// toward the side of the string being tuned so its button is seen end-on, unless the player moved the camera.
// Lazy-loaded (three.js is large); the page falls back to the plain tuner if WebGL is not there.

export type Focus = "body" | "head";
type Show = PegShow & { tone: Tone };

type Props = {
  focus: Focus;
  /** Close-up leans toward this side of the headstock: -1 bass (strings 6-4), 1 treble, 0 straight on. */
  lean?: -1 | 0 | 1;
  shows: StringState[];
  targetOf: (string: number) => string;
  onPick?: (string: number) => void;
  onFail?: () => void;
};

const FOV = 30;
const FLY_MS = 1100;
const BODY_DIR = new THREE.Vector3(-0.1, 0.2, 1).normalize();
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export default function GuitarStage({ focus, lean = 0, shows, targetOf, onPick, onFail }: Props) {
  const host = React.useRef<HTMLDivElement>(null);
  const labels = React.useRef(new Map<number, HTMLDivElement>());
  const showsRef = React.useRef(new Map<number, Show>());
  const focusRef = React.useRef(focus);
  const leanRef = React.useRef(lean);
  const api = React.useRef<{ fly(to: Focus, instant?: boolean): void; moved(): boolean; colors(): Record<Tone, THREE.Color> } | null>(null);
  const pickRef = React.useRef(onPick);
  pickRef.current = onPick;
  const failRef = React.useRef(onFail);
  failRef.current = onFail;

  React.useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      failRef.current?.();
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.0;
    el.prepend(renderer.domElement);
    const canvas = renderer.domElement;
    canvas.setAttribute("aria-hidden", "true");

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const env = pmrem.fromScene(room, 0.04).texture;
    pmrem.dispose();
    room.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry.dispose(); (m.material as THREE.Material).dispose(); } });
    scene.environment = env;
    scene.environmentIntensity = 0.85;
    const key = new THREE.DirectionalLight("#fff6e8", 2.4);
    key.position.set(-40, 60, 90);
    const rim = new THREE.DirectionalLight("#cfe0ff", 1.4);
    rim.position.set(60, -30, -80);
    scene.add(key, rim, new THREE.HemisphereLight("#ffffff", "#30343c", 0.35));

    const guitar = buildLesPaul();
    guitar.root.rotation.z = -Math.PI / 2; // neck to the right, bass side up: the player's view
    guitar.root.position.x = -(guitar.span[0] + guitar.span[1]) / 2;
    scene.add(guitar.root);
    scene.updateMatrixWorld(true);
    const length = guitar.span[1] - guitar.span[0];

    const camera = new THREE.PerspectiveCamera(FOV, 1, 1, 2000);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.zoomToCursor = true; // the wheel zooms where the pointer is (a knob, the switch); double-click frames again
    controls.rotateSpeed = 0.75;
    controls.minDistance = 10;
    controls.maxDistance = 320;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const tan = Math.tan(THREE.MathUtils.degToRad(FOV / 2));
    const pose = (to: Focus) => {
      const aspect = Math.max(camera.aspect, 0.3);
      if (to === "body") {
        const d = Math.max(length / 2 / (tan * aspect * 0.88), 20 / tan);
        return { target: new THREE.Vector3(0, 0, 0), pos: BODY_DIR.clone().multiplyScalar(d) };
      }
      const target = guitar.headFocus.getWorldPosition(new THREE.Vector3());
      const normal = new THREE.Vector3(0, 0, 1).transformDirection(guitar.head.matrixWorld);
      const dir = normal.add(new THREE.Vector3(-0.12, 0.22, 0));
      if (leanRef.current) {
        const side = new THREE.Vector3(leanRef.current, 0, 0).transformDirection(guitar.root.matrixWorld);
        dir.addScaledVector(side, 0.75);
        target.addScaledVector(side, 2.5); // keep that side's buttons in the frame
      }
      dir.normalize();
      const d = Math.max(12 / (tan * aspect), 9 / tan);
      return { target, pos: target.clone().addScaledVector(dir, d) };
    };
    let fly: { p0: THREE.Vector3; t0: THREE.Vector3; p1: THREE.Vector3; t1: THREE.Vector3; start: number } | null = null;
    let moved = false; // the player turned the camera since the last automatic move
    const flyTo = (to: Focus, instant = false) => {
      moved = false;
      const { target, pos } = pose(to);
      if (instant || reduce.matches) {
        camera.position.copy(pos); controls.target.copy(target); controls.update(); fly = null;
        return;
      }
      fly = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos, t1: target, start: performance.now() };
    };
    controls.addEventListener("start", () => { fly = null; moved = true; }); // the player grabbed it: stop flying

    const cssColor = (name: string) => new THREE.Color(getComputedStyle(el).getPropertyValue(name).trim() || "#ffffff");
    const readColors = (): Record<Tone, THREE.Color> => ({ ok: cssColor("--success"), near: cssColor("--warning"), far: cssColor("--danger") });
    let colors = readColors();
    const recolor = () => {
      colors = readColors();
      for (const show of showsRef.current.values()) show.color.copy(colors[show.tone]);
    };
    const themeWatch = new MutationObserver(recolor);
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", recolor);
    api.current = { fly: flyTo, moved: () => moved, colors: () => colors };

    let sized = false;
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
      // first size, or the stage changed shape (single <-> multi): frame again unless the player moved the camera
      if (!sized || (!moved && !fly)) { sized = true; flyTo(focusRef.current, true); }
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    // click (not drag) on a key or string picks that string; hover shows it is clickable
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let down: { x: number; y: number } | null = null;
    let hover: { x: number; y: number } | null = null;
    const hit = (x: number, y: number) => {
      const r = canvas.getBoundingClientRect();
      ndc.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const first = ray.intersectObjects(guitar.pickables, false)[0];
      return (first?.object.userData.string as number | undefined) ?? null;
    };
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY }; };
    const onUp = (e: PointerEvent) => {
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 5) {
        const s = hit(e.clientX, e.clientY);
        if (s !== null) pickRef.current?.(s);
      }
      down = null;
    };
    const onMove = (e: PointerEvent) => { if (!down) hover = { x: e.clientX, y: e.clientY }; };
    const onDbl = () => flyTo(focusRef.current);
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("dblclick", onDbl);
    const onLost = (e: Event) => { e.preventDefault(); failRef.current?.(); };
    canvas.addEventListener("webglcontextlost", onLost);

    const clock = new THREE.Clock();
    const world = new THREE.Vector3();
    renderer.setAnimationLoop(() => {
      const dt = Math.min(clock.getDelta(), 0.05);
      if (fly) {
        const k = Math.min(1, (performance.now() - fly.start) / FLY_MS);
        const e = ease(k);
        camera.position.lerpVectors(fly.p0, fly.p1, e);
        controls.target.lerpVectors(fly.t0, fly.t1, e);
        if (k >= 1) fly = null;
      }
      controls.update();
      if (hover) {
        const pickable = !!pickRef.current && hit(hover.x, hover.y) !== null;
        canvas.style.cursor = pickable ? "pointer" : "";
        hover = null;
      }
      guitar.update(dt, showsRef.current, !reduce.matches);
      renderer.render(scene, camera);
      // labels follow the button of their string
      const w = el.clientWidth, h = el.clientHeight;
      for (const [s, div] of labels.current) {
        const a = guitar.pegAnchor(s);
        if (!a) continue;
        a.getWorldPosition(world).project(camera);
        // kept inside the frame; hidden only when behind the camera
        const x = THREE.MathUtils.clamp(((world.x + 1) / 2) * w, 70, w - 70);
        const y = THREE.MathUtils.clamp(((1 - world.y) / 2) * h, 30, h - 56);
        div.style.opacity = world.z < 1 ? "1" : "0";
        div.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
      }
    });

    return () => {
      renderer.setAnimationLoop(null);
      ro.disconnect();
      themeWatch.disconnect();
      scheme.removeEventListener("change", recolor);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("dblclick", onDbl);
      canvas.removeEventListener("webglcontextlost", onLost);
      controls.dispose();
      guitar.dispose();
      env.dispose();
      renderer.dispose();
      canvas.remove();
      api.current = null;
    };
  }, []);

  React.useEffect(() => {
    focusRef.current = focus;
    api.current?.fly(focus);
  }, [focus]);

  React.useEffect(() => {
    leanRef.current = lean;
    if (focusRef.current === "head" && api.current && !api.current.moved()) api.current.fly("head");
  }, [lean]);

  React.useEffect(() => {
    const colors = api.current?.colors();
    const m = new Map<number, Show>();
    for (const s of shows) {
      const tone = toneOf(s);
      m.set(s.string, { turn: s.turn, offset: s.offset, tone, color: colors ? colors[tone].clone() : new THREE.Color("#ffffff") });
    }
    showsRef.current = m;
  }, [shows]);

  return (
    <div ref={host} className="guitar3d">
      {shows.map((s) => (
        <div key={s.string} className="guitar3d__label" data-tone={toneOf(s)}
          ref={(d) => { if (d) labels.current.set(s.string, d); else labels.current.delete(s.string); }}>
          <span className="t-small">{s.string}. tel · {targetOf(s.string)}</span>
          <strong>{s.turn === "hold" ? "Akortta" : TURN_TEXT[s.turn]}</strong>
        </div>
      ))}
    </div>
  );
}
