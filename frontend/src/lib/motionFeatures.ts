import { domMax } from "framer-motion";

// Loaded lazily by <LazyMotion> in main.tsx so the animation/layout/drag
// feature code stays out of the first-paint bundle. domMax (not
// domAnimation) is required because the app uses layoutId and drag.
export default domMax;
