import { useEffect, useState } from "react";
import { api } from "../api/client";
type O = { id: number; label: string; capacity_note: string; oven_type: string };
const TYPE_OPTIONS = ["盘炉", "石板"];
export default function OvensPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { api<O[]>("/ovens").then(setRows); }, []);
  async function changeType(o: O, oven_type: string) {
    setErr("");
    try {
      const updated = await api<O>(`/ovens/${o.id}`, { method: "PATCH", body: JSON.stringify({ oven_type }) });
      setRows(rows.map(r => (r.id === o.id ? updated : r)));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>炉位</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>标签</th><th>炉型</th><th>备注</th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}><td>{o.label}</td>
      <td><select value={o.oven_type} onChange={e => changeType(o, e.target.value)}>
        {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
      </select></td><td>{o.capacity_note}</td></tr>)}</tbody></table>
  </>);
}
