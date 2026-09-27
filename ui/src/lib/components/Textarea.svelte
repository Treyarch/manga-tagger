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
  class="w-full rounded-md border bg-app-view px-2 py-1.5 text-sm placeholder:text-app-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed disabled:opacity-60 {dirty
    ? 'border-app-dirty text-app-dirty'
    : 'border-app-border text-app-text'} {extra}"
></textarea>
