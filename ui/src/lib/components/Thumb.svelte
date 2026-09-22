<script lang="ts">
  import { Book } from "lucide-svelte";

  let {
    path,
    failed,
    fallback = false,
  }: {
    path: string;
    failed: boolean;
    fallback?: boolean;
  } = $props();

  let url = $state<string | null>(null);
  let missing = $state(false);

  $effect(() => {
    const currentPath = path;
    const skip = failed;
    url = null;
    if (skip) {
      missing = true;
      return;
    }
    missing = false;
    let cancelled = false;
    let objectUrl: string | null = null;
    void fetch(`/api/thumbnail?path=${encodeURIComponent(currentPath)}`).then(
      async (response) => {
        const type = response.headers.get("content-type") ?? "";
        if (cancelled) return;
        if (!response.ok || !type.includes("image/jpeg")) {
          missing = true;
          return;
        }
        const blob = await response.blob();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        url = objectUrl;
      },
    );
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  });
</script>

{#if url}
  <img src={url} alt="" class="h-full w-full object-cover" />
{:else if fallback && (failed || missing)}
  <Book size={16} />
{/if}
