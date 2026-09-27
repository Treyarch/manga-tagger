<script lang="ts">
  import { onMount } from "svelte";
  import { flip } from "svelte/animate";
  import {
    motion, panelTransition, settleMotion, MOTION_DURATION, easeInOut,
  } from "../motion";
  import {
    Check,
    CircleAlert,
    FileArchive,
    ListOrdered,
    Pencil,
    RefreshCw,
    Save,
    ScanSearch,
  } from "lucide-svelte";
  import {
    dismissToast,
    subscribeToasts,
    type ToastIcon,
    type ToastItem,
  } from "../toast";

  let items = $state<ToastItem[]>([]);

  const icons: Record<ToastIcon, typeof Check> = {
    check: Check,
    save: Save,
    pencil: Pencil,
    fileArchive: FileArchive,
    scanSearch: ScanSearch,
    listOrdered: ListOrdered,
    refreshCw: RefreshCw,
    alert: CircleAlert,
  };

  onMount(() => subscribeToasts((next) => {
    items = next;
  }));
</script>

<!-- Host stays mounted so the first toast gets its enter transition. -->
<div
  class="pointer-events-none fixed top-16 left-1/2 z-40 flex w-full max-w-sm -translate-x-1/2 flex-col gap-2"
  role="status"
  aria-live="polite"
  aria-relevant="additions text"
>
  {#each items as item (item.id)}
    {@const Icon = icons[item.icon]}
    <button
      type="button"
      class="pointer-events-auto flex w-full items-start gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-3 text-left text-sm shadow-md dark:border-zinc-600 dark:bg-zinc-800 dark:shadow-lg dark:shadow-black/50 {item.tone ===
      'error'
        ? 'text-red-600 dark:text-red-400'
        : 'text-zinc-900 dark:text-zinc-100'}"
      use:settleMotion
      transition:panelTransition={{ y: -16, enabled: $motion }}
      animate:flip={{ duration: $motion ? MOTION_DURATION : 0, easing: easeInOut }}
      onclick={() => dismissToast(item.id)}
    >
      <span
        class="inline-flex mt-0.5 shrink-0"
        aria-hidden="true"
        use:settleMotion
        in:panelTransition|global={{ y: 0, enabled: $motion }}
      >
        <Icon size={16} />
      </span>
      <span class="min-w-0 flex-1">{item.message}</span>
    </button>
  {/each}
</div>
