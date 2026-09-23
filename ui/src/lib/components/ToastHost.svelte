<script lang="ts">
  import { onMount } from "svelte";
  import { fly } from "svelte/transition";
  import { backOut, cubicIn } from "svelte/easing";
  import {
    dismissToast,
    subscribeToasts,
    type ToastItem,
  } from "../toast";

  let items = $state<ToastItem[]>([]);

  onMount(() => subscribeToasts((next) => {
    items = next;
  }));
</script>

{#if items.length > 0}
  <div
    class="pointer-events-none fixed top-4 right-4 z-40 flex w-full max-w-sm flex-col gap-2"
    role="status"
    aria-live="polite"
    aria-relevant="additions text"
  >
    {#each items as item (item.id)}
      <button
        type="button"
        class="pointer-events-auto w-full rounded-lg border border-zinc-200 bg-white px-4 py-3 text-left text-sm shadow-md dark:border-zinc-600 dark:bg-zinc-800 dark:shadow-lg dark:shadow-black/50 {item.tone ===
        'error'
          ? 'text-red-600 dark:text-red-400'
          : 'text-zinc-900 dark:text-zinc-100'}"
        in:fly={{ y: -24, duration: 400, easing: backOut, opacity: 0 }}
        out:fly={{ y: -12, duration: 220, easing: cubicIn, opacity: 0 }}
        onclick={() => dismissToast(item.id)}
      >
        {item.message}
      </button>
    {/each}
  </div>
{/if}
