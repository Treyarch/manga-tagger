<script lang="ts">
  import { tick } from "svelte";
  import { Book, ListOrdered, LoaderCircle } from "lucide-svelte";
  import Dialog from "./Dialog.svelte";
  import type { Candidate, IssueCandidate } from "../library";
  import { matchCoverSrc, preferredIssueId } from "../library";

  let {
    series,
    issues,
    loading,
    busy,
    preferredNumber,
    onDismiss,
    onIssue,
  }: {
    series: Candidate;
    issues: IssueCandidate[];
    loading: boolean;
    busy: boolean;
    preferredNumber: string;
    onDismiss: () => void;
    onIssue: (id: string) => void;
  } = $props();

  let selectedId = $state("");
  let failedCovers = $state(new Set<string>());
  let listEl: HTMLDivElement | undefined = $state();

  const title = $derived(
    series.year.trim() !== ""
      ? `${series.title} (${series.year}) - Select Issue`
      : `${series.title} - Select Issue`,
  );
  const selected = $derived(
    issues.find((item) => item.id === selectedId) ?? issues[0] ?? null,
  );
  const previewCover = $derived(
    selected !== null && selected.cover.trim() !== ""
      ? selected.cover
      : series.cover,
  );

  $effect(() => {
    if (loading || issues.length === 0) {
      selectedId = "";
      return;
    }
    if (issues.some((item) => item.id === selectedId)) return;
    selectedId = preferredIssueId(issues, preferredNumber) ?? "";
  });

  $effect(() => {
    const id = selectedId;
    if (!id || loading) return;
    void tick().then(() => {
      const row = listEl?.querySelector(`[data-issue-id="${CSS.escape(id)}"]`);
      if (row instanceof HTMLElement) {
        row.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    });
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
    if (selected === null || busy || loading) return;
    onIssue(selected.id);
  }

  function onRowKeydown(event: KeyboardEvent): void {
    if (issues.length === 0 || loading) return;
    const current = selected?.id ?? issues[0].id;
    const index = issues.findIndex((item) => item.id === current);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const next = issues[Math.min(index + 1, issues.length - 1)];
      selectedId = next.id;
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      const prev = issues[Math.max(index - 1, 0)];
      selectedId = prev.id;
    } else if (event.key === "Enter") {
      event.preventDefault();
      confirmSelected();
    }
  }
</script>

<Dialog
  {title}
  size="xl"
  confirmLabel="OK"
  confirmDisabled={loading || busy || selected === null}
  {onDismiss}
  onConfirm={confirmSelected}
>
  {#snippet icon()}
    <ListOrdered size={20} />
  {/snippet}
  {#if loading}
    <div
      class="flex items-center justify-center gap-2 py-8 text-sm text-zinc-500 dark:text-zinc-400"
      aria-busy="true"
      role="status"
    >
      <LoaderCircle size={20} class="animate-spin" aria-hidden="true" />
      <span>Loading issues…</span>
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)]">
      <div
        class="flex aspect-[2/3] max-h-[28rem] items-center justify-center overflow-hidden rounded-sm bg-zinc-100 text-zinc-400 dark:bg-zinc-700 dark:text-zinc-500"
        aria-hidden="true"
      >
        {#if previewCover.trim() !== "" && !coverFailed(previewCover)}
          <img
            src={matchCoverSrc(previewCover)}
            alt=""
            referrerpolicy="no-referrer"
            class="h-full w-full object-contain"
            onerror={() => markCoverFailed(previewCover)}
          />
        {:else}
          <Book size={40} />
        {/if}
      </div>
      <div class="flex min-h-0 min-w-0 flex-col gap-3">
        <div
          bind:this={listEl}
          class="max-h-64 overflow-auto rounded-sm border border-zinc-200 dark:border-zinc-600"
          role="listbox"
          aria-label="Issues"
          tabindex="0"
          onkeydown={onRowKeydown}
        >
          <table class="w-full border-collapse text-left text-sm">
            <thead
              class="sticky top-0 bg-white text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            >
              <tr>
                <th class="w-20 px-2 py-1.5 font-medium">Issue</th>
                <th class="w-24 px-2 py-1.5 font-medium">Date</th>
                <th class="px-2 py-1.5 font-medium">Title</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-200 dark:divide-zinc-700">
              {#each issues as issue (issue.id)}
                <tr
                  data-issue-id={issue.id}
                  role="option"
                  aria-selected={selected?.id === issue.id}
                  class="cursor-pointer {selected?.id === issue.id
                    ? 'bg-blue-600/10 dark:bg-blue-500/15'
                    : 'hover:bg-blue-600/10 dark:hover:bg-blue-500/15'} {busy
                    ? 'opacity-40'
                    : ''}"
                  onclick={() => {
                    if (!busy) selectRow(issue.id);
                  }}
                  ondblclick={() => {
                    if (!busy) {
                      selectRow(issue.id);
                      onIssue(issue.id);
                    }
                  }}
                >
                  <td class="px-2 py-1.5 text-zinc-900 dark:text-zinc-100"
                    >{issue.number}</td
                  >
                  <td class="px-2 py-1.5 text-zinc-500 dark:text-zinc-400"
                    >{issue.date}</td
                  >
                  <td
                    class="max-w-0 truncate px-2 py-1.5 text-zinc-500 dark:text-zinc-400"
                    >{issue.title}</td
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
