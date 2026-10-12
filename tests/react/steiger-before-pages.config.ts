// The Steiger configuration of the CI job "React golden project" while the
// golden project has no folder src/pages. Until the pages story (#174), no
// page or widget refers to the entity slices. Thus the rule
// fsd/insignificant-slice is off. All other recommended rules stay on.
import fsd from "@feature-sliced/steiger-plugin";
import { defineConfig } from "steiger";

export default defineConfig([
  ...fsd.configs.recommended,
  { rules: { "fsd/insignificant-slice": "off" } },
]);
