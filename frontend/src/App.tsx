import { SuiteShell, signOut, useSuiteSession } from "@plantcraft/ui";
import { useEffect, useMemo, useState } from "react";
import { api, UNAUTHORIZED_EVENT } from "./api";
import { BatchPage } from "./BatchPage";
import { BatchesPage } from "./BatchesPage";
import { DemoBanner } from "./DemoBanner";
import { HelpView } from "./SuitePages";
import { t } from "./i18n";
import { href, navigate, usePath } from "./nav";
import { NAV, tourSteps } from "./pages";
import type { Me } from "./types";
import { ErrorBox, Loading } from "./ui";

function Route({ path }: { path: string }) {
  const [, section, id] = path.split("/").map((part) => decodeURIComponent(part));
  if (section === "batches" && id) return <BatchPage key={id} batchId={id} />;
  if (section === "help") return <HelpView pageId={id || undefined} />;
  if (!section) return <BatchesPage />;
  return <ErrorBox text={t("Page not found.")} />;
}

export function App() {
  const path = usePath();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  useSuiteSession(UNAUTHORIZED_EVENT);
  useEffect(() => {
    api.me().then(setMe).catch((err: Error) => setError(err.message));
  }, []);
  const tour = useMemo(() => (me ? () => tourSteps() : undefined), [me]);
  return <SuiteShell
    app="batchlens"
    // The short name inside the suite (app standard, D10); the frame clips the full
    // "BatchlensCraft" at the "Larger text" display size (docs/gaps.md).
    appName="Batchlens"
    subtitle={t("Synthetic demo")}
    nav={NAV.map((item) => ({ ...item, label: t(item.label) }))}
    path={path}
    href={href}
    navigate={navigate}
    user={me ? { name: me.name, role: t(me.role) } : null}
    onSignOut={() => void signOut()}
    helpTo="/help"
    version={me?.version ?? null}
    tour={tour}
  >
    <DemoBanner />
    {error ? <ErrorBox text={error} /> : me ? <Route path={path} /> : <Loading />}
  </SuiteShell>;
}
