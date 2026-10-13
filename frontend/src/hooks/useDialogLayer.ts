import { useEffect, useRef } from "react";

const layerStack: symbol[] = [];
let savedBodyOverflow = "";

export function useDialogLayer(open: boolean, onClose: () => void): void {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const layer = Symbol("dialog-layer");
    if (layerStack.length === 0) {
      savedBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    layerStack.push(layer);

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || layerStack[layerStack.length - 1] !== layer) return;
      event.stopPropagation();
      onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("keydown", onKey);
      const index = layerStack.indexOf(layer);
      if (index !== -1) layerStack.splice(index, 1);
      if (layerStack.length === 0) document.body.style.overflow = savedBodyOverflow;
    };
  }, [open]);
}
