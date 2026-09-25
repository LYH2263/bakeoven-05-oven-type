import { useEffect, useState } from "react";
import { api } from "../api/client";
import { OVEN_TYPE_LABELS, type OvenType } from "../api/ovenType";

type P = { id: number; name: string; ferment_min: number; bake_min: number; oven_type: OvenType };

export default function ProductsPage() {
  const [rows, setRows] = useState<P[]>([]);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const reload = () => api<P[]>("/products").then(setRows);
  useEffect(() => { reload().catch(() => {}); }, []);

  async function changeType(p: P, oven_type: OvenType) {
    setErr("");
    const prev = rows;
    setRows(rs => rs.map(r => r.id === p.id ? { ...r, oven_type } : r));
    setSavingId(p.id);
    try {
      await api(`/products/${p.id}`, { method: "PATCH", body: JSON.stringify({ oven_type }) });
    } catch (e) {
      setRows(prev);
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingId(null);
    }
  }

  return (<>
    <h2>产品（配方时长）</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>发酵 min</th><th>烘烤 min</th><th>合计</th><th>可进炉型</th></tr></thead>
    <tbody>{rows.map(p => <tr key={p.id}>
      <td>{p.name}</td>
      <td className="mono">{p.ferment_min}</td>
      <td className="mono">{p.bake_min}</td>
      <td className="mono">{p.ferment_min + p.bake_min}</td>
      <td>
        <select
          value={p.oven_type}
          disabled={savingId === p.id}
          onChange={e => changeType(p, e.target.value as OvenType)}
          title="该产品可进入的炉型"
        >
          {Object.entries(OVEN_TYPE_LABELS).map(([v, label]) =>
            <option key={v} value={v}>{label}</option>)}
        </select>
        {savingId === p.id && <span className="hint"> 保存中…</span>}
      </td>
    </tr>)}</tbody></table>
  </>);
}
