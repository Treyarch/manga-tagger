<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import { ChevronLeft, ChevronRight } from "lucide-svelte";
  import Button from "./Button.svelte";
  import {
    initialPageIndex,
    requestsPage,
    type Volume,
  } from "../library";

  let { anchor }: { anchor: Volume } = $props();

  // Mount-time seed only; Inspector remounts this via {#key anchor.path}.
  let pageIndex = $state(
    untrack(() =>
      initialPageIndex(anchor.cover_index, anchor.archive_page_count),
    ),
  );
  let pageUrl = $state<string | null>(null);

  const showPage = $derived(pageIndex !== null && requestsPage(anchor));
  const pageCount = $derived(anchor.archive_page_count ?? 0);

  function goTo(index: number) {
    if (index < 0 || index >= pageCount) return;
    pageIndex = index;
  }

  $effect(() => {
    const path = anchor.path;
    const index = pageIndex;
    if (index === null || !requestsPage(anchor)) {
      const previous = pageUrl;
      pageUrl = null;
      if (previous) URL.revokeObjectURL(previous);
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
      if (previous) URL.revokeObjectURL(previous);
    });
    return () => {
      cancelled = true;
    };
  });

  onDestroy(() => {
    if (pageUrl) URL.revokeObjectURL(pageUrl);
  });
</script>

{#if showPage}
  <div class="flex flex-col gap-2">
    <div class="flex h-80 w-full items-center justify-center">
      {#if pageUrl}
        <img src={pageUrl} alt="" class="max-h-full max-w-full object-contain" />
      {/if}
    </div>
    <div class="flex justify-between">
      <Button
        icon
        label="Previous page"
        disabled={pageIndex === null || pageIndex <= 0}
        onclick={() => pageIndex !== null && goTo(pageIndex - 1)}
      >
        <ChevronLeft size={20} />
      </Button>
      <Button
        icon
        label="Next page"
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
