<script lang="ts">
  import type { Snippet } from "svelte";
  import { fly } from "svelte/transition";
  import { backOut, cubicIn } from "svelte/easing";
  import Button from "./Button.svelte";

  let {
    title,
    confirmLabel,
    confirmVariant = "primary",
    onDismiss,
    onConfirm,
    children,
  }: {
    title: string;
    confirmLabel?: string;
    confirmVariant?: "primary" | "danger";
    onDismiss: () => void;
    onConfirm?: () => void;
    children?: Snippet;
  } = $props();
</script>

<div
  class="fixed inset-0 z-30 flex items-center justify-center bg-zinc-900/40 p-4"
  role="presentation"
>
  <div
    class="w-full max-w-md rounded-lg border border-zinc-200 bg-white p-4 shadow-md dark:border-zinc-600 dark:bg-zinc-800 dark:shadow-lg dark:shadow-black/50"
    role="dialog"
    aria-modal="true"
    aria-labelledby="dialog-title"
    in:fly={{ y: 20, duration: 400, easing: backOut, opacity: 0 }}
    out:fly={{ y: 12, duration: 220, easing: cubicIn, opacity: 0 }}
  >
    <h2 id="dialog-title" class="text-sm font-medium text-zinc-900 dark:text-zinc-100">
      {title}
    </h2>
    <div class="mt-3">
      {@render children?.()}
    </div>
    <div class="mt-4 flex justify-end gap-2">
      <Button variant="quiet" onclick={onDismiss}>Cancel</Button>
      {#if confirmLabel !== undefined && onConfirm}
        <Button variant={confirmVariant} onclick={onConfirm}>{confirmLabel}</Button>
      {/if}
    </div>
  </div>
</div>
