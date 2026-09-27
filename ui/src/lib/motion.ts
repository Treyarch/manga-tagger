import { get, writable } from "svelte/store";

export const MOTION_DURATION = 250;
export const MOTION_EASING = "ease-in-out";

export function resolveMotion(saved: boolean, preview: boolean | null, reduced: boolean) {
  return (preview ?? saved) && !reduced;
}

/** A preview never changes the persisted preference, including on failed saves. */
export function createMotionPreferences() {
  let saved = false;
  let preview: boolean | null = null;
  let reduced = false;
  const state = writable(false);
  const publish = () => state.set(resolveMotion(saved, preview, reduced));
  return {
    subscribe: state.subscribe,
    setSaved(value: boolean) { saved = value; publish(); },
    preview(value: boolean) { preview = value; publish(); },
    clearPreview() { preview = null; publish(); },
    setReduced(value: boolean) { reduced = value; publish(); },
  };
}

export const motion = createMotionPreferences();

/** Let outgoing preview snapshots finish using their blob before releasing it. */
export function releaseAfterMotion(release: () => void) {
  if (!get(motion)) { release(); return; }
  // Start after Svelte's DOM flush, with a frame margin for the first paint.
  const timer = setTimeout(done, MOTION_DURATION + 50);
  const unsubscribe = motion.subscribe((enabled) => { if (!enabled) done(); });
  function done() { clearTimeout(timer); unsubscribe(); release(); }
}

export function watchReducedMotion(query: MediaQueryList) {
  const apply = () => motion.setReduced(query.matches);
  apply();
  query.addEventListener("change", apply);
  return () => query.removeEventListener("change", apply);
}

/** CSS's ease-in-out cubic Bezier, used by Svelte's sampled transitions. */
export function easeInOut(t: number): number {
  if (t <= 0 || t >= 1) return t;
  let low = 0, high = 1, u = t;
  for (let i = 0; i < 18; i++) {
    const x = 3 * (1 - u) ** 2 * u * 0.42 + 3 * (1 - u) * u ** 2 * 0.58 + u ** 3;
    if (x < t) low = u;
    else high = u;
    u = (low + high) / 2;
  }
  return 3 * (1 - u) * u ** 2 + u ** 3;
}

export function panelTransition(node: HTMLElement, { y = 16, enabled = get(motion) } = {}) {
  const transform = getComputedStyle(node).transform.replace("none", "");
  return {
    duration: enabled ? MOTION_DURATION : 0,
    easing: easeInOut,
    css: (t: number) => `opacity: ${t}; transform: ${transform} translateY(${(1 - t) * y}px)`,
  };
}

/** Svelte transitions use WAAPI; finish them as well as CSS effects when disabled. */
export function settleMotion(node: HTMLElement) {
  const unsubscribe = motion.subscribe((enabled) => {
    if (!enabled) {
      for (const animation of node.getAnimations()) animation.finish();
    }
  });
  return { destroy: unsubscribe };
}

/** Observe natural content, animate its enclosing viewport, and never scale text. */
export function smoothHeight(node: HTMLElement) {
  const content = node.firstElementChild as HTMLElement;
  let previous = content.getBoundingClientRect().height;
  let animation: Animation | undefined;
  const reset = () => {
    if (animation) {
      animation.onfinish = null;
      animation.cancel();
      animation = undefined;
    }
    node.style.removeProperty("height");
    node.style.removeProperty("overflow");
  };
  const unsubscribe = motion.subscribe((enabled) => { if (!enabled) reset(); });
  const observer = new ResizeObserver(() => {
    const next = content.getBoundingClientRect().height;
    if (Math.abs(next - previous) < 0.5) return;
    const from = animation ? node.getBoundingClientRect().height : previous;
    previous = next;
    reset();
    if (!get(motion)) return;
    node.style.height = `${next}px`;
    node.style.overflow = "clip";
    animation = node.animate([{ height: `${from}px` }, { height: `${next}px` }], {
      duration: MOTION_DURATION, easing: MOTION_EASING,
    });
    animation.onfinish = reset;
  });
  observer.observe(content);
  return { destroy() { unsubscribe(); observer.disconnect(); reset(); } };
}

/** A visual-only outgoing snapshot avoids remounting forms or repeating fetches. */
export function createContentMotion(node: HTMLElement) {
  const content = node.firstElementChild as HTMLElement;
  let outgoing: HTMLElement | undefined;
  let animations: Animation[] = [];
  let direction = 0;
  let startOpacity = "1";
  let startTransform = "none";
  const reset = () => {
    for (const animation of animations) { animation.onfinish = null; animation.cancel(); }
    animations = [];
    outgoing?.remove();
    outgoing = undefined;
  };
  const unsubscribe = motion.subscribe((enabled) => { if (!enabled) reset(); });
  return {
    prepare(y: number) {
      const style = getComputedStyle(content);
      startOpacity = style.opacity;
      startTransform = style.transform;
      reset();
      if (!get(motion)) return;
      direction = y;
      outgoing = content.cloneNode(true) as HTMLElement;
      outgoing.inert = true;
      outgoing.setAttribute("aria-hidden", "true");
      outgoing.removeAttribute("id");
      outgoing.querySelectorAll("[id]").forEach((item) => item.removeAttribute("id"));
      // cloneNode does not copy current textarea/select values.
      const originals = content.querySelectorAll<HTMLInputElement>("input, textarea, select");
      outgoing.querySelectorAll<HTMLInputElement>("input, textarea, select").forEach((item, i) => {
        item.value = originals[i].value;
        if (item.type === "checkbox") item.checked = originals[i].checked;
      });
      Object.assign(outgoing.style, {
        position: "absolute", top: "0", left: "0", width: "100%",
        pointerEvents: "none", opacity: startOpacity, transform: startTransform,
      });
      node.append(outgoing);
    },
    play() {
      if (!outgoing || !get(motion)) return;
      const options = { duration: MOTION_DURATION, easing: MOTION_EASING };
      animations = [
        outgoing.animate([
          { opacity: startOpacity, transform: startTransform },
          { opacity: 0, transform: `translateY(${-direction}px)` },
        ], options),
        content.animate([
          { opacity: 0, transform: `translateY(${direction}px)` },
          { opacity: 1, transform: "translateY(0)" },
        ], options),
      ];
      animations[1].onfinish = reset;
    },
    destroy() { unsubscribe(); reset(); },
  };
}
