const pkrFmt = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 0 });
const numFmt2 = new Intl.NumberFormat("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const numFmt4 = new Intl.NumberFormat("en-PK", { minimumFractionDigits: 3, maximumFractionDigits: 4 });

export const toNum = (v) => {
  if (v === null || v === undefined || v === "") return 0;
  const n = typeof v === "number" ? v : parseFloat(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
};

/** PKR with thousands separators, rounded to the rupee. */
export const pkr = (v, withSymbol = false) => {
  if (v === null || v === undefined || v === "") return "—";
  const s = pkrFmt.format(Math.round(toNum(v)));
  return withSymbol ? `Rs ${s}` : s;
};

/** Weights: stored to 3 dp, displayed to 2. */
export const wt = (v) => (v === null || v === undefined || v === "" ? "—" : numFmt2.format(toNum(v)));
export const pasa = (v) => (v === null || v === undefined || v === "" ? "—" : numFmt4.format(toNum(v)));

/** DD/MM/YYYY */
export const date = (v) => {
  if (!v) return "—";
  const s = String(v);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  return s;
};

export const dateTime = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

/** Today in local time as YYYY-MM-DD (what <input type=date> and the API expect). */
export const todayISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

export const monthStartISO = () => todayISO().slice(0, 8) + "01";

export const label = (s) =>
  String(s || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
