/**
 * React entrypoint. Mounts <App /> into #root. No routing library --
 * this is a single-screen product (Discover page: search in, activities out).
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
