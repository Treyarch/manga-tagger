<script lang="ts">
  import { onDestroy, untrack } from "svelte";
  import { Settings } from "lucide-svelte";
  import MotionPanel from "./MotionPanel.svelte";
  import { motion } from "../motion";
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
  let direction = $state(12);
  let animateInterface = $state(untrack(() => config.animate_interface));
  let finished = false;
  onDestroy(() => {
    if (!finished) motion.clearPreview();
  });

  function dismiss() {
    finished = true;
    motion.clearPreview();
    onClose();
  }

  function switchTab(next: TabId) {
    const nextIndex = TABS.findIndex((item) => item.id === next);
    const previousIndex = TABS.findIndex((item) => item.id === tab);
    direction = nextIndex >= previousIndex ? 12 : -12;
    tab = next;
  }
  let roots = $state(untrack(() => config.library_roots.join("\n")));
  let apiKey = $state(untrack(() => config.comicvine_api_key));
  let nautiljonBaseUrl = $state(untrack(() => config.nautiljon_base_url));
  let nautiljonApiKey = $state(untrack(() => config.nautiljon_api_key));
  let keepOriginal = $state(untrack(() => config.keep_cbr_original));
  let writePosterOnSave = $state(untrack(() => config.write_poster_on_save));
  let autoSaveOnSwitch = $state(untrack(() => config.auto_save_metadata_on_switch));
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
        write_poster_on_save: writePosterOnSave,
        auto_save_metadata_on_switch: autoSaveOnSwitch,
        title_languages: parseLanguages(languages),
        enabled_providers: scrapers
          .filter((item) => item.enabled)
          .map((item) => item.id),
        theme,
        animate_interface: animateInterface,
      });
      finished = true;
      motion.setSaved(next.animate_interface);
      motion.clearPreview();
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
  onDismiss={dismiss}
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
          class="rounded-md px-2 py-1.5 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent {tab ===
          item.id
            ? 'bg-app-selection text-app-text'
            : 'text-app-text hover:bg-app-selection'}"
          aria-current={tab === item.id ? "page" : undefined}
          onclick={() => switchTab(item.id)}
        >
          {item.label}
        </button>
      {/each}
    </nav>
    <div class="min-w-0 flex-1">
      <MotionPanel identity={tab} y={direction}>
        {#if tab === "general"}
          <div class="flex flex-col gap-3">
            <label class="flex flex-col gap-1">
              <span class="text-xs text-app-muted">Theme</span>
              <Select
                label="Theme"
                value={theme}
                options={THEME_OPTIONS}
                onValue={(value) => (theme = value)}
              />
            </label>
            <div class="flex flex-col gap-1">
              <Checkbox
                label="Animate interface"
                bind:checked={() => animateInterface, (value) => {
                  animateInterface = value;
                  motion.preview(value);
                }}
              />
              <p class="text-xs text-app-muted">
                Smooth panel transitions and resizing. Respects reduced motion settings.
              </p>
            </div>
            <label class="flex flex-col gap-1">
              <span class="text-xs text-app-muted">Library roots</span>
              <Textarea value={roots} rows={4} onValue={(value) => (roots = value)} />
            </label>
            <label class="flex flex-col gap-1">
              <span class="text-xs text-app-muted">Title languages</span>
              <TextInput value={languages} onValue={(value) => (languages = value)} />
            </label>
          </div>
        {:else if tab === "archives"}
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-2">
              <Checkbox label="Keep the original CBR" bind:checked={keepOriginal} />
              <p class="text-xs text-app-muted">
                Convert writes a sibling CBZ. When this is on (the default), the original
                CBR is kept beside the new CBZ. When off, the CBR is deleted after a
                successful convert so each book stays one file.
              </p>
            </div>
            <div class="flex flex-col gap-2">
              <Checkbox label="Write poster on save" bind:checked={writePosterOnSave} />
              <p class="text-xs text-app-muted">
                When on (the default), a successful save or rename writes a sibling
                poster JPEG from the cover. When off, those jobs do not extract a
                poster; rename still moves an existing poster with the archive.
              </p>
            </div>
            <div class="flex flex-col gap-2">
              <Checkbox
                label="Auto-save metadata on switch"
                bind:checked={autoSaveOnSwitch}
              />
              <p class="text-xs text-app-muted">
                When off (the default), changing issue or place with unsaved metadata
                asks Save / Don't save / Cancel. When on, the app saves that form then
                switches.
              </p>
            </div>
          </div>
        {:else}
          <ul class="flex flex-col gap-3">
            {#each scrapers as item (item.id)}
              <li
                class="flex flex-col gap-2 rounded-md border border-app-border p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="text-sm font-medium text-app-text">
                      {item.label}
                    </p>
                    <p class="text-xs text-app-muted">{item.note}</p>
                  </div>
                  <Checkbox
                    label="Enable {item.label}"
                    hideLabel
                    bind:checked={item.enabled}
                  />
                </div>
                {#if item.id === "comicvine"}
                  <label class="flex flex-col gap-1">
                    <span class="text-xs text-app-muted"
                      >Comic Vine API key</span
                    >
                    <TextInput value={apiKey} onValue={(value) => (apiKey = value)} />
                  </label>
                {:else if item.id === "nautiljon"}
                  <label class="flex flex-col gap-1">
                    <span class="text-xs text-app-muted"
                      >Nautiljon base URL</span
                    >
                    <TextInput
                      value={nautiljonBaseUrl}
                      onValue={(value) => (nautiljonBaseUrl = value)}
                    />
                  </label>
                  <label class="flex flex-col gap-1">
                    <span class="text-xs text-app-muted"
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
      </MotionPanel>
      {#if error}
        <p class="mt-3 text-sm text-app-text">{error}</p>
      {/if}
    </div>
  </div>
</Dialog>
