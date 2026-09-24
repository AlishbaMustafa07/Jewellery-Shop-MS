import { Button, Loading } from "./ui";

/**
 * columns: [{ key, label, render?(row), num?, className?, sort? (ordering field) , footer? }]
 * data: DRF paginated response {count, results} or a plain array.
 */
export default function DataTable({
  columns, data, loading, onRowClick, rowClass, page, setPage, pageSize = 50, ordering, setOrdering,
  footer, empty = "Nothing to show yet.", selectable, selected, setSelected,
}) {
  const rows = Array.isArray(data) ? data : data?.results || [];
  const count = Array.isArray(data) ? rows.length : data?.count ?? rows.length;
  const pages = Math.max(1, Math.ceil(count / pageSize));

  const toggleSort = (field) => {
    if (!setOrdering || !field) return;
    setOrdering(ordering === field ? `-${field}` : ordering === `-${field}` ? "" : field);
  };
  const allSelected = selectable && rows.length > 0 && rows.every((r) => selected?.has(r.id));
  const toggleAll = () => {
    const next = new Set(selected);
    rows.forEach((r) => (allSelected ? next.delete(r.id) : next.add(r.id)));
    setSelected(next);
  };
  const toggleOne = (id) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  return (
    <div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              {selectable && (
                <th style={{ width: 32 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all" />
                </th>
              )}
              {columns.map((c) => (
                <th key={c.key} className={`${c.num ? "num" : ""} ${c.sort ? "sortable" : ""} ${c.className || ""}`}
                  onClick={() => toggleSort(c.sort)}>
                  {c.label}
                  {c.sort && ordering === c.sort && " ▲"}
                  {c.sort && ordering === `-${c.sort}` && " ▼"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && !rows.length ? (
              <tr><td colSpan={columns.length + (selectable ? 1 : 0)}><Loading /></td></tr>
            ) : !rows.length ? (
              <tr><td colSpan={columns.length + (selectable ? 1 : 0)} className="empty">{empty}</td></tr>
            ) : (
              rows.map((row, i) => (
                <tr key={row.id ?? i} className={`${onRowClick ? "clickable" : ""} ${rowClass?.(row) || ""}`}
                  onClick={() => onRowClick?.(row)}>
                  {selectable && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={selected?.has(row.id) || false} onChange={() => toggleOne(row.id)}
                        aria-label="Select row" />
                    </td>
                  )}
                  {columns.map((c) => (
                    <td key={c.key} className={`${c.num ? "num" : ""} ${c.className || ""}`}>
                      {c.render ? c.render(row) : row[c.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
          {footer && (
            <tfoot>
              <tr>
                {selectable && <td />}
                {columns.map((c) => (
                  <td key={c.key} className={c.num ? "num" : ""}>{footer[c.key] ?? ""}</td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {setPage && count > pageSize && (
        <div className="pager">
          <span>{count.toLocaleString()} records</span>
          <div className="spacer" />
          <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Prev</Button>
          <span>Page {page} of {pages}</span>
          <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next ›</Button>
        </div>
      )}
      {setPage && count <= pageSize && count > 0 && <div className="pager">{count.toLocaleString()} records</div>}
    </div>
  );
}
