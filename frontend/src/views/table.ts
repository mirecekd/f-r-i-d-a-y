// frontend/src/views/table.ts
import "./content.css";
import { el } from "./dom";
import type { Renderer } from "./types";

type Cell = string | number | boolean | null;

function compare(a: Cell, b: Cell): number {
  const na = typeof a === "number" ? a : Number(a);
  const nb = typeof b === "number" ? b : Number(b);
  if (a !== null && b !== null && a !== "" && b !== "" && !isNaN(na) && !isNaN(nb)) return na - nb;
  return String(a ?? "").localeCompare(String(b ?? ""), undefined, { numeric: true });
}

/** data: `{columns: string[], rows: (string|number|boolean|null)[][]}`; click a header to sort. */
export const renderTable: Renderer = (body, data) => {
  const columns: string[] = Array.isArray(data?.columns) ? data.columns.map(String) : [];
  const rows: Cell[][] = Array.isArray(data?.rows) ? data.rows : [];
  if (!columns.length) throw new Error("table: columns missing");
  let sortCol = -1;
  let dir = 1;

  const table = el("table", "v-table");
  const thead = el("thead");
  const tbody = el("tbody");
  const headRow = el("tr");
  const ths = columns.map((c, i) => {
    const th = el("th", "", c);
    th.onclick = () => {
      dir = sortCol === i ? -dir : 1;
      sortCol = i;
      paint();
    };
    headRow.append(th);
    return th;
  });

  function paint(): void {
    const sorted = sortCol < 0 ? rows : [...rows].sort((a, b) => dir * compare(a[sortCol], b[sortCol]));
    ths.forEach((th, i) => th.setAttribute("data-sort", i === sortCol ? (dir > 0 ? "asc" : "desc") : ""));
    tbody.replaceChildren(
      ...sorted.map((r) => {
        const tr = el("tr");
        columns.forEach((_, i) => {
          const v = Array.isArray(r) ? r[i] : undefined;
          const td = el("td", typeof v === "number" ? "num" : "", v === null || v === undefined ? "" : String(v));
          tr.append(td);
        });
        return tr;
      }),
    );
  }

  thead.append(headRow);
  table.append(thead, tbody);
  body.append(table);
  paint();
};
