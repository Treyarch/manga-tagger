<script lang="ts">
  import { untrack } from "svelte";
  import { Settings } from "lucide-svelte";
  import Checkbox from "./Checkbox.svelte";
  import Dialog from "./Dialog.svelte";
  import Select from "./Select.svelte";
  import Textarea from "./Textarea.svelte";
  import TextInput from "./TextInput.svelte";
  import { PROVIDERS, parseLanguages, parseRootLines } from "../library";
  import { putConfig, type Config } from "../api";

  type TabId = "general" | "archives" | "scrapers";

  const TABS: { id: TabId; label: string }[] = [
    { id: "general", label: "General" },
    { id: "archives", label: "Archives" },
    { id: "scrapers", label: "Scrapers" },
  ];

  const THEME_OPTIONS = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];

  const SCRAPER_NOTES: Record<string, string> = {
    mangadex: "Series search. No API key.",
    anilist: "Series search. No API key.",
    jikan: "MyAnimeList via Jikan. No API key.",
    comicvine: "Series and issue search. Requires an API key.",
    nautiljon: "Series and volume search. Requires wrapper URL and key.",
  };

  let {
    config,
    onClose,
    onSaved,
  }: {
    config: Config;
    onClose: () => void;
    onSaved: (config: Config) => void;
  } = $props();

  let tab = $state<TabId>("general");
  let roots = $state(untrack(() => config.library_roots.join("\n")));
  let apiKey = $state(untrack(() => config.comicvine_api_key));
  let nautiljonBaseUrl = $state(untrack(() => config.nautiljon_base_url));
  let nautiljonApiKey = $state(untrack(() => config.nautiljon_api_key));
  let keepOriginal = $state(untrack(() => config.keep_cbr_original));
  let languages = $state(untrack(() => config.title_languages.join(", ")));
  let theme = $state(
    untrack(() =>
      config.theme === "light" || config.theme === "dark" ? config.theme : "system",
    ),
  );
  let scrapers = $state(
    untrack(() => {
      const set = new Set(config.enabled_providers);
      return PROVIDERS.map((item) => ({
        id: item.id,
        label: item.label,
        note: SCRAPER_NOTES[item.id],
        enabled: set.has(item.id),
      }));
    }),
  );
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
        nautiljon_base_url: nautiljonBaseUrl,
        nautiljon_api_key: nautiljonApiKey,
        keep_cbr_original: keepOriginal,
        title_languages: parseLanguages(languages),
        enabled_providers: scrapers
          .filter((item) => item.enabled)
          .map((item) => item.id),
        theme,
      });
      onSaved(next);
    } catch (exc) {
      error = exc instanceof Error ? exc.message : "Could not save settings.";
    }
  }
</script>

<Dialog
  title="Settings"
  size="lg"
  confirmLabel="Save"
  onDismiss={onClose}
  onConfirm={save}
>
  {#snippet icon()}
    <Settings size={20} />
  {/snippet}
  <div class="flex min-h-72 gap-4">
    <nav class="flex w-36 shrink-0 flex-col gap-1" aria-label="Settings sections">
      {#each TABS as item (item.id)}
        <button
          type="button"
          class="rounded-md px-2 py-1.5 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:focus-visible:ring-blue-500 {tab ===
          item.id
            ? 'bg-blue-600/10 text-zinc-900 dark:bg-blue-500/15 dark:text-zinc-100'
            : 'text-zinc-900 hover:bg-blue-600/10 dark:text-zinc-100 dark:hover:bg-blue-500/15'}"
          aria-current={tab === item.id ? "page" : undefined}
          onclick={() => (tab = item.id)}
        >
          {item.label}
        </button>
      {/each}
    </nav>
    <div class="min-w-0 flex-1">
      {#if tab === "general"}
        <div class="flex flex-col gap-3">
          <label class="flex flex-col gap-1">
            <span class="text-xs text-zinc-500 dark:text-zinc-400">Theme</span>
            <Select
              label="Theme"
              value={theme}
              options={THEME_OPTIONS}
              onValue={(value) => (theme = value)}
            />
          </label>
          <label class="flex flex-col gap-1">
            <span class="text-xs text-zinc-500 dark:text-zinc-400">Library roots</span>
            <Textarea value={roots} rows={4} onValue={(value) => (roots = value)} />
          </label>
          <label class="flex flex-col gap-1">
            <span class="text-xs text-zinc-500 dark:text-zinc-400">Title languages</span>
            <TextInput value={languages} onValue={(value) => (languages = value)} />
          </label>
        </div>
      {:else if tab === "archives"}
        <div class="flex flex-col gap-2">
          <Checkbox label="Keep the original CBR" bind:checked={keepOriginal} />
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            Convert writes a sibling CBZ. When this is off (the default), the original
            CBR is deleted after a successful convert so each book stays one file.
            When on, the CBR is kept beside the new CBZ.
          </p>
        </div>
      {:else}
        <ul class="flex flex-col gap-3">
          {#each scrapers as item (item.id)}
            <li
              class="flex flex-col gap-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-700"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {item.label}
                  </p>
                  <p class="text-xs text-zinc-500 dark:text-zinc-400">{item.note}</p>
                </div>
                <Checkbox
                  label="Enable {item.label}"
                  hideLabel
                  bind:checked={item.enabled}
                />
              </div>
              {#if item.id === "comicvine"}
                <label class="flex flex-col gap-1">
                  <span class="text-xs text-zinc-500 dark:text-zinc-400"
                    >Comic Vine API key</span
                  >
                  <TextInput value={apiKey} onValue={(value) => (apiKey = value)} />
                </label>
              {:else if item.id === "nautiljon"}
                <label class="flex flex-col gap-1">
                  <span class="text-xs text-zinc-500 dark:text-zinc-400"
                    >Nautiljon base URL</span
                  >
                  <TextInput
                    value={nautiljonBaseUrl}
                    onValue={(value) => (nautiljonBaseUrl = value)}
                  />
                </label>
                <label class="flex flex-col gap-1">
                  <span class="text-xs text-zinc-500 dark:text-zinc-400"
                    >Nautiljon API key</span
                  >
                  <TextInput
                    value={nautiljonApiKey}
                    onValue={(value) => (nautiljonApiKey = value)}
                  />
                </label>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if error}
        <p class="mt-3 text-sm text-zinc-900 dark:text-zinc-100">{error}</p>
      {/if}
    </div>
  </div>
</Dialog>
