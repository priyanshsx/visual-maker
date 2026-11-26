// Camera-lens effects on the 3D layer: glow around bright things (bloom) and a hint of
// colour fringing towards the edges, like a real lens. Text is HTML on top and stays sharp.
// Uses Three.js's own post-processing with an explicit size, so it renders the same in
// Remotion Studio, in a headless render and on any GPU.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";

// Chromatic aberration: red and blue split slightly, more towards the corners
const LensFringe = {
  uniforms: { tDiffuse: { value: null }, amount: { value: 0.0016 } },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform float amount; varying vec2 vUv;
    void main() {
      vec2 d = (vUv - 0.5) * amount * length(vUv - 0.5) * 2.0;
      vec4 c = texture2D(tDiffuse, vUv);
      gl_FragColor = vec4(texture2D(tDiffuse, vUv + d).r, c.g, texture2D(tDiffuse, vUv - d).b, c.a);
    }`,
};

export const LensEffects: React.FC<{ width: number; height: number; bloom?: number }> = ({ width, height, bloom = 0.75 }) => {
  const { gl, scene, camera } = useThree();
  const composer = useMemo(() => {
    const c = new EffectComposer(gl);
    c.addPass(new RenderPass(scene, camera));
    c.addPass(new UnrealBloomPass(new THREE.Vector2(width, height), bloom, 0.4, 0.62));
    c.addPass(new ShaderPass(LensFringe));
    c.addPass(new OutputPass());
    return c;
  }, [gl, scene, camera, width, height, bloom]);
  useEffect(() => {
    composer.setPixelRatio(gl.getPixelRatio());
    composer.setSize(width, height);
    return () => composer.dispose();
  }, [composer, gl, width, height]);
  useFrame(() => composer.render(), 1);     // priority 1: replaces the normal render
  return null;
};
