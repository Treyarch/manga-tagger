import { mount } from "svelte";
import App from "./App.svelte";
import { getConfig } from "./lib/api";
import { applyDocumentClass, resolveDark } from "./lib/theme";
import "./app.css";

const config = await getConfig();
applyDocumentClass(
  document.documentElement,
  resolveDark(
    config.theme,
    window.matchMedia("(prefers-color-scheme: dark)").matches,
  ),
);

const target = document.getElementById("app");
if (target) mount(App, { target, props: { initialConfig: config } });
