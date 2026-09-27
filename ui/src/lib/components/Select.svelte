<script lang="ts">
  let {
    value,
    options,
    disabled = false,
    label = undefined,
    dirty = false,
    extra = "",
    onValue,
  }: {
    value: string;
    options: { value: string; label: string }[];
    disabled?: boolean;
    label?: string;
    dirty?: boolean;
    extra?: string;
    onValue?: (value: string) => void;
  } = $props();
</script>

<select
  {value}
  {disabled}
  aria-label={label}
  onchange={(event) => onValue?.((event.currentTarget as HTMLSelectElement).value)}
  class="h-9 w-full rounded-md border bg-app-view px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed disabled:opacity-60 {dirty
    ? 'border-app-dirty text-app-dirty'
    : 'border-app-border text-app-text'} {extra}"
>
  {#each options as option (option.value)}
    <option
      value={option.value}
      class="bg-app-view text-app-text"
      >{option.label}</option
    >
  {/each}
</select>
