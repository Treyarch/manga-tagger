<script lang="ts">
  import { onMount, untrack, type Snippet } from "svelte";
  import { createContentMotion } from "../motion";

  let { identity, y = 12, children, extra = "", contentClass = "flow-root" }: {
    identity: unknown;
    y?: number;
    children: Snippet;
    extra?: string;
    contentClass?: string;
  } = $props();
  let node: HTMLDivElement;
  let controller: ReturnType<typeof createContentMotion> | undefined;

  onMount(() => {
    controller = createContentMotion(node);
    return () => controller?.destroy();
  });
  $effect.pre(() => {
    identity;
    untrack(() => controller?.prepare(y));
  });
  $effect(() => {
    identity;
    untrack(() => controller?.play());
  });
</script>

<div bind:this={node} class="relative min-h-0 {extra}">
  <div class={contentClass}>{@render children()}</div>
</div>
