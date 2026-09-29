<script lang="ts">
  import { onMount } from "svelte";
  import type { Snippet } from "svelte";

  let {
    x,
    y,
    items,
    label = "Actions",
    icon,
    onSelect,
    onDismiss,
  }: {
    x: number;
    y: number;
    items: { id: string; label: string; disabled?: boolean }[];
    label?: string;
    icon: Snippet<[string]>;
    onSelect: (id: string) => void;
    onDismiss: () => void;
  } = $props();

  let panel: HTMLDivElement;
  let left = $state(0);
  let top = $state(0);

  function enabledButtons(): HTMLButtonElement[] {
    return Array.from(
      panel.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
    );
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      onDismiss();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const buttons = enabledButtons();
    if (buttons.length === 0) return;
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const direction = event.key === "ArrowDown" ? 1 : -1;
    const next = current < 0 ? 0 : (current + direction + buttons.length) % buttons.length;
    buttons[next].focus();
  }

  onMount(() => {
    const bounds = panel.getBoundingClientRect();
    left = Math.max(8, Math.min(x, window.innerWidth - bounds.width - 8));
    top = Math.max(8, Math.min(y, window.innerHeight - bounds.height - 8));
    enabledButtons()[0]?.focus();

    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !panel.contains(event.target)) onDismiss();
    };
    const dismiss = () => onDismiss();
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("scroll", dismiss, true);
    window.addEventListener("resize", dismiss);
    window.addEventListener("blur", dismiss);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("scroll", dismiss, true);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("blur", dismiss);
    };
  });
</script>

<div
  bind:this={panel}
  class="fixed z-20 min-w-44 rounded-md border border-app-border bg-app-view py-1 shadow-md"
  style="left: {left}px; top: {top}px"
  role="menu"
  aria-label={label}
  tabindex="-1"
  onkeydown={onKeydown}
>
  {#each items as item (item.id)}
    <button
      type="button"
      role="menuitem"
      disabled={item.disabled}
      class="flex h-9 w-full items-center gap-2 px-2 text-left text-sm text-app-text hover:bg-app-selection focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed disabled:opacity-50"
      onclick={() => onSelect(item.id)}
    >
      {@render icon(item.id)}
      <span class="flex-1">{item.label}</span>
    </button>
  {/each}
</div>
