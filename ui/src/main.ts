import { mount } from "svelte";
import App from "./App.svelte";
import { getAppVersion, getConfig, getSystemTheme } from "./lib/api";
import { applyTheme } from "./lib/theme";
import "./app.css";
import { motion } from "./lib/motion";

const [config, systemTheme, appVersion] = await Promise.all([
  getConfig(),
  getSystemTheme().catch(() => null),
  getAppVersion(),
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
if (target) mount(App, { target, props: { initialConfig: config, initialSystemTheme: systemTheme, appVersion } });
