import { mount } from "svelte";
import App from "./App.svelte";
import { getConfig, getSystemTheme } from "./lib/api";
import { applyTheme } from "./lib/theme";
import "./app.css";
import { motion } from "./lib/motion";

const [config, systemTheme] = await Promise.all([
  getConfig(),
  getSystemTheme().catch(() => null),
]);
motion.setSaved(config.animate_interface);
motion.setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
applyTheme(
  document.documentElement,
  config.theme,
  window.matchMedia("(prefers-color-scheme: dark)").matches,
  systemTheme,
);

const target = document.getElementById("app");
if (target) mount(App, { target, props: { initialConfig: config, initialSystemTheme: systemTheme } });
