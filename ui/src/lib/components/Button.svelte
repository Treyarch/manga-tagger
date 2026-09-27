<script lang="ts">
  import type { Snippet } from "svelte";

  type Variant = "primary" | "secondary" | "quiet" | "danger";

  let {
    variant = "quiet",
    icon = false,
    pressed = false,
    type = "button",
    disabled = false,
    label = undefined,
    tooltip = undefined,
    onclick,
    children,
  }: {
    variant?: Variant;
    icon?: boolean;
    pressed?: boolean;
    type?: "button" | "submit";
    disabled?: boolean;
    label?: string;
    tooltip?: string;
    onclick?: (event: MouseEvent) => void;
    children?: Snippet;
  } = $props();

  const look = $derived(
    variant === "primary"
      ? "bg-app-accent text-app-on-accent"
      : variant === "danger"
        ? "bg-app-danger text-app-on-danger hover:bg-app-danger-hover"
        : variant === "secondary"
          ? "border border-app-strong-border bg-app-secondary text-app-text hover:bg-app-secondary-hover"
          : pressed
            ? "bg-app-selection text-app-text"
            : "bg-transparent text-app-text hover:bg-app-quiet-hover",
  );
</script>

<button
  {type}
  {disabled}
  aria-label={label}
  title={tooltip ?? label}
  aria-pressed={pressed ? true : undefined}
  class="inline-flex cursor-pointer items-center justify-center rounded-md text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed disabled:opacity-40 {icon
    ? 'size-8'
    : 'h-9 px-3'} {look}"
  {onclick}
>
  {@render children?.()}
</button>
