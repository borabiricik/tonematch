import * as React from "react";
import { createRoot } from "react-dom/client";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/app.css";
import { App } from "./app/App";
import { initCli } from "./cli";

await initCli();
createRoot(document.getElementById("root")!).render(<App />);
