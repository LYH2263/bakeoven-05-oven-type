import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string; ferment_min: number; bake_min: number; oven_types: string };
const TYPE_OPTIONS = ["盘炉", "石板", "盘炉,石板"];
export default function ProductsPage() {
  const [rows, setRows] = useState<P[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { api<P[]>("/products").then(setRows); }, []);
  async function changeTypes(p: P, oven_types: string) {
    setErr("");
    try {
      const updated = await api<P>(`/products/${p.id}`, { method: "PATCH", body: JSON.stringify({ oven_types }) });
      setRows(rows.map(r => (r.id === p.id ? updated : r)));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>产品（配方时长）</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>发酵 min</th><th>烘烤 min</th><th>合计</th><th>可进炉型</th></tr></thead>
    <tbody>{rows.map(p => <tr key={p.id}><td>{p.name}</td><td className="mono">{p.ferment_min}</td><td className="mono">{p.bake_min}</td><td className="mono">{p.ferment_min + p.bake_min}</td>
      <td><select value={p.oven_types} onChange={e => changeTypes(p, e.target.value)}>
        {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t.replace(",", " + ")}</option>)}
      </select></td></tr>)}</tbody></table>
  </>);
}
