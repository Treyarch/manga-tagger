<script lang="ts">
  import { Check } from "lucide-svelte";
  import type { Snippet } from "svelte";

  let {
    items,
    icon,
    onSelect,
  }: {
    items: { id: string; label: string; checked: boolean }[];
    icon: Snippet<[string]>;
    onSelect: (id: string) => void;
  } = $props();
</script>

<div
  class="absolute top-full right-0 z-20 mt-1 min-w-40 rounded-md border border-zinc-200 bg-white py-1 shadow-md dark:border-zinc-800 dark:bg-zinc-900"
  role="menu"
>
  {#each items as item (item.id)}
    <button
      type="button"
      role="menuitem"
      class="flex h-9 w-full items-center gap-2 px-2 text-left text-sm text-zinc-900 hover:bg-blue-600/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-zinc-100 dark:hover:bg-blue-500/15 dark:focus-visible:ring-blue-500"
      onclick={() => onSelect(item.id)}
    >
      {@render icon(item.id)}
      <span class="flex-1">{item.label}</span>
      {#if item.checked}
        <Check size={16} />
      {/if}
    </button>
  {/each}
</div>
