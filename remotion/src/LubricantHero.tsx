// 3D hero for industrial / lubricant topics, built only from simple shapes:
// a polished steel ball bearing (two races, balls, a brass cage) with a glossy amber
// lubricant drop above it and a few small droplets around. Studio lighting comes from
// Three.js's built-in RoomEnvironment, so there are no image or model files.
import { ContactShadows } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

// Studio reflections, set up while the scene is first built (not after), so even a single
// still frame already has them; without them polished metal renders almost black
const Studio: React.FC = () => {
  const { gl, scene } = useThree();
  useMemo(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  }, [gl, scene]);
  return null;
};

// A ring with a rounded rectangular cross-section (a bearing race), made by spinning a profile
function raceGeometry(inner: number, outer: number, height: number): THREE.LatheGeometry {
  const r = 0.06;
  const pts: THREE.Vector2[] = [];
  const corner = (cx: number, cy: number, a0: number) => {
    for (let i = 0; i <= 6; i++) {
      const a = a0 + (i / 6) * (Math.PI / 2);
      pts.push(new THREE.Vector2(cx + r * Math.cos(a), cy + r * Math.sin(a)));
    }
  };
  const h = height / 2;
  corner(outer - r, -h + r, -Math.PI / 2);
  corner(outer - r, h - r, 0);
  corner(inner + r, h - r, Math.PI / 2);
  corner(inner + r, -h + r, Math.PI);
  pts.push(pts[0].clone());
  return new THREE.LatheGeometry(pts, 128);
}

// Teardrop: round at the bottom, pointed at the top
function dropGeometry(): THREE.LatheGeometry {
  const pts: THREE.Vector2[] = [];
  for (let i = 0; i <= 40; i++) {
    const t = i / 40;                        // 0 = bottom, 1 = tip
    const a = t * Math.PI;
    const radius = Math.sin(a) * (1 - 0.55 * t * t) + 0.0001;
    pts.push(new THREE.Vector2(radius * 0.55, -Math.cos(a) * 0.55 + Math.pow(t, 3) * 0.42));
  }
  return new THREE.LatheGeometry(pts, 96);
}

const steel = { color: "#e6ebf2", metalness: 0.9, roughness: 0.22, envMapIntensity: 1.6 };

export const LubricantHero: React.FC<{ width: number; height: number; accent: string }> = ({ width, height, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const outerRace = useMemo(() => raceGeometry(1.62, 2.05, 0.62), []);
  const innerRace = useMemo(() => raceGeometry(0.72, 1.08, 0.62), []);
  const drop = useMemo(() => dropGeometry(), []);
  const balls = 11;
  const spin = t * 0.5;

  return (
    <ThreeCanvas width={width} height={height} dpr={2}
      gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true, toneMapping: THREE.ACESFilmicToneMapping }}
      camera={{ fov: 28, position: [0, 2.6, 12.2], near: 0.1, far: 100 }}
      onCreated={({ camera }) => camera.lookAt(0, 0.3, 0)}
      style={{ position: "absolute", inset: 0 }}>
      <Studio />
      <ambientLight intensity={0.25} />
      <directionalLight position={[4, 6, 5]} intensity={2.2} />
      <pointLight position={[-3, 1, 3]} intensity={18} distance={12} color={accent} />

      {/* bearing, tilted towards the viewer */}
      <group position={[0, -0.35, 0]} rotation={[0.62, 0.25, -0.32]}>
        <mesh geometry={outerRace} rotation={[0, 0, 0]}>
          <meshStandardMaterial {...steel} />
        </mesh>
        <group rotation={[0, spin, 0]}>
          <mesh geometry={innerRace}>
            <meshStandardMaterial {...steel} roughness={0.12} />
          </mesh>
        </group>
        <group rotation={[0, spin * 0.45, 0]}>
          {Array.from({ length: balls }, (_, i) => {
            const a = (i / balls) * Math.PI * 2;
            return (
              <mesh key={i} position={[Math.cos(a) * 1.35, 0, Math.sin(a) * 1.35]}>
                <sphereGeometry args={[0.255, 48, 32]} />
                <meshStandardMaterial color="#f4f6fa" metalness={0.85} roughness={0.16} envMapIntensity={1.8} />
              </mesh>
            );
          })}
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[1.35, 0.05, 16, 128]} />
            <meshStandardMaterial color="#c8962e" metalness={1} roughness={0.3} />
          </mesh>
        </group>
        {/* a thin film of lubricant on the inner race */}
        <mesh position={[0, 0.315, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.78, 1.02, 96]} />
          <meshPhysicalMaterial color="#c97700" roughness={0.08} clearcoat={1} metalness={0} envMapIntensity={0.7} transparent opacity={0.6} />
        </mesh>
      </group>

      {/* the drop, hovering and bobbing gently */}
      <group position={[0.35, 2.05 + 0.06 * Math.sin(t * 1.6), 0.9]} rotation={[0, 0, -0.1]}>
        <mesh geometry={drop}>
          <meshPhysicalMaterial color="#c97700" roughness={0.06} metalness={0} clearcoat={1} clearcoatRoughness={0.02}
            emissive="#4a2500" emissiveIntensity={0.25} envMapIntensity={0.7} />
        </mesh>
      </group>
      {[[-1.9, 1.2, 0.4, 0.13], [2.0, 0.9, 0.2, 0.1], [-1.2, 2.3, -0.4, 0.08], [1.4, 2.25, 0.1, 0.07]].map(([x, y, z, r], i) => (
        <mesh key={i} position={[x, y + 0.05 * Math.sin(t * 1.3 + i), z]}>
          <sphereGeometry args={[r, 32, 24]} />
          <meshPhysicalMaterial color="#c97700" roughness={0.06} clearcoat={1} emissive="#4a2500" emissiveIntensity={0.25} envMapIntensity={0.7} />
        </mesh>
      ))}

      <ContactShadows position={[0, -1.85, 0]} opacity={0.38} scale={9} blur={2.6} far={3} color="#0B1B3F" frames={1} />
    </ThreeCanvas>
  );
};
