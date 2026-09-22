<script lang="ts">
  import { ChevronLeft, ChevronRight } from "lucide-svelte";
  import Button from "./Button.svelte";
  import Select from "./Select.svelte";
  import Textarea from "./Textarea.svelte";
  import TextInput from "./TextInput.svelte";
  import {
    FORM_FIELDS,
    SHARED_FIELDS,
    mangaChoices,
    requestsPage,
    type Candidate,
    type InspectorForm,
    type Volume,
  } from "../library";

  let {
    anchor,
    pageIndex,
    form,
    formLocked,
    busy,
    lines,
    noMatches,
    candidates,
    onPage,
    onEdit,
    onCandidate,
  }: {
    anchor: Volume | null;
    pageIndex: number | null;
    form: InspectorForm | null;
    formLocked: boolean;
    busy: boolean;
    lines: string[];
    noMatches: boolean;
    candidates: Candidate[];
    onPage: (index: number) => void;
    onEdit: (key: string, value: string) => void;
    onCandidate: (id: string) => void;
  } = $props();

  let pageUrl = $state<string | null>(null);
  const showPage = $derived(
    anchor !== null && pageIndex !== null && requestsPage(anchor),
  );
  const pageCount = $derived(anchor?.archive_page_count ?? 0);
  const fields = $derived(
    form === null ? [] : form.mode === "one" ? FORM_FIELDS : SHARED_FIELDS,
  );

  $effect(() => {
    const volume = anchor;
    const index = pageIndex;
    if (volume === null || index === null || !requestsPage(volume)) {
      pageUrl = null;
      return;
    }
    const path = volume.path;
    let cancelled = false;
    let objectUrl: string | null = null;
    pageUrl = null;
    void fetch(
      `/api/page?path=${encodeURIComponent(path)}&index=${index}`,
    ).then(async (response) => {
      if (!response.ok || cancelled) return;
      const blob = await response.blob();
      if (cancelled) return;
      objectUrl = URL.createObjectURL(blob);
      pageUrl = objectUrl;
    });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  });
</script>

<div class="flex flex-col gap-3 p-4">
  {#if lines.length > 0}
    <ul class="flex flex-col gap-1 text-sm text-zinc-900 dark:text-zinc-100">
      {#each lines as line}
        <li>{line}</li>
      {/each}
    </ul>
  {/if}
  {#if noMatches}
    <p class="text-sm text-zinc-500 dark:text-zinc-400">No matches.</p>
  {/if}
  {#if candidates.length > 0}
    <ul class="flex flex-col">
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
  {#if anchor && showPage}
    <div class="flex flex-col gap-2">
      {#if pageUrl}
        <img src={pageUrl} alt="" class="max-h-80 w-full object-contain" />
      {/if}
      <div class="flex justify-between">
        <Button
          icon
          label="Previous page"
          disabled={pageIndex === null || pageIndex <= 0}
          onclick={() => pageIndex !== null && onPage(pageIndex - 1)}
        >
          <ChevronLeft size={20} />
        </Button>
        <Button
          icon
          label="Next page"
          disabled={pageIndex === null || pageIndex >= pageCount - 1}
          onclick={() => pageIndex !== null && onPage(pageIndex + 1)}
        >
          <ChevronRight size={20} />
        </Button>
      </div>
    </div>
  {:else if anchor && anchor.error_message}
    <p class="text-sm text-zinc-900 dark:text-zinc-100">{anchor.error_message}</p>
  {/if}
  {#if form}
    <div class="flex flex-col gap-3">
      {#each fields as name (name)}
        {@const field = form.values[name]}
        <label class="flex flex-col gap-1" for={`field-${name}`}>
          <span class="text-xs text-zinc-500 dark:text-zinc-400">{name}</span>
          {#if name === "Summary" || name === "Notes"}
            <Textarea
              id={`field-${name}`}
              value={field.value}
              placeholder={field.mixed ? "Mixed" : ""}
              disabled={formLocked}
              onValue={(next) => onEdit(name, next)}
            />
          {:else if name === "Manga"}
            <Select
              value={field.value}
              disabled={formLocked}
              options={mangaChoices(field.value).map((option) => ({
                value: option,
                label: option,
              }))}
              onValue={(next) => onEdit(name, next)}
            />
          {:else}
            <TextInput
              id={`field-${name}`}
              value={field.value}
              placeholder={field.mixed ? "Mixed" : ""}
              disabled={formLocked}
              onValue={(next) => onEdit(name, next)}
            />
          {/if}
        </label>
      {/each}
    </div>
  {/if}
</div>
