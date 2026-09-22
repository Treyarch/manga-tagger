<script lang="ts">
  let {
    value,
    placeholder = "",
    disabled = false,
    id = undefined,
    label = undefined,
    rows = 4,
    onValue,
  }: {
    value: string;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    label?: string;
    rows?: number;
    onValue?: (value: string) => void;
  } = $props();
</script>

<textarea
  {id}
  {value}
  {placeholder}
  {disabled}
  {rows}
  aria-label={label}
  oninput={(event) => onValue?.((event.currentTarget as HTMLTextAreaElement).value)}
  class="w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-400 dark:focus-visible:ring-blue-500"
></textarea>
