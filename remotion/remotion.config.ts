// Remotion settings used by "npx remotion studio" and "npx remotion render".
// visual-maker's Python CLI passes its own flags (props, size, GL backend) on top of these.
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png");     // lossless frames before encoding: crisp text and UI
Config.setCodec("h264");
Config.setCrf(18);
Config.setPixelFormat("yuv420p");      // plays everywhere (LinkedIn, X, QuickTime)
Config.setChromiumOpenGlRenderer("angle");   // WebGL for the 3D scenes (Python overrides on Linux)
