<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import { ChevronLeft, ChevronRight } from "lucide-svelte";
  import MotionPanel from "./MotionPanel.svelte";
  import { releaseAfterMotion } from "../motion";
  import Button from "./Button.svelte";
  import {
    coverPageIndex,
    initialPageIndex,
    requestsPage,
    type Volume,
  } from "../library";
  import {
    pageAfterShortcut,
    previewShortcut,
    shortcutTooltip,
    SHORTCUT_HINTS,
  } from "../shortcuts";

  let {
    anchor,
    coverActions = false,
    coverActionsDisabled = true,
    shortcutsDisabled = false,
    onReplaceCover,
    onInsertCover,
  }: {
    anchor: Volume;
    coverActions?: boolean;
    coverActionsDisabled?: boolean;
    shortcutsDisabled?: boolean;
    onReplaceCover?: () => void;
    onInsertCover?: () => void;
  } = $props();

  // Inspector remounts after a path change or a completed cover write.
  let pageIndex = $state(
    untrack(() =>
      initialPageIndex(anchor.cover_index, anchor.archive_page_count),
    ),
  );
  let pageUrl = $state<string | null>(null);

  const showPage = $derived(pageIndex !== null && requestsPage(anchor));
  const pageCount = $derived(anchor.archive_page_count ?? 0);
  const showingCover = $derived(
    pageIndex !== null && pageIndex === coverPageIndex(anchor),
  );
  const showCoverActions = $derived(coverActions && showingCover);

  function goTo(index: number) {
    if (index < 0 || index >= pageCount) return;
    pageIndex = index;
  }

  function onShortcutKeydown(event: KeyboardEvent) {
    if (!showPage) return;
    const shortcut = previewShortcut(event);
    if (shortcut === null) return;
    event.preventDefault();
    if (shortcutsDisabled || pageIndex === null) return;
    goTo(pageAfterShortcut(pageIndex, pageCount, shortcut));
  }

  $effect(() => {
    const path = anchor.path;
    const index = pageIndex;
    if (index === null || !requestsPage(anchor)) {
      const previous = pageUrl;
      pageUrl = null;
      if (previous) releaseAfterMotion(() => URL.revokeObjectURL(previous));
      return;
    }
    let cancelled = false;
    void fetch(
      `/api/page?path=${encodeURIComponent(path)}&index=${index}`,
    ).then(async (response) => {
      if (!response.ok || cancelled) return;
      const blob = await response.blob();
      if (cancelled) return;
      const objectUrl = URL.createObjectURL(blob);
      if (cancelled) {
        URL.revokeObjectURL(objectUrl);
        return;
      }
      const previous = pageUrl;
      pageUrl = objectUrl;
      if (previous) releaseAfterMotion(() => URL.revokeObjectURL(previous));
    });
    return () => {
      cancelled = true;
    };
  });

  onDestroy(() => {
    const previous = pageUrl;
    if (previous) releaseAfterMotion(() => URL.revokeObjectURL(previous));
  });
</script>

<svelte:window onkeydown={onShortcutKeydown} />

{#if showPage}
  <div class="flex flex-col gap-2">
    <div class="relative flex h-80 w-full items-center justify-center">
      <MotionPanel identity={pageUrl} y={0} extra="h-full w-full" contentClass="h-full flex items-center justify-center">
        {#if pageUrl}
          <img src={pageUrl} alt="" class="max-h-full max-w-full object-contain" />
        {/if}
      </MotionPanel>
      {#if showCoverActions}
        <div
          class="absolute inset-x-0 bottom-0 flex justify-center gap-2 bg-gradient-to-t from-zinc-950/60 to-transparent p-2"
        >
          <Button
            variant="secondary"
            label="Replace cover"
            disabled={coverActionsDisabled}
            onclick={() => onReplaceCover?.()}
          >
            Replace cover
          </Button>
          <Button
            variant="secondary"
            label="Insert cover"
            disabled={coverActionsDisabled}
            onclick={() => onInsertCover?.()}
          >
            Insert cover
          </Button>
        </div>
      {/if}
    </div>
    <div class="flex justify-between">
      <Button
        icon
        label="Previous page"
        tooltip={shortcutTooltip("Previous page", SHORTCUT_HINTS.previousPage)}
        disabled={pageIndex === null || pageIndex <= 0}
        onclick={() => pageIndex !== null && goTo(pageIndex - 1)}
      >
        <ChevronLeft size={20} />
      </Button>
      <Button
        icon
        label="Next page"
        tooltip={shortcutTooltip("Next page", SHORTCUT_HINTS.nextPage)}
        disabled={pageIndex === null || pageIndex >= pageCount - 1}
        onclick={() => pageIndex !== null && goTo(pageIndex + 1)}
      >
        <ChevronRight size={20} />
      </Button>
    </div>
  </div>
{:else if anchor.error_message}
  <p class="text-sm text-zinc-900 dark:text-zinc-100">{anchor.error_message}</p>
{/if}
