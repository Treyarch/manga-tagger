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
  class="absolute top-full right-0 z-20 mt-1 min-w-40 rounded-md border border-app-border bg-app-view py-1 shadow-md"
  role="menu"
>
  {#each items as item (item.id)}
    <button
      type="button"
      role="menuitem"
      class="flex h-9 w-full items-center gap-2 px-2 text-left text-sm text-app-text hover:bg-app-selection focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent"
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
