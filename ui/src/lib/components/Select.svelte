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
  class="h-9 w-full rounded-md border bg-white px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:bg-zinc-900 dark:focus-visible:ring-blue-500 {dirty
    ? 'border-amber-600 text-amber-700 dark:border-amber-500 dark:text-amber-400'
    : 'border-zinc-200 text-zinc-900 dark:border-zinc-800 dark:text-zinc-100'} {extra}"
>
  {#each options as option (option.value)}
    <option
      value={option.value}
      class="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100"
      >{option.label}</option
    >
  {/each}
</select>
