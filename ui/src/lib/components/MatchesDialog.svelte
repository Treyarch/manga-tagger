<script lang="ts">
  import { LoaderCircle, ScanSearch } from "lucide-svelte";
  import Dialog from "./Dialog.svelte";
  import type { Candidate } from "../library";

  let {
    candidates,
    searching,
    busy,
    onDismiss,
    onCandidate,
  }: {
    candidates: Candidate[];
    searching: boolean;
    busy: boolean;
    onDismiss: () => void;
    onCandidate: (id: string) => void;
  } = $props();
</script>

<Dialog title="Matches" {onDismiss}>
  {#snippet icon()}
    <ScanSearch size={20} />
  {/snippet}
  {#if searching}
    <div
      class="flex items-center justify-center gap-2 py-8 text-sm text-zinc-500 dark:text-zinc-400"
      aria-busy="true"
      role="status"
    >
      <LoaderCircle size={20} class="animate-spin" aria-hidden="true" />
      <span>Searching…</span>
    </div>
  {:else}
    <ul class="max-h-80 overflow-y-auto">
      {#each candidates as candidate (candidate.id)}
        <li>
          <button
            type="button"
            class="w-full rounded-md px-2 py-1 text-left hover:bg-blue-600/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:opacity-40 dark:hover:bg-blue-500/15 dark:focus-visible:ring-blue-500"
            disabled={busy}
            onclick={() => onCandidate(candidate.id)}
          >
            <span class="block text-sm text-zinc-900 dark:text-zinc-100"
              >{candidate.title}</span
            >
            {#if candidate.detail.trim() !== ""}
              <span class="block text-xs text-zinc-500 dark:text-zinc-400"
                >{candidate.detail}</span
              >
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</Dialog>
