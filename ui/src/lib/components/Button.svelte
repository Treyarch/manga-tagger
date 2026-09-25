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
    onclick,
    children,
  }: {
    variant?: Variant;
    icon?: boolean;
    pressed?: boolean;
    type?: "button" | "submit";
    disabled?: boolean;
    label?: string;
    onclick?: (event: MouseEvent) => void;
    children?: Snippet;
  } = $props();

  const look = $derived(
    variant === "primary"
      ? "bg-blue-600 text-white dark:bg-blue-500"
      : variant === "danger"
        ? "bg-red-600 text-white hover:bg-red-700"
        : variant === "secondary"
          ? "border border-zinc-200 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-600"
          : pressed
            ? "bg-blue-600/10 text-zinc-900 dark:bg-blue-500/15 dark:text-zinc-100"
            : "bg-transparent text-zinc-900 hover:bg-zinc-200/70 dark:text-zinc-100 dark:hover:bg-zinc-800",
  );
</script>

<button
  {type}
  {disabled}
  aria-label={label}
  title={label}
  aria-pressed={pressed ? true : undefined}
  class="inline-flex cursor-pointer items-center justify-center rounded-md text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:cursor-not-allowed disabled:opacity-40 dark:focus-visible:ring-blue-500 {icon
    ? 'size-8'
    : 'h-9 px-3'} {look}"
  {onclick}
>
  {@render children?.()}
</button>
