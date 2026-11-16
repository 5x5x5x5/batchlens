/** `/`: every batch with its product, bioreactor, window and reference mark. */
import { useEffect, useState } from "react";
import { DataTable, Pill } from "@plantcraft/ui";
import { api } from "./api";
import { t } from "./i18n";
import type { BatchList } from "./types";
import { ErrorBox, Heading, Link, Loading, message } from "./ui";
import { NotInPlantCraft, useInstallationZone, when, ZoneNote } from "./when";

export function BatchesPage() {
  const [list, setList] = useState<BatchList | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.batches().then(setList).catch((err) => setError(message(err))); }, []);
  useInstallationZone(list?.time_zone);
  if (error) return <ErrorBox text={error} />;
  if (!list) return <Loading />;
  return <>
    <Heading title={t("Batches")} />
    {list.batches.length === 0
      ? <div className="panel"><h2>{t("No batches yet")}</h2><p className="muted">{t("Load the synthetic demo batches with the command batchlens seed-demo.")}</p></div>
      : <DataTable rows={list.batches} rowKey={(batch) => batch.batch_id} label={t("Batches")}
          searchText={(batch) => `${batch.batch_id} ${batch.product} ${batch.asset_id ?? ""} ${batch.asset_name ?? ""}`}
          initialSort={{ key: "start", descending: false }}
          columns={[
            { key: "batch", label: t("Batch"), sort: (batch) => batch.batch_id, render: (batch) => <Link to={`/batches/${encodeURIComponent(batch.batch_id)}`}>{batch.batch_id}</Link> },
            { key: "product", label: t("Product"), sort: (batch) => batch.product, render: (batch) => batch.product },
            { key: "bioreactor", label: t("Bioreactor"), sort: (batch) => batch.asset_name ?? batch.asset_id, phone: "hide",
              render: (batch) => batch.asset_name ?? <>{batch.asset_id}<NotInPlantCraft /></> },
            { key: "start", label: t("Start"), sort: (batch) => batch.start, render: (batch) => when(batch.start) },
            { key: "end", label: t("End"), sort: (batch) => batch.end, phone: "hide", render: (batch) => (batch.running ? <Pill status="good" label={t("Running now")} /> : when(batch.end)) },
            { key: "reference", label: t("Reference"), sort: (batch) => (batch.is_reference ? 0 : 1),
              render: (batch) => (batch.is_reference ? <Pill status="info" label={t("Reference")} /> : "") },
            { key: "comparable", label: t("Comparable"), sort: (batch) => (batch.is_comparable ? 0 : 1), phone: "hide",
              render: (batch) => (batch.is_comparable ? <Pill status="inactive" label={t("Comparable")} /> : "") },
          ]} />}
    <ZoneNote />
  </>;
}
