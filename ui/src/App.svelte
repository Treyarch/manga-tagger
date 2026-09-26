<script lang="ts">
  import { onMount, untrack } from "svelte";
  import {
    FileArchive,
    Folder,
    FolderPlus,
    LayoutGrid,
    List,
    Pencil,
    RefreshCw,
    Save,
    ScanSearch,
    Settings,
    X,
  } from "lucide-svelte";
  import { getJson, postJson, type Config } from "./lib/api";
  import BrandMark from "./lib/components/BrandMark.svelte";
  import Button from "./lib/components/Button.svelte";
  import Dialog from "./lib/components/Dialog.svelte";
  import Inspector from "./lib/components/Inspector.svelte";
  import MatchesDialog from "./lib/components/MatchesDialog.svelte";
  import IssuesDialog from "./lib/components/IssuesDialog.svelte";
  import RenameDialog from "./lib/components/RenameDialog.svelte";
  import Select from "./lib/components/Select.svelte";
  import SettingsDialog from "./lib/components/SettingsDialog.svelte";
  import Thumb from "./lib/components/Thumb.svelte";
  import ToastHost from "./lib/components/ToastHost.svelte";
  import { jobToastMessage, pushToast } from "./lib/toast";
  import {
    OFFERED_RENAME_TEMPLATE,
    POLL_MS,
    cbrCount,
    candidatesOf,
    clampProvider,
    convertConfirmMessage,
    editField,
    enabledProviderOptions,
    entriesOf,
    entryErrorLines,
    fieldLockedOnAll,
    filenameStem,
    folderDropRequest,
    groupVolumesBySeries,
    formFromVolumes,
    formIsDirty,
    formOf,
    isBusy,
    issuesOf,
    jobLabel,
    placeAfterLibrary,
    preferredIssueNumber,
    renamePlanLines,
    savePatch,
    scanRootLines,
    selectionAfterEntries,
    selectionAfterFilter,
    selectionFromClick,
    selectionKey,
    seriesForSearch,
    setFieldLocked,
    shouldRefetchLibrary,
    switchGuard,
    volumesForShelf,
    type Candidate,
    type InspectorForm,
    type IssueCandidate,
    type Job,
    type Place,
    type Selection,
    type Volume,
  } from "./lib/library";
  import { applyDocumentClass, resolveDark } from "./lib/theme";

  type PendingNavigation =
    | { type: "place"; path: string }
    | { type: "volume"; path: string; shift: boolean; toggle: boolean };

  let { initialConfig }: { initialConfig: Config } = $props();

  let config = $state(untrack(() => initialConfig));
  let places = $state<Place[]>([]);
  let volumes = $state<Volume[]>([]);
  let selectedPlace = $state<string | null>(null);
  let view = $state<"list" | "grid">("list");
  let selection = $state<Selection>({ paths: [], anchor: null });
  let form = $state<InspectorForm | null>(null);
  let provider = $state("mangadex");
  let headerJob = $state<Job | null>(null);
  let candidates = $state<Candidate[]>([]);
  let issues = $state<IssueCandidate[]>([]);
  let issuesSeries = $state<Candidate | null>(null);
  let inspectorLines = $state<string[]>([]);
  let folderError = $state("");
  let dragDepth = $state(0);
  let settingsOpen = $state(false);
  let renameOpen = $state(false);
  let convertOpen = $state(false);
  let unsavedOpen = $state(false);
  let pendingNavigation = $state<PendingNavigation | null>(null);
  let renameTemplate = $state(OFFERED_RENAME_TEMPLATE);
  let renameLines = $state<string[]>([]);
  let renameError = $state("");
  let activeId = $state<string | null>(null);
  let newestSearchId = $state<string | null>(null);
  let newestIssuesId = $state<string | null>(null);
  let newestLoadId = $state<string | null>(null);
  let loadSelectionKey = $state("");
  let planToken = 0;
  const settled = new Set<string>();

  const shelf = $derived(volumesForShelf(volumes, selectedPlace));
  const groups = $derived(groupVolumesBySeries(shelf));
  const visible = $derived(groups.flatMap((group) => group.volumes));
  const visiblePaths = $derived(visible.map((row) => row.path));
  const selectedRows = $derived(
    selection.paths.flatMap((path) => {
      const row = volumes.find((item) => item.path === path);
      return row ? [row] : [];
    }),
  );
  const anchor = $derived(
    volumes.find((row) => row.path === selection.anchor) ?? null,
  );
  const busy = $derived(isBusy(headerJob));
  const searching = $derived(
    headerJob !== null && isBusy(headerJob) && headerJob.name === "Search",
  );
  const listingIssues = $derived(
    headerJob !== null && isBusy(headerJob) && headerJob.name === "Issues",
  );
  const matchesOpen = $derived(searching || candidates.length > 0);
  const issuesOpen = $derived(listingIssues || issues.length > 0);
  const headerChromeJob = $derived(
    headerJob !== null &&
      isBusy(headerJob) &&
      headerJob.name !== "Search" &&
      headerJob.name !== "Issues" &&
      headerJob.name !== "Load" &&
      headerJob.name !== "Save"
      ? headerJob
      : null,
  );
  const formLocked = $derived(
    headerJob !== null &&
      isBusy(headerJob) &&
      (headerJob.name === "Load" || headerJob.name === "Save"),
  );
  const selectedCbr = $derived(cbrCount(selectedRows));
  const providerOptions = $derived(
    enabledProviderOptions(config.enabled_providers),
  );

  $effect(() => {
    const enabled = config.enabled_providers;
    const next = clampProvider(untrack(() => provider), enabled);
    if (next !== untrack(() => provider)) provider = next;
  });

  function rowsFor(paths: string[]): Volume[] {
    return paths.flatMap((path) => {
      const row = volumes.find((item) => item.path === path);
      return row ? [row] : [];
    });
  }

  function rebuildForm() {
    form = formFromVolumes(rowsFor(selection.paths));
  }

  function terminal(state: string): boolean {
    return state === "succeeded" || state === "failed" || state === "cancelled";
  }

  async function loadShelf() {
    const library = await getJson<{ places: Place[]; volumes: Volume[] }>(
      "/api/library",
    );
    volumes = library.volumes;
    places = library.places;
    selectedPlace = placeAfterLibrary(selectedPlace, places);
    selection = selectionAfterFilter(visiblePathsAfter(), selection);
    rebuildForm();
  }

  function visiblePathsAfter(): string[] {
    return groupVolumesBySeries(
      volumesForShelf(volumes, selectedPlace),
    ).flatMap((group) => group.volumes.map((row) => row.path));
  }

  async function refreshLibrary(job: Job) {
    const library = await getJson<{ places: Place[]; volumes: Volume[] }>(
      "/api/library",
    );
    volumes = library.volumes;
    places = library.places;
    const nextPlace = placeAfterLibrary(selectedPlace, places);
    const placeChanged = nextPlace !== selectedPlace;
    selectedPlace = nextPlace;
    if (placeChanged || job.name === "Rename") {
      selection = { paths: [], anchor: null };
    } else if (job.name === "Save" || job.name === "Convert") {
      selection = selectionAfterEntries(
        selection,
        entriesOf(job.result),
        new Set(volumes.map((row) => row.path)),
      );
    } else {
      selection = selectionAfterFilter(visiblePathsAfter(), selection);
    }
    if (!(job.name === "Scan" && formIsDirty(form))) rebuildForm();
    if (job.name === "Scan") {
      const result = (job.result ?? {}) as {
        skipped?: string[];
        incomplete?: string[];
      };
      const lines = scanRootLines(result);
      if (job.state === "failed" && job.error_message) lines.unshift(job.error_message);
      inspectorLines = lines;
    } else {
      const lines = entryErrorLines(entriesOf(job.result));
      inspectorLines =
        lines.length === 0 && job.state === "failed" && job.error_message
          ? [job.error_message]
          : lines;
    }
  }

  function toastFrom(job: Job) {
    const toast = jobToastMessage(job);
    if (toast) pushToast(toast.message, toast.tone, toast.icon);
  }

  async function settle(job: Job) {
    if (settled.has(job.id) || !terminal(job.state)) return;
    settled.add(job.id);
    if (job.name === "Search") {
      if (job.id !== newestSearchId) return;
      if (job.state === "failed" || job.state === "cancelled") {
        candidates = [];
        issues = [];
        issuesSeries = null;
        if (job.state === "failed") toastFrom(job);
        return;
      }
      if (job.state !== "succeeded") return;
      candidates = candidatesOf(job.result);
      toastFrom(job);
      return;
    }
    if (job.name === "Issues") {
      if (job.id !== newestIssuesId) return;
      if (job.state === "failed" || job.state === "cancelled") {
        issues = [];
        issuesSeries = null;
        if (job.state === "failed") toastFrom(job);
        return;
      }
      if (job.state !== "succeeded") return;
      const found = issuesOf(job.result);
      if (found.length === 0) {
        issues = [];
        issuesSeries = null;
        toastFrom(job);
        return;
      }
      issues = found;
      return;
    }
    if (job.name === "Load") {
      if (job.id !== newestLoadId || job.state === "cancelled") return;
      if (job.state === "failed") {
        toastFrom(job);
        return;
      }
      if (selectionKey(selection) !== loadSelectionKey) return;
      const next = formOf(job.result);
      if (next) form = next;
      candidates = [];
      issues = [];
      issuesSeries = null;
      toastFrom(job);
      return;
    }
    if (shouldRefetchLibrary(job)) await refreshLibrary(job);
    toastFrom(job);
    if (job.name === "Save" && pendingNavigation !== null) {
      if (job.state === "succeeded") {
        const pending = pendingNavigation;
        applyNavigation(pending);
      } else {
        pendingNavigation = null;
      }
    }
  }

  function watch(job: Job) {
    activeId = job.id;
    headerJob = isBusy(job) ? job : null;
    if (!isBusy(job)) void settle(job);
  }

  async function poll() {
    const current = await getJson<Job | null>("/api/jobs/current");
    if (current && isBusy(current)) {
      const job = await getJson<Job>(`/api/jobs/${current.id}`);
      headerJob = isBusy(job) ? job : null;
      activeId = job.id;
      if (!isBusy(job)) await settle(job);
      return;
    }
    headerJob = null;
    if (activeId === null) return;
    const id = activeId;
    activeId = null;
    const job = await getJson<Job>(`/api/jobs/${id}`);
    await settle(job);
  }

  async function startJob(path: string, body?: unknown): Promise<Job> {
    const job = await postJson<Job>(path, body);
    watch(job);
    return job;
  }

  function onPlace(path: string) {
    requestNavigation({ type: "place", path });
  }

  function onVolume(path: string, event: MouseEvent) {
    requestNavigation({
      type: "volume",
      path,
      shift: event.shiftKey,
      toggle: event.ctrlKey || event.metaKey,
    });
  }

  function navigationBlocked(): boolean {
    return unsavedOpen || pendingNavigation !== null || busy;
  }

  function requestNavigation(pending: PendingNavigation) {
    if (navigationBlocked()) return;
    const guard = switchGuard(form, config.auto_save_metadata_on_switch);
    if (guard === "proceed") {
      applyNavigation(pending);
      return;
    }
    pendingNavigation = pending;
    if (guard === "confirm") {
      unsavedOpen = true;
      return;
    }
    void saveForPendingNavigation();
  }

  function applyNavigation(pending: PendingNavigation) {
    if (pending.type === "place") {
      selectedPlace = pending.path === selectedPlace ? null : pending.path;
      selection = { paths: [], anchor: null };
      candidates = [];
      issues = [];
      issuesSeries = null;
    } else {
      const previous = selection.anchor;
      selection = selectionFromClick(visiblePaths, selection, pending.path, {
        shift: pending.shift,
        toggle: pending.toggle,
      });
      if (selection.anchor !== previous) {
        candidates = [];
        issues = [];
        issuesSeries = null;
      }
    }
    pendingNavigation = null;
    unsavedOpen = false;
    rebuildForm();
  }

  function dismissUnsaved() {
    pendingNavigation = null;
    unsavedOpen = false;
  }

  function discardUnsaved() {
    const pending = pendingNavigation;
    if (pending === null) {
      dismissUnsaved();
      return;
    }
    applyNavigation(pending);
  }

  async function saveForPendingNavigation() {
    unsavedOpen = false;
    if (form === null || selection.paths.length === 0) {
      const pending = pendingNavigation;
      if (pending !== null) applyNavigation(pending);
      return;
    }
    inspectorLines = [];
    try {
      await startJob("/api/jobs/save", {
        paths: selection.paths,
        patch: savePatch(form),
        mode: form.mode,
      });
    } catch {
      pendingNavigation = null;
    }
  }

  function onEdit(key: string, value: string) {
    if (form === null) return;
    form = editField(form, key, value);
  }

  async function onToggleLock(key: string, locked: boolean) {
    if (form === null || selection.paths.length === 0 || formLocked) return;
    try {
      const result = await postJson<{ volumes: Volume[] }>("/api/field-locks", {
        paths: selection.paths,
        field: key,
        locked,
      });
      const byPath = new Map(result.volumes.map((row) => [row.path, row]));
      volumes = volumes.map((row) => byPath.get(row.path) ?? row);
      const selected = rowsFor(selection.paths);
      form = setFieldLocked(form, key, fieldLockedOnAll(selected, key));
    } catch {
      /* keep current form; toast comes from shared error handling if any */
    }
  }

  async function scrape() {
    if (anchor === null || busy) return;
    candidates = [];
    issues = [];
    issuesSeries = null;
    const job = await postJson<Job>("/api/jobs/search", {
      provider,
      series: seriesForSearch(form),
      filename_stem: filenameStem(anchor.name),
    });
    newestSearchId = job.id;
    watch(job);
  }

  async function chooseCandidate(id: string) {
    if (anchor === null || form === null || busy) return;
    const series = candidates.find((item) => item.id === id);
    loadSelectionKey = selectionKey(selection);
    const job = await postJson<Job>("/api/jobs/load", {
      provider,
      match_id: id,
      filename_stem: filenameStem(anchor.name),
      mode: form.mode,
      form,
      count: series?.count ?? "",
    });
    newestLoadId = job.id;
    watch(job);
  }

  async function selectIssue(id: string) {
    if (busy || form?.mode !== "one") return;
    const series = candidates.find((item) => item.id === id);
    if (series === undefined) return;
    issues = [];
    issuesSeries = series;
    const job = await postJson<Job>("/api/jobs/issues", {
      provider,
      match_id: id,
    });
    newestIssuesId = job.id;
    watch(job);
  }

  async function chooseIssue(id: string) {
    if (anchor === null || form === null || issuesSeries === null || busy) return;
    loadSelectionKey = selectionKey(selection);
    const job = await postJson<Job>("/api/jobs/load", {
      provider,
      match_id: issuesSeries.id,
      filename_stem: filenameStem(anchor.name),
      mode: form.mode,
      form,
      issue_id: id,
      count: issuesSeries.count,
    });
    newestLoadId = job.id;
    watch(job);
  }

  async function save() {
    if (form === null || selection.paths.length === 0 || busy) return;
    inspectorLines = [];
    await startJob("/api/jobs/save", {
      paths: selection.paths,
      patch: savePatch(form),
      mode: form.mode,
    });
  }

  async function rescan() {
    if (busy) return;
    await startJob("/api/jobs/scan");
  }

  async function refreshPlan() {
    if (selectedPlace === null) return;
    const token = ++planToken;
    const template = renameTemplate;
    try {
      const result = await postJson<{ entries: Parameters<typeof renamePlanLines>[0] }>(
        "/api/rename/preview",
        { directory: selectedPlace, template },
      );
      if (token !== planToken) return;
      renameLines = renamePlanLines(result.entries);
      renameError = "";
    } catch (exc) {
      if (token !== planToken) return;
      renameLines = [];
      renameError = exc instanceof Error ? exc.message : "Could not plan the rename.";
    }
  }

  function openRename() {
    if (selectedPlace === null || busy) return;
    renameTemplate = OFFERED_RENAME_TEMPLATE;
    renameLines = [];
    renameError = "";
    renameOpen = true;
    void refreshPlan();
  }

  async function confirmRename() {
    if (selectedPlace === null) return;
    renameOpen = false;
    await startJob("/api/jobs/rename", {
      directory: selectedPlace,
      template: renameTemplate,
    });
  }

  async function runConvert() {
    convertOpen = false;
    if (selection.paths.length === 0) return;
    await startJob("/api/jobs/convert", { paths: selection.paths });
  }

  function requestConvert() {
    if (selectedCbr === 0 || busy) return;
    if (config.keep_cbr_original) void runConvert();
    else convertOpen = true;
  }

  async function dismissMatches() {
    if (searching || listingIssues) await cancelJob();
    candidates = [];
    issues = [];
    issuesSeries = null;
  }

  async function dismissIssues() {
    if (listingIssues) await cancelJob();
    issues = [];
    issuesSeries = null;
  }

  async function cancelJob() {
    if (headerJob === null) return;
    const job = await postJson<Job>(`/api/jobs/${headerJob.id}/cancel`, {});
    headerJob = isBusy(job) ? job : null;
    if (terminal(job.state)) await settle(job);
  }

  function selected(path: string): boolean {
    return selection.paths.includes(path);
  }

  async function addRoots(paths: string[]) {
    if (paths.length === 0) {
      folderError = "Drop a folder.";
      return;
    }
    try {
      const result = await postJson<{
        config: Config;
        added: string[];
        job: Job | null;
      }>("/api/library/roots", { paths });
      config = result.config;
      folderError = result.added.length === 0 ? "Drop a folder." : "";
      if (result.job) watch(result.job);
    } catch (exc) {
      folderError = exc instanceof Error ? exc.message : "Could not add that folder.";
    }
  }

  async function addFolder() {
    folderError = "";
    try {
      const chosen = await postJson<{ path: string | null }>("/api/dialogs/folder");
      if (!chosen.path) return;
      await addRoots([chosen.path]);
    } catch (exc) {
      folderError = exc instanceof Error ? exc.message : "Could not add that folder.";
    }
  }

  function onFoldersDropped(event: Event) {
    const detail = event instanceof CustomEvent ? event.detail : null;
    void addRoots(folderDropRequest(detail).paths);
  }

  onMount(() => {
    void loadShelf();
    void poll();
    const timer = setInterval(() => {
      void poll().catch(() => undefined);
    }, POLL_MS);
    window.addEventListener("folders-dropped", onFoldersDropped);
    return () => {
      clearInterval(timer);
      window.removeEventListener("folders-dropped", onFoldersDropped);
    };
  });

  $effect(() => {
    const theme = config.theme;
    const queryMedia = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      applyDocumentClass(
        document.documentElement,
        resolveDark(theme, queryMedia.matches),
      );
    };
    apply();
    queryMedia.addEventListener("change", apply);
    return () => queryMedia.removeEventListener("change", apply);
  });
</script>

<div
  class="flex h-full flex-col gap-2 bg-zinc-100 p-2 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100"
>
  <header
    class="grid h-12 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-1 border border-zinc-200 bg-white px-2 dark:border-zinc-800 dark:bg-zinc-900"
  >
    <div class="justify-self-start">
      <BrandMark />
    </div>
    <div class="flex items-center gap-1">
      <div class="w-40 shrink-0">
        <Select
          label="Provider"
          value={provider}
          options={providerOptions}
          disabled={providerOptions.length === 0}
          onValue={(next) => (provider = next)}
        />
      </div>
      <Button
        icon
        label="Scrape"
        disabled={busy || anchor === null || provider === ""}
        onclick={scrape}
      >
        <ScanSearch size={20} />
      </Button>
      <Button
        icon
        label="Save"
        disabled={busy || selection.paths.length === 0}
        onclick={save}
      >
        <Save size={20} />
      </Button>
      <Button
        icon
        label="Rename file(s)"
        disabled={busy || selectedPlace === null}
        onclick={openRename}
      >
        <Pencil size={20} />
      </Button>
      <Button icon label="Convert CBR" disabled={busy || selectedCbr === 0} onclick={requestConvert}>
        <FileArchive size={20} />
      </Button>
      <Button icon label="Scan library" disabled={busy} onclick={rescan}>
        <RefreshCw size={20} />
      </Button>
      <Button icon label="List view" pressed={view === "list"} onclick={() => (view = "list")}>
        <List size={20} />
      </Button>
      <Button icon label="Grid view" pressed={view === "grid"} onclick={() => (view = "grid")}>
        <LayoutGrid size={20} />
      </Button>
      {#if headerChromeJob}
        <span class="px-1 text-sm">{jobLabel(headerChromeJob)}</span>
        <Button icon label="Cancel" onclick={cancelJob}><X size={20} /></Button>
      {/if}
    </div>
    <div class="flex items-center justify-self-end gap-1">
      <Button icon label="Settings" onclick={() => (settingsOpen = true)}>
        <Settings size={20} />
      </Button>
      <Button
        icon
        label="Close"
        onclick={() => {
          void postJson("/api/window/close").catch(() => undefined);
        }}
      >
        <X size={20} />
      </Button>
    </div>
  </header>
  <div
    class="flex min-h-0 flex-1 overflow-hidden border border-zinc-200 dark:border-zinc-800"
  >
    <nav
      id="places"
      class="w-60 shrink-0 overflow-y-auto {dragDepth > 0
        ? 'bg-blue-600/10 dark:bg-blue-500/15'
        : 'bg-zinc-100 dark:bg-zinc-950'}"
      ondragenter={(event) => {
        event.preventDefault();
        dragDepth += 1;
      }}
      ondragover={(event) => {
        event.preventDefault();
      }}
      ondragleave={() => {
        dragDepth = Math.max(0, dragDepth - 1);
      }}
      ondrop={(event) => {
        event.preventDefault();
        dragDepth = 0;
      }}
    >
      <div class="flex h-9 items-center gap-1 px-2">
        <span class="min-w-0 flex-1 truncate text-xs text-zinc-500 dark:text-zinc-400"
          >My library</span
        >
        <Button icon label="Add folder" onclick={() => void addFolder()}>
          <FolderPlus size={16} />
        </Button>
      </div>
      {#if folderError}
        <p class="px-2 pb-1 text-xs text-zinc-900 dark:text-zinc-100">{folderError}</p>
      {/if}
      {#if places.length === 0}
        <p class="px-2 text-xs text-zinc-500 dark:text-zinc-400">Drop a folder here.</p>
      {/if}
      {#each places as place (place.path)}
        <button
          type="button"
          class="flex h-9 w-full items-center gap-2 px-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:focus-visible:ring-blue-500 {selectedPlace ===
          place.path
            ? 'bg-blue-600/10 dark:bg-blue-500/15'
            : ''}"
          onclick={() => onPlace(place.path)}
        >
          <Folder size={16} />
          <span class="truncate">{place.label}</span>
        </button>
      {/each}
    </nav>
    <main class="min-w-0 flex-1 overflow-y-auto bg-white dark:bg-zinc-900">
      {#if visible.length === 0}
        <div class="flex h-full items-center justify-center">
          <p class="text-sm text-zinc-500 dark:text-zinc-400">No volumes yet.</p>
        </div>
      {:else if view === "list"}
        <ul>
          {#each groups as group (group.series)}
            {#if group.series !== ""}
              <li
                class="truncate px-2 pt-3 pb-1 text-xs text-zinc-500 dark:text-zinc-400"
              >
                {group.series}
              </li>
            {/if}
            {#each group.volumes as row, index (row.path)}
              <li>
                <button
                  type="button"
                  class="flex h-9 w-full items-center gap-2 px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:focus-visible:ring-blue-500 {selected(
                    row.path,
                  )
                    ? 'bg-blue-600/10 dark:bg-blue-500/15'
                    : ''}"
                  onclick={(event) => onVolume(row.path, event)}
                >
                  {#if group.series !== ""}
                    <span class="relative h-9 w-3 shrink-0" aria-hidden="true">
                      <span
                        class="absolute top-0 left-1 w-px bg-zinc-300 dark:bg-zinc-600 {index ===
                        group.volumes.length - 1
                          ? 'h-1/2'
                          : 'bottom-0'}"
                      ></span>
                      <span
                        class="absolute top-1/2 left-1 h-px w-2 bg-zinc-300 dark:bg-zinc-600"
                      ></span>
                    </span>
                  {/if}
                  <span class="flex size-4 shrink-0 items-center justify-center overflow-hidden">
                    <Thumb path={row.path} failed={row.status === "failed"} fallback />
                  </span>
                  <span class="min-w-0 flex-1 truncate text-sm">{row.name}</span>
                </button>
              </li>
            {/each}
          {/each}
        </ul>
      {:else}
        <div class="flex flex-col gap-4 p-3">
          {#each groups as group (group.series)}
            <section class="flex flex-col gap-2">
              {#if group.series !== ""}
                <h3
                  class="truncate text-xs text-zinc-500 dark:text-zinc-400"
                >
                  {group.series}
                </h3>
              {/if}
              <ul class="grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-3">
                {#each group.volumes as row (row.path)}
                  <li>
                    <button
                      type="button"
                      class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:focus-visible:ring-blue-500"
                      onclick={(event) => onVolume(row.path, event)}
                    >
                      <span
                        class="block aspect-[2/3] overflow-hidden bg-zinc-100 dark:bg-zinc-950 {selected(
                          row.path,
                        )
                          ? 'ring-2 ring-blue-600 dark:ring-blue-500'
                          : ''}"
                      >
                        {#if row.status !== "failed"}
                          <Thumb path={row.path} failed={false} />
                        {/if}
                      </span>
                      <span
                        class="mt-1 block truncate text-xs {selected(row.path)
                          ? 'bg-blue-600/10 dark:bg-blue-500/15'
                          : ''}"
                      >
                        {row.name}
                      </span>
                    </button>
                  </li>
                {/each}
              </ul>
            </section>
          {/each}
        </div>
      {/if}
    </main>
    <aside
      class="w-96 shrink-0 overflow-y-auto border-l border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
    >
      <Inspector
        {anchor}
        {form}
        {formLocked}
        lines={inspectorLines}
        {onEdit}
        {onToggleLock}
      />
    </aside>
  </div>
</div>

{#if matchesOpen}
  <MatchesDialog
    {candidates}
    {searching}
    {busy}
    {provider}
    selectIssueEnabled={form?.mode === "one"}
    onDismiss={dismissMatches}
    onCandidate={chooseCandidate}
    onSelectIssue={selectIssue}
  />
{/if}
{#if issuesOpen && issuesSeries !== null}
  <IssuesDialog
    series={issuesSeries}
    {issues}
    loading={listingIssues}
    {busy}
    preferredNumber={preferredIssueNumber(form)}
    onDismiss={dismissIssues}
    onIssue={chooseIssue}
  />
{/if}
{#if settingsOpen}
  <SettingsDialog
    {config}
    onClose={() => (settingsOpen = false)}
    onSaved={(next) => {
      const rootsChanged =
        next.library_roots.length !== config.library_roots.length ||
        next.library_roots.some((root, index) => root !== config.library_roots[index]);
      config = next;
      provider = clampProvider(provider, next.enabled_providers);
      applyDocumentClass(
        document.documentElement,
        resolveDark(
          next.theme,
          window.matchMedia("(prefers-color-scheme: dark)").matches,
        ),
      );
      settingsOpen = false;
      if (rootsChanged) {
        void getJson<Job | null>("/api/jobs/current").then((current) => {
          if (current) watch(current);
        });
      }
    }}
  />
{/if}
{#if renameOpen}
  <RenameDialog
    template={renameTemplate}
    lines={renameLines}
    error={renameError}
    onTemplate={(value) => {
      renameTemplate = value;
      void refreshPlan();
    }}
    onDismiss={() => (renameOpen = false)}
    onConfirm={confirmRename}
  />
{/if}
{#if convertOpen}
  <Dialog
    title="Convert"
    confirmLabel="Convert"
    confirmVariant="danger"
    onDismiss={() => (convertOpen = false)}
    onConfirm={runConvert}
  >
    {#snippet icon()}
      <FileArchive size={20} />
    {/snippet}
    <p class="text-sm">{convertConfirmMessage(selectedCbr)}</p>
  </Dialog>
{/if}
{#if unsavedOpen}
  <Dialog
    title="Unsaved metadata"
    leadingLabel="Don't save"
    confirmLabel="Save"
    onLeading={discardUnsaved}
    onDismiss={dismissUnsaved}
    onConfirm={() => void saveForPendingNavigation()}
  >
    {#snippet icon()}
      <Save size={20} />
    {/snippet}
    <p class="text-sm">
      Metadata changes have not been written to the archive(s) yet. Save before
      switching, or discard them?
    </p>
  </Dialog>
{/if}
<ToastHost />
