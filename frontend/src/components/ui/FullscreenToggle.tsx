import { Maximize, Minimize } from "lucide-react";
import { motion } from "framer-motion";
import { useTelegramFullscreen } from "../../hooks/useTelegramViewportFix";

export function FullscreenToggle() {
  const { isFullscreen, toggle, supported } = useTelegramFullscreen();
  if (!supported) return null;

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={toggle}
      className="flex items-center justify-center rounded-lg bg-primary/10 p-2.5 text-primary transition-colors hover:bg-primary/20"
      title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
    >
      {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
    </motion.button>
  );
}
