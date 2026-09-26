<script lang="ts">
  import Select from "./Select.svelte";
  import Textarea from "./Textarea.svelte";
  import TextInput from "./TextInput.svelte";
  import PagePreview from "./PagePreview.svelte";
  import {
    FORM_FIELDS,
    SHARED_FIELDS,
    fieldLabel,
    mangaChoices,
    mangaLabel,
    type InspectorForm,
    type Volume,
  } from "../library";

  let {
    anchor,
    form,
    formLocked,
    lines,
    onEdit,
    onToggleLock,
  }: {
    anchor: Volume | null;
    form: InspectorForm | null;
    formLocked: boolean;
    lines: string[];
    onEdit: (key: string, value: string) => void;
    onToggleLock: (key: string, locked: boolean) => void;
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
  {#if anchor}
    {#key anchor.path}
      <PagePreview {anchor} />
    {/key}
  {/if}
  {#if form}
    <div class="flex flex-col gap-3">
      {#each fields as name (name)}
        {@const field = form.values[name]}
        {@const caption = fieldLabel(name)}
        {@const controlDisabled = formLocked || field.locked}
        {@const lockLabel = field.locked ? `Unlock ${caption}` : `Lock ${caption}`}
        <div class="flex flex-col gap-1">
          <span class="text-xs text-zinc-500 dark:text-zinc-400">{caption}</span>
          <div class="relative">
            {#if name === "Summary" || name === "Notes"}
              <Textarea
                id={`field-${name}`}
                value={field.value}
                placeholder={field.mixed ? "Mixed" : ""}
                disabled={controlDisabled}
                dirty={field.dirty}
                onValue={(next) => onEdit(name, next)}
              />
            {:else if name === "Manga"}
              <Select
                value={field.value}
                disabled={controlDisabled}
                dirty={field.dirty}
                options={mangaChoices(field.value).map((option) => ({
                  value: option,
                  label: mangaLabel(option),
                }))}
                onValue={(next) => onEdit(name, next)}
              />
            {:else}
              <TextInput
                id={`field-${name}`}
                value={field.value}
                placeholder={field.mixed ? "Mixed" : ""}
                disabled={controlDisabled}
                dirty={field.dirty}
                onValue={(next) => onEdit(name, next)}
              />
            {/if}
            <button
              type="button"
              class="absolute -top-[12px] right-1.5 z-10 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-900 dark:focus-visible:ring-blue-500 {field.locked
                ? 'text-zinc-900 dark:text-zinc-100'
                : 'text-zinc-400 dark:text-zinc-500'}"
              disabled={formLocked}
              title={lockLabel}
              aria-label={lockLabel}
              onclick={() => onToggleLock(name, !field.locked)}
            >
              <!-- Circle + padlock share one viewBox so the glyph stays optically centered. -->
              <svg
                class="pointer-events-none size-full"
                viewBox="0 0 20 20"
                fill="none"
                aria-hidden="true"
              >
                <circle
                  cx="10"
                  cy="10"
                  r="9"
                  stroke="currentColor"
                  stroke-width="1"
                />
                {#if field.locked}
                  <path
                    d="M7.75 8.75V7a2.25 2.25 0 0 1 4.5 0v1.75"
                    stroke="currentColor"
                    stroke-width="1.25"
                    stroke-linecap="round"
                  />
                  <rect
                    x="6.75"
                    y="8.75"
                    width="6.5"
                    height="5"
                    rx="1"
                    stroke="currentColor"
                    stroke-width="1.25"
                  />
                {:else}
                  <path
                    d="M7.75 8.75V7a2.25 2.25 0 0 1 4.15-1.2"
                    stroke="currentColor"
                    stroke-width="1.25"
                    stroke-linecap="round"
                  />
                  <rect
                    x="6.75"
                    y="8.75"
                    width="6.5"
                    height="5"
                    rx="1"
                    stroke="currentColor"
                    stroke-width="1.25"
                  />
                {/if}
              </svg>
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
