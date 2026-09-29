<script lang="ts">
  import { FolderPlus, X } from "lucide-svelte";
  import Button from "./Button.svelte";

  let {
    label,
    addLabel,
    paths,
    emptyText,
    browseDisabled = false,
    onBrowse,
    onRemove,
  }: {
    label: string;
    addLabel: string;
    paths: readonly string[];
    emptyText: string;
    browseDisabled?: boolean;
    onBrowse: () => void;
    onRemove: (path: string) => void;
  } = $props();
</script>

<section class="flex flex-col gap-1">
  <div class="flex items-center justify-between gap-3">
    <h3 class="text-xs text-app-muted">{label}</h3>
    <Button
      icon
      label={addLabel}
      disabled={browseDisabled}
      onclick={onBrowse}
    >
      <FolderPlus size={16} />
    </Button>
  </div>
  <div class="overflow-hidden rounded-md border border-app-border bg-app-view">
    {#if paths.length === 0}
      <p class="flex min-h-10 items-center px-2 text-sm text-app-muted">
        {emptyText}
      </p>
    {:else}
      <ul class="max-h-40 divide-y divide-app-border overflow-y-auto">
        {#each paths as path (path)}
          <li class="flex min-h-10 items-center gap-2 px-2">
            <span class="min-w-0 flex-1 truncate text-sm text-app-text" title={path}>
              {path}
            </span>
            <Button
              icon
              label="Remove {path}"
              onclick={() => onRemove(path)}
            >
              <X size={16} />
            </Button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</section>
