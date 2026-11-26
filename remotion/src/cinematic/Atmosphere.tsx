// Cinematic 3D surroundings, made from plain shapes (no 3D models):
//   - fog that swallows anything far from the camera
//   - a dark, wet-looking floor that reflects the screen with a soft blur
//   - slow-floating dust that catches the light
//   - a soft beam of brand-coloured light from above
// Everything moves with the frame number, so renders are identical every time.
import { MeshReflectorMaterial } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useMemo } from "react";
import * as THREE from "three";
import { seeded } from "./random";

// Fog follows the camera: clear around the subject, fading out behind it
export const FogRig: React.FC<{ color: string; camZ: number }> = ({ color, camZ }) => {
  const scene = useThree((s) => s.scene);
  if (!(scene.fog instanceof THREE.Fog)) scene.fog = new THREE.Fog(color, 1, 2);
  const fog = scene.fog as THREE.Fog;
  fog.color.set(color);
  fog.near = camZ + 1.5;
  fog.far = camZ + 16;
  return null;
};

export const ReflectiveFloor: React.FC<{ y: number; color: string }> = ({ y, color }) => (
  <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
    <planeGeometry args={[80, 80]} />
    <MeshReflectorMaterial
      blur={[240, 80]}
      resolution={1024}
      mixBlur={0.8}
      mixStrength={45}
      roughness={0.75}
      depthScale={1.1}
      minDepthThreshold={0.4}
      maxDepthThreshold={1.4}
      color={color}
      metalness={0.6}
      mirror={0.75}
    />
  </mesh>
);

function dotTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.4, "rgba(255,255,255,0.35)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export const Dust: React.FC<{ seconds: number; color: string; count?: number }> = ({ seconds, color, count = 260 }) => {
  const base = useMemo(() => {
    const rnd = seeded(7);
    return Array.from({ length: count }, () => [
      (rnd() - 0.5) * 14, rnd() * 7 - 2.5, (rnd() - 0.65) * 12, rnd() * Math.PI * 2, 0.04 + rnd() * 0.08,
    ]);
  }, [count]);
  const sprite = useMemo(() => dotTexture(), []);
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    return g;
  }, [count]);
  const attr = geometry.getAttribute("position") as THREE.BufferAttribute;
  base.forEach(([x, y, z, phase, speed], i) => {
    const rise = ((y + 2.5 + seconds * speed) % 7) - 2.5;               // drift up, wrap around
    attr.setXYZ(i, x + 0.25 * Math.sin(seconds * 0.4 + phase), rise, z + 0.2 * Math.cos(seconds * 0.3 + phase));
  });
  attr.needsUpdate = true;
  return (
    <points geometry={geometry} frustumCulled={false}>
      <pointsMaterial map={sprite} color={color} size={0.06} sizeAttenuation transparent opacity={0.55}
        depthWrite={false} blending={THREE.AdditiveBlending} />
    </points>
  );
};

function beamTexture(color: string): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 512;
  const g = c.getContext("2d")!;
  const v = g.createLinearGradient(0, 0, 0, 512);
  v.addColorStop(0, color);
  v.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = v;
  g.fillRect(0, 0, 256, 512);
  g.globalCompositeOperation = "destination-in";          // soft left/right edges
  const h = g.createLinearGradient(0, 0, 256, 0);
  h.addColorStop(0, "rgba(0,0,0,0)");
  h.addColorStop(0.5, "rgba(0,0,0,1)");
  h.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = h;
  g.fillRect(0, 0, 256, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export const LightBeam: React.FC<{ color: string; width: number; top: number; seconds: number }> = ({ color, width, top, seconds }) => {
  const tex = useMemo(() => beamTexture(color), [color]);
  const breathe = 0.85 + 0.15 * Math.sin(seconds * 0.8);
  return (
    <group position={[0, top, -1.4]}>
      {[-0.22, 0.18].map((tilt, i) => (
        <mesh key={i} rotation={[0, 0, tilt]} position={[tilt * 3, -2.6, i * -0.3]}>
          <planeGeometry args={[width, 7]} />
          <meshBasicMaterial map={tex} transparent opacity={0.16 * breathe} depthWrite={false}
            blending={THREE.AdditiveBlending} fog={false} />
        </mesh>
      ))}
    </group>
  );
};
