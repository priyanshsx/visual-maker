// The 3D part of the device demo: a floating screen (rounded bezel + screenshot),
// a soft brand-colour glow behind it, and an optional pulsing ring on the focus point.
// Everything is driven by the frame number, so every render is identical.
import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useEffect, useMemo, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import * as THREE from "three";
import { FOV, FPS, MOVE_SECONDS, PANEL_WORLD_WIDTH, cameraAt, phaseAt } from "./timeline";
import { Dust, FogRig, LightBeam, ReflectiveFloor } from "./cinematic/Atmosphere";
import { LensEffects } from "./cinematic/Effects";
import { RedrawOnFrame } from "./shared";
import type { DeviceDemoProps } from "./types";

const BEZEL = 0.07;         // bezel width around the screenshot (world units)
const DEPTH = 0.08;         // panel thickness

function isDark(hex: string): boolean {
  const n = parseInt(hex.slice(1), 16);
  const lum = 0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255);
  return lum < 128;
}

function roundedRect(w: number, h: number, r: number): THREE.Shape {
  const s = new THREE.Shape();
  const x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y);
  s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h);
  s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r);
  s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

function glowTexture(color: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 512;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(256, 256, 0, 256, 256, 256);
  grad.addColorStop(0, color);
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 512, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Load every screenshot before the first frame is captured
function useTextures(srcs: string[]): THREE.Texture[] | null {
  const [textures, setTextures] = useState<THREE.Texture[] | null>(null);
  const [handle] = useState(() => delayRender("Loading screenshots"));
  useEffect(() => {
    const loader = new THREE.TextureLoader();
    Promise.all(srcs.map((src) => loader.loadAsync(src))).then((list) => {
      list.forEach((t) => {
        t.colorSpace = THREE.SRGBColorSpace;
        t.anisotropy = 8;
        t.minFilter = THREE.LinearMipmapLinearFilter;
        t.generateMipmaps = true;
      });
      setTextures(list);
      continueRender(handle);
    });
  }, [srcs, handle]);
  return textures;
}

// How visible each screenshot is at this frame (cross-fades when a step changes image)
function imageWeights(p: DeviceDemoProps, frame: number): number[] {
  const w = p.images.map(() => 0);
  const ph = phaseAt(p, frame);
  const stepIndex = ph.kind === "step" ? ph.index : ph.kind === "intro" ? 0 : p.steps.length - 1;
  const current = p.steps[stepIndex].image;
  const fade = Math.round(MOVE_SECONDS * FPS * 0.6);
  if (ph.kind === "step" && ph.index > 0) {
    const prev = p.steps[ph.index - 1].image;
    const t = Math.min(Math.max((frame - ph.start) / fade, 0), 1);
    if (prev !== current) {
      w[prev] = 1 - t;
      w[current] = t;
      return w;
    }
  }
  w[current] = 1;
  return w;
}

export const Screen3D: React.FC<{ p: DeviceDemoProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  const srcs = useMemo(() => p.images.map((i) => i.src), [p.images]);
  const textures = useTextures(srcs);
  const dark = isDark(p.brand.colors.background);
  const aspect = p.images[0].aspect;
  const W = PANEL_WORLD_WIDTH;
  const H = W / aspect;

  const bezelGeo = useMemo(() => {
    const g = new THREE.ExtrudeGeometry(roundedRect(W + 2 * BEZEL, H + 2 * BEZEL, 0.14), {
      depth: DEPTH, bevelEnabled: true, bevelThickness: 0.015, bevelSize: 0.015, bevelSegments: 4, curveSegments: 16,
    });
    g.translate(0, 0, -DEPTH);
    return g;
  }, [W, H]);
  const glow = useMemo(() => glowTexture(p.brand.colors.primary), [p.brand.colors.primary]);

  const cam = cameraAt(p, frame);
  const weights = imageWeights(p, frame);
  const ph = phaseAt(p, frame);
  const cine = p.look === "cinematic";
  const seconds = frame / FPS;
  const bg = p.brand.colors.background;

  // Focus ring: only on steps that ask for it, after the camera has arrived
  let ring: { x: number; y: number; r: number; opacity: number; scale: number } | null = null;
  if (ph.kind === "step" && p.steps[ph.index].marker) {
    const st = p.steps[ph.index];
    const arrive = ph.start + Math.round(MOVE_SECONDS * FPS);
    const t = (frame - arrive) / FPS;
    if (t > 0) {
      const pop = Math.min(t / 0.35, 1);
      ring = {
        x: (st.focus[0] - 0.5) * W,
        y: (0.5 - st.focus[1]) * H,
        r: 44 * cam.wpp * (p.width / 1080),
        opacity: pop * (0.75 + 0.25 * Math.sin(t * 5)),
        scale: 0.6 + 0.4 * pop + 0.06 * Math.sin(t * 5),
      };
    }
  }

  // Screen ratio for each image: fit inside the panel (first image fills it exactly)
  const fit = (a: number): [number, number] => (a >= aspect ? [W, W / a] : [H * a, H]);

  return (
    <ThreeCanvas
      frameloop="demand"
      width={p.width}
      height={p.height}
      dpr={2}
      gl={{ antialias: true, alpha: !cine, preserveDrawingBuffer: true }}
      camera={{ fov: FOV, near: 0.05, far: 200, position: [cam.x, cam.y, cam.z] }}
      style={{ position: "absolute", inset: 0 }}
    >
      <CameraRig x={cam.x} y={cam.y} z={cam.z} roll={cam.roll} />
      <RedrawOnFrame />
      {cine && (
        <>
          <color attach="background" args={[bg]} />
          <FogRig color={bg} camZ={cam.z} />
          <ReflectiveFloor y={-H / 2 - BEZEL - 0.22} color={dark ? "#0d0f12" : "#dfe5f2"} />
          <Dust seconds={seconds} color={dark ? "#d8fff0" : p.brand.colors.primary} />
          <LightBeam color={p.brand.colors.primary} width={W * 0.9} top={H / 2 + 3.2} seconds={seconds} />
          <LensEffects width={p.width} height={p.height} bloom={dark ? 0.65 : 0.3} />
        </>
      )}
      <ambientLight intensity={dark ? 0.9 : 1.4} />
      <directionalLight position={[-4, 6, 8]} intensity={2.2} />
      <pointLight position={[0, 0, -2]} intensity={6} distance={10} color={p.brand.colors.primary} />
      <directionalLight position={[5, -3, 4]} intensity={dark ? 1.2 : 0.6} color={p.brand.colors.primary} />

      <group position={[0, cam.lift, cam.depth]} rotation={[cam.rotX, cam.rotY, 0]}>
        <mesh position={[0, 0, -0.6]} scale={[W * 1.9, H * 2.2, 1]}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial map={glow} transparent opacity={dark ? 0.35 : 0.22} depthWrite={false}
            blending={dark ? THREE.AdditiveBlending : THREE.NormalBlending} />
        </mesh>
        <mesh geometry={bezelGeo}>
          <meshStandardMaterial color={dark ? "#2a2e35" : "#111827"} metalness={0.45} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0, 0.018]}>
          <planeGeometry args={[W, H]} />
          <meshBasicMaterial color={p.brand.colors.surface} toneMapped={false} />
        </mesh>
        {textures && p.images.map((img, i) => weights[i] > 0 && (
          <mesh key={i} position={[0, 0, 0.02 + i * 0.001]}>
            <planeGeometry args={fit(img.aspect)} />
            <meshBasicMaterial map={textures[i]} toneMapped={false} transparent opacity={weights[i]} />
          </mesh>
        ))}
        {ring && (
          <mesh position={[ring.x, ring.y, 0.04]} scale={[ring.scale, ring.scale, 1]}>
            <ringGeometry args={[ring.r * 0.82, ring.r, 64]} />
            <meshBasicMaterial color={p.brand.colors.primary} transparent opacity={ring.opacity} toneMapped={false} />
          </mesh>
        )}
      </group>
    </ThreeCanvas>
  );
};

// Moves the camera every frame (the camera prop above only sets the starting position)
const CameraRig: React.FC<{ x: number; y: number; z: number; roll: number }> = ({ x, y, z, roll }) => {
  const camera = useThree((s) => s.camera);
  camera.position.set(x, y, z);
  camera.rotation.set(0, 0, roll);
  camera.updateProjectionMatrix();
  return null;
};
