<script lang="ts">
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
</script>

<Dialog title="Rename" confirmLabel="Rename" {onDismiss} {onConfirm}>
  <div class="flex flex-col gap-3">
    <TextInput label="Template" value={template} onValue={onTemplate} />
    {#if error}
      <p class="text-sm text-zinc-900 dark:text-zinc-100">{error}</p>
    {/if}
    {#if lines.length > 0}
      <ul class="flex flex-col gap-1 text-sm text-zinc-900 dark:text-zinc-100">
        {#each lines as line}
          <li>{line}</li>
        {/each}
      </ul>
    {/if}
  </div>
</Dialog>
