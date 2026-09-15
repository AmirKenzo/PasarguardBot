import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  radius: number;
}

export const SmokeyBackground = ({ className = "" }: { className?: string }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animationFrameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    const particles = particlesRef.current;

    const createParticle = () => {
      const x = Math.random() * canvas.width;
      const y = canvas.height + 50;
      const vx = (Math.random() - 0.5) * 2;
      const vy = -Math.random() * 2 - 1;
      const radius = Math.random() * 60 + 40;
      const maxLife = Math.random() * 2000 + 3000;

      particles.push({
        x,
        y,
        vx,
        vy,
        life: 0,
        maxLife,
        radius,
      });
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (Math.random() < 0.08) {
        createParticle();
      }

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]!;

        p.x += p.vx;
        p.y += p.vy;
        p.life += 16;

        const progress = p.life / p.maxLife;
        const alpha = Math.sin(progress * Math.PI) * 0.15;

        ctx.fillStyle = `rgba(59, 130, 246, ${alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        if (p.life >= p.maxLife) {
          particles.splice(i, 1);
        }
      }

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 ${className}`}
      style={{ background: "transparent" }}
    />
  );
};
