<script lang="ts">
  import { untrack } from "svelte";
  import { Settings } from "lucide-svelte";
  import Checkbox from "./Checkbox.svelte";
  import Dialog from "./Dialog.svelte";
  import Textarea from "./Textarea.svelte";
  import TextInput from "./TextInput.svelte";
  import { parseLanguages, parseRootLines } from "../library";
  import { putConfig, type Config } from "../api";

  let {
    config,
    onClose,
    onSaved,
  }: {
    config: Config;
    onClose: () => void;
    onSaved: (config: Config) => void;
  } = $props();

  let roots = $state(untrack(() => config.library_roots.join("\n")));
  let apiKey = $state(untrack(() => config.comicvine_api_key));
  let keepOriginal = $state(untrack(() => config.keep_cbr_original));
  let languages = $state(untrack(() => config.title_languages.join(", ")));
  let error = $state("");

  async function save() {
    const parsed = parseRootLines(roots);
    if (parsed.error) {
      error = parsed.error;
      return;
    }
    try {
      const next = await putConfig({
        library_roots: parsed.roots,
        comicvine_api_key: apiKey,
        keep_cbr_original: keepOriginal,
        title_languages: parseLanguages(languages),
      });
      onSaved(next);
    } catch (exc) {
      error = exc instanceof Error ? exc.message : "Could not save settings.";
    }
  }
</script>

<Dialog title="Settings" confirmLabel="Save" onDismiss={onClose} onConfirm={save}>
  {#snippet icon()}
    <Settings size={20} />
  {/snippet}
  <div class="flex flex-col gap-3">
    <label class="flex flex-col gap-1">
      <span class="text-xs text-zinc-500 dark:text-zinc-400">Library roots</span>
      <Textarea value={roots} rows={4} onValue={(value) => (roots = value)} />
    </label>
    <label class="flex flex-col gap-1">
      <span class="text-xs text-zinc-500 dark:text-zinc-400">Comic Vine API key</span>
      <TextInput value={apiKey} onValue={(value) => (apiKey = value)} />
    </label>
    <Checkbox label="Keep the original CBR" bind:checked={keepOriginal} />
    <label class="flex flex-col gap-1">
      <span class="text-xs text-zinc-500 dark:text-zinc-400">Title languages</span>
      <TextInput value={languages} onValue={(value) => (languages = value)} />
    </label>
    {#if error}
      <p class="text-sm text-zinc-900 dark:text-zinc-100">{error}</p>
    {/if}
  </div>
</Dialog>
