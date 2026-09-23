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
  }: {
    anchor: Volume | null;
    form: InspectorForm | null;
    formLocked: boolean;
    lines: string[];
    onEdit: (key: string, value: string) => void;
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
        <label class="flex flex-col gap-1" for={`field-${name}`}>
          <span class="text-xs text-zinc-500 dark:text-zinc-400"
            >{fieldLabel(name)}</span
          >
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
                label: mangaLabel(option),
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
