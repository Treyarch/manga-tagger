<script lang="ts">
  let {
    checked = $bindable(false),
    disabled = false,
    label,
  }: {
    checked?: boolean;
    disabled?: boolean;
    label: string;
  } = $props();
</script>

<label class="flex items-center gap-2 text-sm text-zinc-900 dark:text-zinc-100">
  <input
    type="checkbox"
    {disabled}
    bind:checked
    class="size-4 accent-blue-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:accent-blue-500 dark:focus-visible:ring-blue-500"
  />
  {label}
</label>
