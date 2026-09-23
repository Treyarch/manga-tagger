<script lang="ts">
  import { Book, LoaderCircle, ScanSearch } from "lucide-svelte";
  import Dialog from "./Dialog.svelte";
  import type { Candidate } from "../library";
  import { matchCoverSrc } from "../library";

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

  let failedCovers = $state(new Set<string>());

  function coverFailed(url: string): boolean {
    return failedCovers.has(url);
  }

  function markCoverFailed(url: string): void {
    if (failedCovers.has(url)) return;
    const next = new Set(failedCovers);
    next.add(url);
    failedCovers = next;
  }
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
    <ul
      class="max-h-80 divide-y divide-zinc-200 overflow-y-auto dark:divide-zinc-700"
    >
      {#each candidates as candidate (candidate.id)}
        <li>
          <button
            type="button"
            class="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-blue-600/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:opacity-40 dark:hover:bg-blue-500/15 dark:focus-visible:ring-blue-500"
            disabled={busy}
            onclick={() => onCandidate(candidate.id)}
          >
            <span
              class="flex h-[60px] w-10 shrink-0 items-center justify-center overflow-hidden rounded-sm bg-zinc-100 text-zinc-400 dark:bg-zinc-700 dark:text-zinc-500"
              aria-hidden="true"
            >
              {#if candidate.cover.trim() !== "" && !coverFailed(candidate.cover)}
                <img
                  src={matchCoverSrc(candidate.cover)}
                  alt=""
                  referrerpolicy="no-referrer"
                  class="h-full w-full object-cover"
                  onerror={() => markCoverFailed(candidate.cover)}
                />
              {:else}
                <Book size={16} />
              {/if}
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm text-zinc-900 dark:text-zinc-100"
                >{candidate.title}</span
              >
              {#if candidate.detail.trim() !== ""}
                <span class="block truncate text-xs text-zinc-500 dark:text-zinc-400"
                  >{candidate.detail}</span
                >
              {/if}
            </span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</Dialog>
