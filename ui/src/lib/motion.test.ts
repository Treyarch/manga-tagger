import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";
import {
  createContentMotion, createMotionPreferences, easeInOut, motion,
  panelTransition, releaseAfterMotion, resolveMotion, settleMotion,
  smoothHeight, watchReducedMotion,
} from "./motion";

class FakeAnimation {
  onfinish: (() => void) | null = null;
  cancel = vi.fn();
  finish = vi.fn(() => this.onfinish?.());
}

class FakeElement {
  height = 100;
  inert = false;
  attributes = new Map<string, string>();
  style: Record<string, any> = { removeProperty: vi.fn((key) => delete this.style[key]) };
  children: FakeElement[] = [];
  firstElementChild: FakeElement | null = null;
  animations: FakeAnimation[] = [];
  removed = false;
  animate = vi.fn((_frames: unknown, _options: unknown) => {
    const animation = new FakeAnimation();
    this.animations.push(animation);
    return animation;
  });
  getBoundingClientRect() { return { height: this.height }; }
  getAnimations() { return this.animations; }
  cloneNode() { return new FakeElement(); }
  setAttribute(name: string, value: string) { this.attributes.set(name, value); }
  removeAttribute(name: string) { this.attributes.delete(name); }
  querySelectorAll() { return []; }
  append(child: FakeElement) { this.children.push(child); }
  remove() { this.removed = true; }
}

let resize: () => void;
let disconnect: ReturnType<typeof vi.fn>;
function fixture() {
  const node = new FakeElement();
  const content = new FakeElement();
  node.firstElementChild = content;
  return { node, content, element: node as unknown as HTMLElement };
}

beforeEach(() => {
  motion.clearPreview();
  motion.setReduced(false);
  motion.setSaved(false);
  disconnect = vi.fn();
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback: () => void) { resize = callback; }
    observe = vi.fn();
    disconnect = disconnect;
  });
  vi.stubGlobal("getComputedStyle", () => ({ opacity: "1", transform: "none" }));
});

afterEach(() => {
  motion.setSaved(false);
  motion.clearPreview();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("motion preferences", () => {
  it("resolves all saved, preview, and reduced-motion combinations", () => {
    for (const saved of [false, true]) {
      for (const preview of [null, false, true]) {
        expect(resolveMotion(saved, preview, true)).toBe(false);
        expect(resolveMotion(saved, preview, false)).toBe(preview ?? saved);
      }
    }
  });

  it("previews both directions, rolls back, and commits the saved value", () => {
    const preferences = createMotionPreferences();
    preferences.preview(true);
    expect(get(preferences)).toBe(true);
    preferences.clearPreview();
    expect(get(preferences)).toBe(false);
    preferences.preview(true);
    preferences.setSaved(true);
    preferences.clearPreview();
    expect(get(preferences)).toBe(true);
    preferences.preview(false);
    expect(get(preferences)).toBe(false);
    preferences.clearPreview();
    expect(get(preferences)).toBe(true);
  });

  it("reacts to system changes without losing the saved preference and detaches", () => {
    let listener: () => void = () => {};
    const query = {
      matches: true,
      addEventListener: vi.fn((_event, callback) => { listener = callback; }),
      removeEventListener: vi.fn(),
    };
    motion.setSaved(true);
    const stop = watchReducedMotion(query as unknown as MediaQueryList);
    expect(get(motion)).toBe(false);
    query.matches = false;
    listener();
    expect(get(motion)).toBe(true);
    stop();
    expect(query.removeEventListener).toHaveBeenCalledWith("change", listener);
  });
});

describe("transitions", () => {
  it("uses an exact endpoint and symmetric ease-in-out curve", () => {
    expect(easeInOut(0)).toBe(0);
    expect(easeInOut(1)).toBe(1);
    expect(easeInOut(0.5)).toBeCloseTo(0.5, 4);
    expect(easeInOut(0.2)).toBeLessThan(0.2);
    expect(easeInOut(0.8)).toBeCloseTo(1 - easeInOut(0.2), 4);
  });

  it("disables transitions and immediately finishes active Svelte animations", () => {
    const { element, node } = fixture();
    expect(panelTransition(element).duration).toBe(0);
    motion.setSaved(true);
    expect(panelTransition(element).duration).toBe(250);
    const animation = node.animate([], {});
    const action = settleMotion(element);
    motion.setReduced(true);
    expect(animation.finish).toHaveBeenCalledOnce();
    action.destroy();
  });

  it("keeps preview resources until their outgoing visual is finished", () => {
    vi.useFakeTimers();
    motion.setSaved(true);
    const release = vi.fn();
    releaseAfterMotion(release);
    vi.advanceTimersByTime(250);
    expect(release).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(release).toHaveBeenCalledOnce();
    const next = vi.fn();
    releaseAfterMotion(next);
    motion.setReduced(true);
    expect(next).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("measured height", () => {
  it("leaves initial layout natural and animates growth and shrinkage", () => {
    motion.setSaved(true);
    const { element, node, content } = fixture();
    const action = smoothHeight(element);
    resize();
    expect(node.animate).not.toHaveBeenCalled();
    content.height = 300;
    resize();
    expect(node.animate).toHaveBeenLastCalledWith([{ height: "100px" }, { height: "300px" }], { duration: 250, easing: "ease-in-out" });
    node.height = 175;
    content.height = 80;
    resize();
    expect(node.animations[0].cancel).toHaveBeenCalledOnce();
    expect(node.animate).toHaveBeenLastCalledWith([{ height: "175px" }, { height: "80px" }], { duration: 250, easing: "ease-in-out" });
    node.animations[1].finish();
    expect(node.style.height).toBeUndefined();
    expect(node.style.overflow).toBeUndefined();
    action.destroy();
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it("settles on disable, tracks natural sizes while off, and cleans up mid-animation", () => {
    const { element, node, content } = fixture();
    const action = smoothHeight(element);
    content.height = 200;
    resize();
    expect(node.animate).not.toHaveBeenCalled();
    motion.setSaved(true);
    content.height = 300;
    resize();
    motion.preview(false);
    expect(node.animations[0].cancel).toHaveBeenCalled();
    expect(node.style.height).toBeUndefined();
    motion.clearPreview();
    content.height = 400;
    resize();
    action.destroy();
    expect(node.animations[1].cancel).toHaveBeenCalled();
    expect(node.style.height).toBeUndefined();
  });
});

describe("content replacement", () => {
  it("crossfades an inert out-of-flow visual while keeping live content mounted", () => {
    motion.setSaved(true);
    const { element, node, content } = fixture();
    const controller = createContentMotion(element);
    controller.prepare(-12);
    controller.play();
    const outgoing = node.children[0];
    expect(outgoing.inert).toBe(true);
    expect(outgoing.attributes.get("aria-hidden")).toBe("true");
    expect(outgoing.style.position).toBe("absolute");
    expect(content.animate.mock.calls[0][0]).toEqual([
      { opacity: 0, transform: "translateY(-12px)" },
      { opacity: 1, transform: "translateY(0)" },
    ]);
    content.animations[0].finish();
    expect(outgoing.removed).toBe(true);
    expect(node.firstElementChild).toBe(content);
    controller.destroy();
  });

  it("replaces interrupted effects, settles immediately when disabled, and disposes", () => {
    motion.setSaved(true);
    const { element, node, content } = fixture();
    const controller = createContentMotion(element);
    controller.prepare(12);
    controller.play();
    controller.prepare(-12);
    expect(content.animations[0].cancel).toHaveBeenCalledOnce();
    expect(node.children[0].removed).toBe(true);
    controller.play();
    motion.setReduced(true);
    expect(node.children[1].removed).toBe(true);
    expect(content.animations[1].cancel).toHaveBeenCalledOnce();
    controller.prepare(12);
    controller.play();
    expect(content.animate).toHaveBeenCalledTimes(2);
    controller.destroy();
  });
});
