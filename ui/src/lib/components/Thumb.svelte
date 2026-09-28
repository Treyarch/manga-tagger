<script lang="ts">
  import { Book } from "lucide-svelte";
  import { thumbnailSrc } from "../library";

  let {
    path,
    failed,
    fallback = false,
    revision = "",
  }: {
    path: string;
    failed: boolean;
    fallback?: boolean;
    revision?: string;
  } = $props();

  let broken = $state(false);

  const src = $derived(failed ? "" : thumbnailSrc(path, revision));
  const showImage = $derived(src !== "" && !broken);
  const showFallback = $derived(fallback && (failed || broken || src === ""));

  $effect(() => {
    src;
    broken = false;
  });
</script>

{#if showImage}
  <img
    src={src}
    alt=""
    class="h-full w-full object-cover"
    loading="lazy"
    decoding="async"
    onerror={() => (broken = true)}
  />
{:else if showFallback}
  <Book size={16} />
{/if}
