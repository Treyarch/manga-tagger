<script lang="ts">
  import Dialog from "./Dialog.svelte";
  import type { Candidate } from "../library";

  let {
    candidates,
    busy,
    onDismiss,
    onCandidate,
  }: {
    candidates: Candidate[];
    busy: boolean;
    onDismiss: () => void;
    onCandidate: (id: string) => void;
  } = $props();
</script>

<Dialog title="Matches" {onDismiss}>
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
</Dialog>
