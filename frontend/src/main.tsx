import { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles/index.css";
import Nav from "./components/Nav";

const Story = lazy(() => import("./story/Story"));
const Console = lazy(() => import("./console/Console"));
const Report = lazy(() => import("./report/Report"));

// No StrictMode: its dev-only double mount leaves react-force-graph-3d's ref on the discarded first
// instance, so the case-file camera frames an empty scene. Production builds are unaffected either way.
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Nav />
    <Suspense fallback={null}>
      <Routes>
        <Route path="/" element={<Story />} />
        <Route path="/case" element={<Console />} />
        <Route path="/report" element={<Report />} />
        <Route path="*" element={<Story />} />
      </Routes>
    </Suspense>
  </BrowserRouter>,
);
