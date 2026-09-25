<script lang="ts">
  import type { Snippet } from "svelte";
  import { X } from "lucide-svelte";
  import { fly } from "svelte/transition";
  import { backOut, cubicIn } from "svelte/easing";
  import Button from "./Button.svelte";

  let {
    title,
    icon,
    size = "md",
    confirmLabel,
    confirmVariant = "primary",
    confirmDisabled = false,
    leadingLabel,
    leadingDisabled = false,
    onLeading,
    onDismiss,
    onConfirm,
    children,
  }: {
    title: string;
    icon?: Snippet;
    size?: "md" | "xl";
    confirmLabel?: string;
    confirmVariant?: "primary" | "danger";
    confirmDisabled?: boolean;
    leadingLabel?: string;
    leadingDisabled?: boolean;
    onLeading?: () => void;
    onDismiss: () => void;
    onConfirm?: () => void;
    children?: Snippet;
  } = $props();

  const width = $derived(size === "xl" ? "max-w-4xl" : "max-w-md");
</script>

<div
  class="fixed inset-0 z-30 flex items-center justify-center bg-zinc-900/40 p-4"
  role="presentation"
>
  <div
    class="w-full {width} rounded-lg border border-zinc-200 bg-white p-4 shadow-md dark:border-zinc-600 dark:bg-zinc-800 dark:shadow-lg dark:shadow-black/50"
    role="dialog"
    aria-modal="true"
    aria-labelledby="dialog-title"
    in:fly={{ y: 20, duration: 400, easing: backOut, opacity: 0 }}
    out:fly={{ y: 12, duration: 220, easing: cubicIn, opacity: 0 }}
  >
    <div class="flex items-center gap-2">
      <h2
        id="dialog-title"
        class="flex min-h-8 min-w-0 flex-1 items-center gap-2 text-base font-bold leading-none text-zinc-900 dark:text-zinc-100"
      >
        {#if icon}
          <span class="inline-flex shrink-0" aria-hidden="true">{@render icon()}</span>
        {/if}
        {title}
      </h2>
      <Button icon label="Close" onclick={onDismiss}>
        <X size={20} />
      </Button>
    </div>
    <div class="mt-3">
      {@render children?.()}
    </div>
    <div class="mt-4 flex justify-end gap-2">
      {#if leadingLabel !== undefined && onLeading}
        <Button variant="quiet" disabled={leadingDisabled} onclick={onLeading}
          >{leadingLabel}</Button
        >
      {/if}
      <Button variant="quiet" onclick={onDismiss}>Cancel</Button>
      {#if confirmLabel !== undefined && onConfirm}
        <Button
          variant={confirmVariant}
          disabled={confirmDisabled}
          onclick={onConfirm}>{confirmLabel}</Button
        >
      {/if}
    </div>
  </div>
</div>
