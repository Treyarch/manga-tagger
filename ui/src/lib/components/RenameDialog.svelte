<script lang="ts">
  import { tick } from "svelte";
  import { Pencil } from "lucide-svelte";
  import {
    RENAME_TAGS,
    insertRenameToken,
    renameToken,
    type RenameTag,
  } from "../rename";
  import Dialog from "./Dialog.svelte";
  import TextInput from "./TextInput.svelte";

  let {
    template,
    lines,
    error,
    onTemplate,
    onDismiss,
    onConfirm,
  }: {
    template: string;
    lines: string[];
    error: string;
    onTemplate: (value: string) => void;
    onDismiss: () => void;
    onConfirm: () => void;
  } = $props();

  let templateInput: HTMLInputElement | null = null;

  function dragTag(event: DragEvent, tag: RenameTag) {
    if (!event.dataTransfer) return;
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData("text/plain", renameToken(tag));
  }

  function insertTag(tag: RenameTag) {
    const insertion = insertRenameToken(
      template,
      renameToken(tag),
      templateInput?.selectionStart ?? null,
      templateInput?.selectionEnd ?? null,
    );
    onTemplate(insertion.value);
    void tick().then(() => {
      templateInput?.focus();
      templateInput?.setSelectionRange(insertion.caret, insertion.caret);
    });
  }
</script>

<Dialog title="Rename" confirmLabel="Rename" {onDismiss} {onConfirm}>
  {#snippet icon()}
    <Pencil size={20} />
  {/snippet}
  <div class="flex flex-col gap-3">
    <TextInput
      label="Template"
      value={template}
      onValue={onTemplate}
      onFocus={(input) => (templateInput = input)}
    />
    <div>
      <p class="mb-1.5 text-xs text-app-muted">Tags — drag or click to insert</p>
      <div class="flex flex-wrap gap-1.5" aria-label="Rename tags">
        {#each RENAME_TAGS as tag}
          <button
            type="button"
            draggable="true"
            aria-label="Insert {renameToken(tag)}"
            title="Drag or click to insert {renameToken(tag)}"
            class="cursor-grab rounded-md border border-app-border bg-app-secondary px-2 py-1 text-xs text-app-text hover:bg-app-secondary-hover active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent"
            ondragstart={(event) => dragTag(event, tag)}
            onclick={() => insertTag(tag)}
          >{renameToken(tag)}</button>
        {/each}
      </div>
    </div>
    {#if error}
      <p class="text-sm text-app-text">{error}</p>
    {/if}
    {#if lines.length > 0}
      <ul
        class="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-md border border-app-border bg-app-view p-2 pr-1 text-sm text-app-text"
        role="region"
        aria-label="Rename preview"
      >
        {#each lines as line}
          <li class="break-words">{line}</li>
        {/each}
      </ul>
    {/if}
  </div>
</Dialog>
