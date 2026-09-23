<script lang="ts">
  import Select from "./Select.svelte";
  import Textarea from "./Textarea.svelte";
  import TextInput from "./TextInput.svelte";
  import PagePreview from "./PagePreview.svelte";
  import {
    FORM_FIELDS,
    SHARED_FIELDS,
    mangaChoices,
    type Candidate,
    type InspectorForm,
    type Volume,
  } from "../library";

  let {
    anchor,
    form,
    formLocked,
    busy,
    lines,
    noMatches,
    candidates,
    onEdit,
    onCandidate,
  }: {
    anchor: Volume | null;
    form: InspectorForm | null;
    formLocked: boolean;
    busy: boolean;
    lines: string[];
    noMatches: boolean;
    candidates: Candidate[];
    onEdit: (key: string, value: string) => void;
    onCandidate: (id: string) => void;
  } = $props();

  const fields = $derived(
    form === null ? [] : form.mode === "one" ? FORM_FIELDS : SHARED_FIELDS,
  );
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
  {#if anchor}
    {#key anchor.path}
      <PagePreview {anchor} />
    {/key}
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
