<script lang="ts">
  let {
    value,
    placeholder = "",
    disabled = false,
    id = undefined,
    label = undefined,
    rows = 4,
    dirty = false,
    extra = "",
    onValue,
  }: {
    value: string;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    label?: string;
    rows?: number;
    dirty?: boolean;
    extra?: string;
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
  class="w-full rounded-md border bg-white px-2 py-1.5 text-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:bg-zinc-900 dark:placeholder:text-zinc-400 dark:focus-visible:ring-blue-500 {dirty
    ? 'border-amber-600 text-amber-700 dark:border-amber-500 dark:text-amber-400'
    : 'border-zinc-200 text-zinc-900 dark:border-zinc-800 dark:text-zinc-100'} {extra}"
></textarea>
