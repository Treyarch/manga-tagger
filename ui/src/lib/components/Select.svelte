<script lang="ts">
  let {
    value,
    options,
    disabled = false,
    label = undefined,
    onValue,
  }: {
    value: string;
    options: { value: string; label: string }[];
    disabled?: boolean;
    label?: string;
    onValue?: (value: string) => void;
  } = $props();
</script>

<select
  {value}
  {disabled}
  aria-label={label}
  onchange={(event) => onValue?.((event.currentTarget as HTMLSelectElement).value)}
  class="h-9 w-full rounded-md border border-zinc-200 bg-white px-2 text-sm text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:focus-visible:ring-blue-500"
>
  {#each options as option (option.value)}
    <option
      value={option.value}
      class="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100"
      >{option.label}</option
    >
  {/each}
</select>
