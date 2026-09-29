<script lang="ts">
  import { onMount, untrack } from "svelte";
  import {
    FileArchive,
    Folder,
    FolderMinus,
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
  import {
    getJson,
    getSystemTheme,
    postJson,
    putConfig,
    type Config,
    type SystemTheme,
  } from "./lib/api";
  import BrandMark from "./lib/components/BrandMark.svelte";
  import Button from "./lib/components/Button.svelte";
  import Dialog from "./lib/components/Dialog.svelte";
  import ContextMenu from "./lib/components/ContextMenu.svelte";
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
    canFetchCoverFromWeb,
    claimJobSettlement,
    clampProvider,
    convertConfirmMessage,
    editField,
    enabledProviderOptions,
    excludedFoldersAfterRemove,
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
    placeAfterLibrary,
    placeFromClick,
    preferredIssueNumber,
    preserveDirtyFields,
    renamePlanLines,
    requestsPage,
    savePatch,
    saveAllowsPendingNavigation,
    savePreservesDraft,
    scanRootLines,
    selectionAfterEntries,
    selectionAfterFilter,
    selectionFromClick,
    selectionKey,
    seriesGroupLabel,
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
    type ScanResult,
    type Selection,
    type Volume,
  } from "./lib/library";
  import MotionPanel from "./lib/components/MotionPanel.svelte";
  import { motion, watchReducedMotion } from "./lib/motion";
  import { applyTheme } from "./lib/theme";
  import { thumbnailRevision } from "./lib/cache";
  import {
    SIDEBAR_DEFAULT_WIDTH,
    SIDEBAR_MAX_WIDTH,
    SIDEBAR_MIN_WIDTH,
    clampSidebarWidth,
    sidebarMaxWidth,
    sidebarWidthFromKey,
  } from "./lib/layout";
  import {
    SHORTCUT_HINTS,
    activeDialog,
    appShortcut,
    dialogDismissal,
    shortcutDisposition,
    shortcutTooltip,
    type DialogKind,
  } from "./lib/shortcuts";

  type PendingNavigation =
    | { type: "place"; path: string | null }
    | { type: "volume"; path: string; shift: boolean; toggle: boolean }
    | { type: "exclude-folder"; path: string };

  type PlaceContextMenu = { path: string; x: number; y: number };

  let {
    initialConfig,
    initialSystemTheme,
  }: { initialConfig: Config; initialSystemTheme: SystemTheme | null } = $props();

  let config = $state(untrack(() => initialConfig));
  let systemTheme = $state<SystemTheme | null>(untrack(() => initialSystemTheme));
  let places = $state<Place[]>([]);
  let volumes = $state<Volume[]>([]);
  let selectedPlace = $state<string | null>(null);
  let view = $state<"list" | "grid">("list");
  let selection = $state<Selection>({ paths: [], anchor: null });
  let form = $state<InspectorForm | null>(null);
  let provider = $state("mangadex");
  let currentJob = $state<Job | null>(null);
  let candidates = $state<Candidate[]>([]);
  let issues = $state<IssueCandidate[]>([]);
  let issuesSeries = $state<Candidate | null>(null);
  let inspectorLines = $state<string[]>([]);
  let folderError = $state("");
  let placeContextMenu = $state<PlaceContextMenu | null>(null);
  let dragDepth = $state(0);
  let settingsOpen = $state(false);
  let renameOpen = $state(false);
  let convertOpen = $state(false);
  let unsavedOpen = $state(false);
  let pendingNavigation = $state<PendingNavigation | null>(null);
  let renameTemplate = $state(OFFERED_RENAME_TEMPLATE);
  let renamePaths = $state<string[]>([]);
  let renameLines = $state<string[]>([]);
  let renameError = $state("");
  let activeId = $state<string | null>(null);
  let newestSearchId = $state<string | null>(null);
  let newestIssuesId = $state<string | null>(null);
  let newestLoadId = $state<string | null>(null);
  let themePollActive = false;
  let loadSelectionKey = $state("");
  let planToken = 0;
  let coverStarting = $state(false);
  let coverRevisions = $state<Record<string, string>>({});
  let cacheRevision = $state(0);
  let paneStrip: HTMLDivElement;
  let sidebarResizeHandle: HTMLButtonElement;
  let sidebarWidth = $state(SIDEBAR_DEFAULT_WIDTH);
  let sidebarResizeMaximum = $state(SIDEBAR_MAX_WIDTH);
  let sidebarResizePointer = $state<number | null>(null);
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
  const busy = $derived(isBusy(currentJob));
  const searching = $derived(
    currentJob !== null && isBusy(currentJob) && currentJob.name === "Search",
  );
  const listingIssues = $derived(
    currentJob !== null && isBusy(currentJob) && currentJob.name === "Issues",
  );
  const matchesOpen = $derived(searching || candidates.length > 0);
  const issuesOpen = $derived(listingIssues || issues.length > 0);
  const activeModal = $derived(
    activeDialog({
      matchesOpen,
      issuesOpen,
      settingsOpen,
      renameOpen,
      convertOpen,
      unsavedOpen,
    }),
  );
  const formLocked = $derived(
    currentJob !== null &&
      isBusy(currentJob) &&
      (currentJob.name === "Load" || currentJob.name === "Save" || currentJob.name === "Cover"),
  );
  const selectedCbr = $derived(cbrCount(selectedRows));
  const providerOptions = $derived(
    enabledProviderOptions(config.enabled_providers),
  );
  const formWeb = $derived(
    form?.mode === "one" ? (form.values.Web?.value ?? "") : "",
  );
  const formNumber = $derived(
    form?.mode === "one" ? (form.values.Number?.value ?? "") : "",
  );
  const coverActions = $derived(form?.mode === "one" && anchor !== null);
  const coverActionsDisabled = $derived(
    busy || coverStarting ||
      anchor === null ||
      !canFetchCoverFromWeb(formWeb, config) ||
      !requestsPage(anchor),
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

  function constrainSidebarWidth() {
    if (!paneStrip) return;
    sidebarResizeMaximum = sidebarMaxWidth(paneStrip.clientWidth);
    sidebarWidth = clampSidebarWidth(sidebarWidth, paneStrip.clientWidth);
  }

  function resizeSidebarAt(clientX: number) {
    if (!paneStrip) return;
    const bounds = paneStrip.getBoundingClientRect();
    sidebarResizeMaximum = sidebarMaxWidth(bounds.width);
    sidebarWidth = clampSidebarWidth(clientX - bounds.left, bounds.width);
  }

  function startSidebarResize(event: PointerEvent) {
    if (event.button !== 0) return;
    event.preventDefault();
    sidebarResizePointer = event.pointerId;
    sidebarResizeHandle.setPointerCapture(event.pointerId);
    resizeSidebarAt(event.clientX);
  }

  function moveSidebarResize(event: PointerEvent) {
    if (event.pointerId !== sidebarResizePointer) return;
    resizeSidebarAt(event.clientX);
  }

  function endSidebarResize(event: PointerEvent) {
    if (event.pointerId !== sidebarResizePointer) return;
    sidebarResizePointer = null;
    if (sidebarResizeHandle.hasPointerCapture(event.pointerId)) {
      sidebarResizeHandle.releasePointerCapture(event.pointerId);
    }
  }

  function onSidebarResizeKeydown(event: KeyboardEvent) {
    if (!paneStrip) return;
    const next = sidebarWidthFromKey(
      sidebarWidth,
      event.key,
      paneStrip.clientWidth,
      event.shiftKey,
    );
    if (next === null) return;
    event.preventDefault();
    sidebarResizeMaximum = sidebarMaxWidth(paneStrip.clientWidth);
    sidebarWidth = next;
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
    const draft = form;
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
    } else if (job.name === "Save" || job.name === "Convert" || job.name === "Cover") {
      selection = selectionAfterEntries(
        selection,
        entriesOf(job.result),
        new Set(volumes.map((row) => row.path)),
      );
    } else {
      selection = selectionAfterFilter(visiblePathsAfter(), selection);
    }
    if (job.name === "Cover") {
      form = preserveDirtyFields(formFromVolumes(rowsFor(selection.paths)), form);
      for (const entry of entriesOf(job.result)) {
        if (entry.output_path) coverRevisions[entry.output_path] = job.id;
      }
    } else if (job.name === "Save" && savePreservesDraft(job)) {
      form = preserveDirtyFields(formFromVolumes(rowsFor(selection.paths)), draft);
    } else if (!(job.name === "Scan" && formIsDirty(form))) rebuildForm();
    if (job.name === "Scan") {
      const result = job.result as ScanResult | null;
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
    if (!claimJobSettlement(settled, job)) return;
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
      if (saveAllowsPendingNavigation(job)) {
        const pending = pendingNavigation;
        applyNavigation(pending);
      } else {
        pendingNavigation = null;
      }
    }
  }

  function watch(job: Job) {
    activeId = job.id;
    currentJob = isBusy(job) ? job : null;
    if (!isBusy(job)) void settle(job);
  }

  async function poll() {
    const current = await getJson<Job | null>("/api/jobs/current");
    if (current && isBusy(current)) {
      const job = await getJson<Job>(`/api/jobs/${current.id}`);
      currentJob = isBusy(job) ? job : null;
      activeId = job.id;
      if (!isBusy(job)) await settle(job);
      return;
    }
    currentJob = null;
    if (activeId === null) return;
    const id = activeId;
    activeId = null;
    const job = await getJson<Job>(`/api/jobs/${id}`);
    await settle(job);
  }

  async function pollSystemTheme() {
    if (themePollActive) return;
    themePollActive = true;
    try {
      systemTheme = await getSystemTheme();
    } catch {
      // A desktop-theme read must never interrupt job polling or app work.
    } finally {
      themePollActive = false;
    }
  }

  async function startJob(path: string, body?: unknown): Promise<Job> {
    const job = await postJson<Job>(path, body);
    watch(job);
    return job;
  }

  function onPlace(path: string | null) {
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
    if (pending.type === "exclude-folder") {
      pendingNavigation = null;
      unsavedOpen = false;
      rebuildForm();
      void removeFolder(pending.path);
      return;
    }
    if (pending.type === "place") {
      selectedPlace = placeFromClick(selectedPlace, pending.path);
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
        { directory: selectedPlace, template, paths: renamePaths },
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
    renamePaths = [...selection.paths];
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
      paths: renamePaths,
    });
  }

  async function runCover(action: "replace" | "insert") {
    if (!coverActions || coverActionsDisabled || anchor === null) return;
    coverStarting = true;
    inspectorLines = [];
    try {
      await startJob("/api/jobs/cover", {
        path: anchor.path, action, web: formWeb, number: formNumber,
      });
    } catch (exc) {
      pushToast(exc instanceof Error ? exc.message : "Cover failed.", "error");
    } finally {
      coverStarting = false;
    }
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
    if (currentJob === null) return;
    const job = await postJson<Job>(`/api/jobs/${currentJob.id}/cancel`, {});
    currentJob = isBusy(job) ? job : null;
    if (terminal(job.state)) await settle(job);
  }

  async function dismissActiveDialog(dialog: DialogKind) {
    const dismissal = dialogDismissal(dialog);
    if (dismissal === "dismiss-unsaved") dismissUnsaved();
    else if (dismissal === "close-convert") convertOpen = false;
    else if (dismissal === "close-rename") renameOpen = false;
    else if (dismissal === "close-settings") settingsOpen = false;
    else if (dismissal === "cancel-issues") await dismissIssues();
    else await dismissMatches();
  }

  function onShortcutKeydown(event: KeyboardEvent) {
    const shortcut = appShortcut(event);
    if (shortcut === null) return;
    event.preventDefault();
    if (event.repeat) return;

    const disposition = shortcutDisposition(shortcut, activeModal);
    if (disposition === "dismiss" && activeModal !== null) {
      void dismissActiveDialog(activeModal);
      return;
    }
    if (disposition !== "run") return;

    if (shortcut === "save") void save();
    else if (shortcut === "rename") openRename();
    else if (shortcut === "scan") void rescan();
    else if (shortcut === "list-view") view = "list";
    else if (shortcut === "grid-view") view = "grid";
    else if (shortcut === "settings") settingsOpen = true;
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

  function openPlaceContextMenu(event: MouseEvent, path: string) {
    event.preventDefault();
    event.stopPropagation();
    folderError = "";
    const target = event.currentTarget as HTMLElement;
    const bounds = target.getBoundingClientRect();
    placeContextMenu = {
      path,
      x: event.clientX || bounds.left + 16,
      y: event.clientY || bounds.top + bounds.height / 2,
    };
  }

  function requestRemoveFolder(path: string) {
    placeContextMenu = null;
    requestNavigation({ type: "exclude-folder", path });
  }

  async function removeFolder(path: string) {
    folderError = "";
    try {
      const result = await putConfig({
        excluded_folders: excludedFoldersAfterRemove(
          config.excluded_folders,
          path,
        ),
      });
      config = result.config;
      if (result.job) watch(result.job);
    } catch (exc) {
      folderError = exc instanceof Error ? exc.message : "Could not remove that folder.";
    }
  }

  function onFoldersDropped(event: Event) {
    const detail = event instanceof CustomEvent ? event.detail : null;
    void addRoots(folderDropRequest(detail).paths);
  }

  onMount(() => {
    const stopMotion = watchReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)"));
    constrainSidebarWidth();
    void loadShelf();
    void getJson<Job | null>("/api/jobs/startup")
      .then((startup) => {
        if (startup) watch(startup);
      })
      .catch(() => undefined);
    void poll();
    const timer = setInterval(() => {
      void poll().catch(() => undefined);
      void pollSystemTheme();
    }, POLL_MS);
    window.addEventListener("folders-dropped", onFoldersDropped);
    return () => {
      stopMotion();
      clearInterval(timer);
      window.removeEventListener("folders-dropped", onFoldersDropped);
    };
  });

  $effect(() => motion.setSaved(config.animate_interface));

  $effect(() => {
    const theme = config.theme;
    const palette = systemTheme;
    const queryMedia = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      applyTheme(
        document.documentElement,
        theme,
        queryMedia.matches,
        palette,
      );
    };
    apply();
    queryMedia.addEventListener("change", apply);
    return () => queryMedia.removeEventListener("change", apply);
  });
</script>

<svelte:window
  onkeydown={onShortcutKeydown}
  onresize={constrainSidebarWidth}
/>

<div
  class="flex h-full flex-col gap-2 bg-app-window p-2 text-app-text {sidebarResizePointer !==
  null
    ? 'sidebar-resizing select-none'
    : ''}"
>
  <header
    class="grid h-12 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-1 border border-app-border bg-app-view px-2"
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
        tooltip={shortcutTooltip("Save", SHORTCUT_HINTS.save)}
        disabled={busy || selection.paths.length === 0}
        onclick={save}
      >
        <Save size={20} />
      </Button>
      <Button
        icon
        label="Rename file(s)"
        tooltip={shortcutTooltip("Rename file(s)", SHORTCUT_HINTS.rename)}
        disabled={busy || selectedPlace === null}
        onclick={openRename}
      >
        <Pencil size={20} />
      </Button>
      <Button icon label="Convert CBR" disabled={busy || selectedCbr === 0} onclick={requestConvert}>
        <FileArchive size={20} />
      </Button>
      <Button
        icon
        label="Scan library"
        tooltip={shortcutTooltip("Scan library", SHORTCUT_HINTS.scan)}
        disabled={busy}
        onclick={rescan}
      >
        <RefreshCw size={20} />
      </Button>
      <Button
        icon
        label="List view"
        tooltip={shortcutTooltip("List view", SHORTCUT_HINTS.listView)}
        pressed={view === "list"}
        onclick={() => (view = "list")}
      >
        <List size={20} />
      </Button>
      <Button
        icon
        label="Grid view"
        tooltip={shortcutTooltip("Grid view", SHORTCUT_HINTS.gridView)}
        pressed={view === "grid"}
        onclick={() => (view = "grid")}
      >
        <LayoutGrid size={20} />
      </Button>
    </div>
    <div class="flex items-center justify-self-end gap-1">
      <Button
        icon
        label="Settings"
        tooltip={shortcutTooltip("Settings", SHORTCUT_HINTS.settings)}
        onclick={() => (settingsOpen = true)}
      >
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
    bind:this={paneStrip}
    class="flex min-h-0 flex-1 overflow-hidden border border-app-border"
  >
    <nav
      id="places"
      style:width={`${sidebarWidth}px`}
      class="relative w-60 shrink-0 overflow-y-auto {dragDepth > 0
        ? 'bg-app-selection'
        : 'bg-app-window'}"
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
      <button
        type="button"
        aria-label="Show whole library"
        aria-disabled={selectedPlace === null}
        tabindex={selectedPlace === null ? -1 : 0}
        class="absolute inset-0 size-full cursor-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-app-accent"
        onclick={() => {
          if (selectedPlace !== null) onPlace(null);
        }}
      ></button>
      <div class="pointer-events-none relative z-10 flex h-9 items-center gap-1 px-2">
        <span class="min-w-0 flex-1 truncate text-sm text-app-muted"
          >My library</span
        >
        <span class="pointer-events-auto">
          <Button icon label="Add folder" onclick={() => void addFolder()}>
            <FolderPlus size={16} />
          </Button>
        </span>
      </div>
      {#if folderError}
        <p class="pointer-events-none relative z-10 px-2 pb-1 text-xs text-app-text">{folderError}</p>
      {/if}
      {#if places.length === 0}
        <p class="pointer-events-none relative z-10 px-2 text-xs text-app-muted">Drop a folder here.</p>
      {/if}
      {#each places as place (place.path)}
        <button
          type="button"
          aria-haspopup="menu"
          class="relative z-10 flex h-9 w-full items-center gap-2 px-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent {selectedPlace ===
          place.path
            ? 'bg-app-selection'
            : ''}"
          onclick={() => onPlace(place.path)}
          oncontextmenu={(event) => openPlaceContextMenu(event, place.path)}
        >
          <span class="flex size-4 shrink-0 items-center justify-center" aria-hidden="true">
            <Folder size={16} />
          </span>
          <span class="truncate">{place.label}</span>
        </button>
      {/each}
    </nav>
    <button
      bind:this={sidebarResizeHandle}
      type="button"
      aria-label={`Resize library sidebar, ${sidebarWidth} pixels. Minimum ${SIDEBAR_MIN_WIDTH}, maximum ${sidebarResizeMaximum}.`}
      class="group relative z-20 w-px shrink-0 touch-none cursor-col-resize border-0 bg-transparent p-0 focus-visible:outline-none"
      onpointerdown={startSidebarResize}
      onpointermove={moveSidebarResize}
      onpointerup={endSidebarResize}
      onpointercancel={endSidebarResize}
      onlostpointercapture={(event) => {
        if (event.pointerId === sidebarResizePointer) {
          sidebarResizePointer = null;
        }
      }}
      onkeydown={onSidebarResizeKeydown}
    >
      <span
        aria-hidden="true"
        class="absolute inset-y-0 left-1/2 w-[7px] -translate-x-1/2"
      ></span>
      <span
        aria-hidden="true"
        class="pointer-events-none absolute inset-y-0 left-0 w-px {sidebarResizePointer !==
        null
          ? 'bg-app-strong-border'
          : 'bg-app-border group-hover:bg-app-strong-border group-focus-visible:bg-app-strong-border'}"
      ></span>
    </button>
    <main class="min-w-0 flex-1 overflow-y-auto bg-app-view">
      <MotionPanel identity={`${selectedPlace}:${view}`} extra={visible.length === 0 ? "h-full" : "min-h-full"} contentClass={visible.length === 0 ? "h-full" : ""}>
        {#if visible.length === 0}
          <div class="flex h-full items-center justify-center">
            <p class="text-sm text-app-muted">No volumes yet.</p>
          </div>
        {:else if view === "list"}
          <ul>
            {#each groups as group (group.series)}
              <li
                class="truncate px-2 pt-3 pb-1 text-sm text-app-muted"
              >
                {seriesGroupLabel(group.series)}
              </li>
              {#each group.volumes as row, index (row.path)}
                <li>
                  <button
                    type="button"
                    class="flex h-9 w-full items-center gap-2 px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent {selected(
                      row.path,
                    )
                      ? 'bg-app-selection'
                      : ''}"
                    onclick={(event) => onVolume(row.path, event)}
                  >
                    <span class="relative h-9 w-3 shrink-0" aria-hidden="true">
                      <span
                        class="absolute top-0 left-1 w-px bg-app-strong-border {index ===
                        group.volumes.length - 1
                          ? 'h-1/2'
                          : 'bottom-0'}"
                      ></span>
                      <span
                        class="absolute top-1/2 left-1 h-px w-2 bg-app-strong-border"
                      ></span>
                    </span>
                    <span class="flex size-4 shrink-0 items-center justify-center overflow-hidden">
                      <Thumb
                        revision={thumbnailRevision(cacheRevision, coverRevisions[row.path] ?? "")}
                        path={row.path}
                        failed={row.status === "failed"}
                        fallback
                      />
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
                <h3
                  class="truncate text-sm text-app-muted"
                >
                  {seriesGroupLabel(group.series)}
                </h3>
                <ul class="grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-3">
                  {#each group.volumes as row (row.path)}
                    <li>
                      <button
                        type="button"
                        class="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent"
                        onclick={(event) => onVolume(row.path, event)}
                      >
                        <span
                          class="block aspect-[2/3] overflow-hidden bg-app-window {selected(
                            row.path,
                          )
                            ? 'ring-2 ring-app-accent'
                            : ''}"
                        >
                          {#if row.status !== "failed"}
                            <Thumb
                              revision={thumbnailRevision(cacheRevision, coverRevisions[row.path] ?? "")}
                              path={row.path}
                              failed={false}
                            />
                          {/if}
                        </span>
                        <span
                          class="mt-1 block truncate text-xs {selected(row.path)
                            ? 'bg-app-selection'
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
      </MotionPanel>
    </main>
    <aside
      class="w-96 shrink-0 overflow-y-auto border-l border-app-border bg-app-view"
    >
      <MotionPanel identity={selectionKey(selection)} extra="min-h-full">
        <Inspector
          {anchor}
          {form}
          {formLocked}
          lines={inspectorLines}
          coverRevision={anchor ? coverRevisions[anchor.path] ?? "" : ""}
          {coverActions}
          {coverActionsDisabled}
          shortcutsDisabled={activeModal !== null}
          {onEdit}
          {onToggleLock}
          onReplaceCover={() => void runCover("replace")}
          onInsertCover={() => void runCover("insert")}
        />
      </MotionPanel>
    </aside>
  </div>
</div>

{#if placeContextMenu}
  {#key `${placeContextMenu.path}:${placeContextMenu.x}:${placeContextMenu.y}`}
    <ContextMenu
      x={placeContextMenu.x}
      y={placeContextMenu.y}
      items={[
        { id: "remove", label: "Remove folder", disabled: busy },
      ]}
      label="Folder actions"
      onDismiss={() => (placeContextMenu = null)}
      onSelect={(id) => {
        if (id === "remove") requestRemoveFolder(placeContextMenu!.path);
      }}
    >
      {#snippet icon(id)}
        {#if id === "remove"}
          <FolderMinus size={16} />
        {/if}
      {/snippet}
    </ContextMenu>
  {/key}
{/if}

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
    onCacheCleared={() => (cacheRevision += 1)}
    onSaved={(next, job) => {
      motion.setSaved(next.animate_interface);
      motion.clearPreview();
      config = next;
      provider = clampProvider(provider, next.enabled_providers);
      applyTheme(
        document.documentElement,
        next.theme,
        window.matchMedia("(prefers-color-scheme: dark)").matches,
        systemTheme,
      );
      settingsOpen = false;
      if (job) watch(job);
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
