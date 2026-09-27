<script lang="ts">
  import { tick } from "svelte";
  import { Book, ListOrdered, LoaderCircle } from "lucide-svelte";
  import MotionPanel from "./MotionPanel.svelte";
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
      ? `${series.title} (${series.year}) - Select matching issue`
      : `${series.title} - Select matching issue`,
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
  <MotionPanel identity={loading}>
    {#if loading}
      <div
        class="flex items-center justify-center gap-2 py-8 text-sm text-app-muted"
        aria-busy="true"
        role="status"
      >
        <LoaderCircle size={20} class="animate-spin" aria-hidden="true" />
        <span>Loading issues…</span>
      </div>
    {:else}
      <div class="grid gap-3 sm:grid-cols-[minmax(10rem,14rem)_minmax(0,1fr)]">
        <div
          class="flex aspect-[2/3] max-h-[28rem] items-center justify-center overflow-hidden rounded-sm bg-app-secondary text-app-muted"
          aria-hidden="true"
        >
          <MotionPanel identity={previewCover} y={0} extra="h-full w-full" contentClass="h-full flex items-center justify-center">
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
          </MotionPanel>
        </div>
        <div class="flex min-h-0 min-w-0 flex-col gap-3">
          <div
            bind:this={listEl}
            class="max-h-64 overflow-auto rounded-sm border border-app-strong-border"
            role="listbox"
            aria-label="Issues"
            tabindex="0"
            onkeydown={onRowKeydown}
          >
            <table class="w-full border-collapse text-left text-sm">
              <thead
                class="sticky top-0 bg-app-raised text-xs text-app-muted"
              >
                <tr>
                  <th class="w-20 px-2 py-1.5 font-medium">Issue</th>
                  <th class="w-24 px-2 py-1.5 font-medium">Date</th>
                  <th class="px-2 py-1.5 font-medium">Title</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-app-border">
                {#each issues as issue (issue.id)}
                  <tr
                    data-issue-id={issue.id}
                    role="option"
                    aria-selected={selected?.id === issue.id}
                    class="cursor-pointer {selected?.id === issue.id
                      ? 'bg-app-selection'
                      : 'hover:bg-app-selection'} {busy
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
                    <td class="px-2 py-1.5 text-app-text"
                      >{issue.number}</td
                    >
                    <td class="px-2 py-1.5 text-app-muted"
                      >{issue.date}</td
                    >
                    <td
                      class="max-w-0 truncate px-2 py-1.5 text-app-muted"
                      >{issue.title}</td
                    >
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <div
            class="min-h-24 overflow-y-auto rounded-sm border border-app-strong-border px-3 py-2 text-sm text-app-muted"
          >
            <MotionPanel identity={selected?.id} y={0}>
              {#if selected !== null && selected.summary.trim() !== ""}
                {selected.summary}
              {/if}
            </MotionPanel>
          </div>
        </div>
      </div>
    {/if}
  </MotionPanel>
</Dialog>
