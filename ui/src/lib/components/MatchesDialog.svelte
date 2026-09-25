<script lang="ts">
  import { Book, LoaderCircle, ScanSearch } from "lucide-svelte";
  import Dialog from "./Dialog.svelte";
  import type { Candidate } from "../library";
  import { matchCoverSrc } from "../library";

  let {
    candidates,
    searching,
    busy,
    provider,
    selectIssueEnabled = true,
    onDismiss,
    onCandidate,
    onSelectIssue,
  }: {
    candidates: Candidate[];
    searching: boolean;
    busy: boolean;
    provider: string;
    selectIssueEnabled?: boolean;
    onDismiss: () => void;
    onCandidate: (id: string) => void;
    onSelectIssue: (id: string) => void;
  } = $props();

  let selectedId = $state("");
  let failedCovers = $state(new Set<string>());

  const creditHeading = $derived(
    provider === "comicvine" ? "Publisher" : "Author",
  );
  const selected = $derived(
    candidates.find((item) => item.id === selectedId) ?? candidates[0] ?? null,
  );

  $effect(() => {
    if (searching || candidates.length === 0) {
      selectedId = "";
      return;
    }
    if (!candidates.some((item) => item.id === selectedId)) {
      selectedId = candidates[0].id;
    }
  });

  function coverFailed(url: string): boolean {
    return failedCovers.has(url);
  }

  function markCoverFailed(url: string): void {
    if (failedCovers.has(url)) return;
    const next = new Set(failedCovers);
    next.add(url);
    failedCovers = next;
  }

  function selectRow(id: string): void {
    selectedId = id;
  }

  function confirmSelected(): void {
    if (selected === null || busy || searching) return;
    onCandidate(selected.id);
  }

  function selectIssue(): void {
    if (!selectIssueEnabled || selected === null || busy || searching) return;
    onSelectIssue(selected.id);
  }

  function activateRow(id: string): void {
    if (busy || searching) return;
    selectRow(id);
    if (selectIssueEnabled) {
      onSelectIssue(id);
      return;
    }
    onCandidate(id);
  }

  function onRowKeydown(event: KeyboardEvent): void {
    if (candidates.length === 0 || searching) return;
    const current = selected?.id ?? candidates[0].id;
    const index = candidates.findIndex((item) => item.id === current);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const next = candidates[Math.min(index + 1, candidates.length - 1)];
      selectedId = next.id;
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      const prev = candidates[Math.max(index - 1, 0)];
      selectedId = prev.id;
    } else if (event.key === "Enter") {
      event.preventDefault();
      confirmSelected();
    }
  }
</script>

<Dialog
  title="Matches"
  size="xl"
  leadingLabel={selectIssueEnabled ? "Select Issue" : undefined}
  leadingDisabled={searching || busy || selected === null}
  onLeading={selectIssueEnabled ? selectIssue : undefined}
  confirmLabel="OK"
  confirmDisabled={searching || busy || selected === null}
  {onDismiss}
  onConfirm={confirmSelected}
>
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
    <div class="grid gap-3 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)]">
      <div
        class="flex aspect-[2/3] max-h-[28rem] items-center justify-center overflow-hidden rounded-sm bg-zinc-100 text-zinc-400 dark:bg-zinc-700 dark:text-zinc-500"
        aria-hidden="true"
      >
        {#if selected !== null && selected.cover.trim() !== "" && !coverFailed(selected.cover)}
          <img
            src={matchCoverSrc(selected.cover)}
            alt=""
            referrerpolicy="no-referrer"
            class="h-full w-full object-contain"
            onerror={() => markCoverFailed(selected.cover)}
          />
        {:else}
          <Book size={40} />
        {/if}
      </div>
      <div class="flex min-h-0 min-w-0 flex-col gap-3">
        <div
          class="max-h-64 overflow-auto rounded-sm border border-zinc-200 dark:border-zinc-600"
          role="listbox"
          aria-label="Matches"
          tabindex="0"
          onkeydown={onRowKeydown}
        >
          <table class="w-full border-collapse text-left text-sm">
            <thead
              class="sticky top-0 bg-white text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            >
              <tr>
                <th class="px-2 py-1.5 font-medium">Series</th>
                <th class="w-16 px-2 py-1.5 font-medium">Year</th>
                <th class="w-16 px-2 py-1.5 font-medium">Issues</th>
                <th class="px-2 py-1.5 font-medium">{creditHeading}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-200 dark:divide-zinc-700">
              {#each candidates as candidate (candidate.id)}
                <tr
                  role="option"
                  aria-selected={selected?.id === candidate.id}
                  class="cursor-pointer {selected?.id === candidate.id
                    ? 'bg-blue-600/10 dark:bg-blue-500/15'
                    : 'hover:bg-blue-600/10 dark:hover:bg-blue-500/15'} {busy
                    ? 'opacity-40'
                    : ''}"
                  onclick={() => {
                    if (!busy) selectRow(candidate.id);
                  }}
                  ondblclick={() => activateRow(candidate.id)}
                >
                  <td
                    class="max-w-0 truncate px-2 py-1.5 text-zinc-900 dark:text-zinc-100"
                    >{candidate.title}</td
                  >
                  <td class="px-2 py-1.5 text-zinc-500 dark:text-zinc-400"
                    >{candidate.year}</td
                  >
                  <td class="px-2 py-1.5 text-zinc-500 dark:text-zinc-400"
                    >{candidate.count}</td
                  >
                  <td
                    class="max-w-0 truncate px-2 py-1.5 text-zinc-500 dark:text-zinc-400"
                    >{candidate.credit}</td
                  >
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div
          class="min-h-24 overflow-y-auto rounded-sm border border-zinc-200 px-3 py-2 text-sm text-zinc-500 dark:border-zinc-600 dark:text-zinc-400"
        >
          {#if selected !== null && selected.summary.trim() !== ""}
            {selected.summary}
          {/if}
        </div>
      </div>
    </div>
  {/if}
</Dialog>
