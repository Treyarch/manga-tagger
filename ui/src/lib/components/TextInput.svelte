<script lang="ts">
  let {
    value,
    placeholder = "",
    disabled = false,
    id = undefined,
    label = undefined,
    dirty = false,
    extra = "",
    onValue,
  }: {
    value: string;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    label?: string;
    dirty?: boolean;
    extra?: string;
    onValue?: (value: string) => void;
  } = $props();
</script>

<input
  {id}
  {value}
  {placeholder}
  {disabled}
  aria-label={label}
  oninput={(event) => onValue?.((event.currentTarget as HTMLInputElement).value)}
  class="h-9 w-full rounded-md border bg-app-view px-2 text-sm placeholder:text-app-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-accent disabled:cursor-not-allowed disabled:opacity-60 {dirty
    ? 'border-app-dirty text-app-dirty'
    : 'border-app-border text-app-text'} {extra}"
/>
