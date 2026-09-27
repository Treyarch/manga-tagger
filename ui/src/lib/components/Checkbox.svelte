<script lang="ts">
  let {
    checked = $bindable(false),
    disabled = false,
    label,
    hideLabel = false,
  }: {
    checked?: boolean;
    disabled?: boolean;
    label: string;
    hideLabel?: boolean;
  } = $props();
</script>

<label
  class="inline-flex items-center gap-2 text-sm text-app-text {disabled
    ? 'opacity-40'
    : 'cursor-pointer'}"
>
  <span class="relative inline-flex size-4 shrink-0 items-center justify-center">
    <input
      type="checkbox"
      {disabled}
      bind:checked
      aria-label={hideLabel ? label : undefined}
      class="peer size-4 appearance-none rounded border border-app-strong-border bg-app-view checked:border-app-accent checked:bg-app-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed"
    />
    <svg
      class="pointer-events-none absolute size-3 text-app-on-accent opacity-0 peer-checked:opacity-100"
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M2.5 6.2 4.8 8.5 9.5 3.5"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </span>
  {#if !hideLabel}
    {label}
  {/if}
</label>
