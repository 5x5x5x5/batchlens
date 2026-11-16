import { tourClosing, tt, type ShellNavItem, type TourStep } from "@plantcraft/ui";
import { FlaskConical } from "lucide-react";

/** The app's own pages in the suite frame (app standard, section 10); Help is the frame's own entry.
 * Batches holds the list and each batch's page (`/batches/<id>`). */
export const NAV: Array<Omit<ShellNavItem, "label"> & { label: string }> = [
  {
    to: "/",
    label: "Batches",
    icon: <FlaskConical />,
    match: (path) => path === "/" || path.startsWith("/batches/"),
  },
];

/** The app's guided tour (@plantcraft/ui): opens the first time a person opens the app. */
export function tourSteps(): TourStep[] {
  return [
    {
      title: tt("Welcome to BatchLens"),
      body: tt("BatchLens follows synthetic antibody batches from cell culture to Protein A capture. Everything here is a demonstration: synthetic data, non-GxP."),
    },
    {
      path: "/",
      target: ".pcs-content table",
      title: tt("Batches"),
      body: tt("Each batch with its bioreactor and its window. Open one to see its phases, its metrics beside the reference batch, and where each number comes from."),
    },
    tourClosing(),
  ];
}
