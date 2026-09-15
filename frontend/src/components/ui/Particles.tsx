import { useEffect, useRef } from "react";

export interface ParticlesProps {
  className?: string;
  quantity?: number;
  size?: number;
  /** "R G B" triplet, e.g. "109 92 246". Defaults to the theme's --c-primary-rgb. */
  color?: string;
}

interface Dot {
  x: number;
  y: number;
  r: number;
  dx: number;
  dy: number;
  alpha: number;
}

/** Magic UI's Particles, reworked as a lightweight ambient drift (no mouse-magnetism) to stay cheap on mobile. */
export function Particles({ className = "", quantity = 40, size = 1.6, color }: ParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const rgb = color ?? (getComputedStyle(document.documentElement).getPropertyValue("--c-primary-rgb").trim() || "109 92 246");
    const rgba = rgb.trim().split(/\s+/).join(", ");

    const dpr = window.devicePixelRatio || 1;
    let width = 0;
    let height = 0;
    let dots: Dot[] = [];
    let frame = 0;

    function makeDot(): Dot {
      return {
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * size + 0.4,
        dx: (Math.random() - 0.5) * 0.15,
        dy: (Math.random() - 0.5) * 0.15,
        alpha: Math.random() * 0.5 + 0.15,
      };
    }

    function resize() {
      const parent = canvas!.parentElement;
      width = parent?.clientWidth ?? window.innerWidth;
      height = parent?.clientHeight ?? window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      dots = Array.from({ length: quantity }, makeDot);
    }

    function draw() {
      ctx!.clearRect(0, 0, width, height);
      for (const dot of dots) {
        dot.x += dot.dx;
        dot.y += dot.dy;
        if (dot.x < 0) dot.x = width;
        if (dot.x > width) dot.x = 0;
        if (dot.y < 0) dot.y = height;
        if (dot.y > height) dot.y = 0;
        ctx!.beginPath();
        ctx!.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(${rgba}, ${dot.alpha})`;
        ctx!.fill();
      }
      frame = requestAnimationFrame(draw);
    }

    resize();
    draw();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [quantity, size, color]);

  return <canvas ref={canvasRef} className={`pointer-events-none absolute inset-0 ${className}`} />;
}
