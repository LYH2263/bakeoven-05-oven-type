import { useEffect, useState } from "react";
import { api } from "../api/client";
import { OVEN_TYPE_LABELS, type OvenType } from "../api/ovenType";

type O = { id: number; label: string; capacity_note: string; oven_type: OvenType };

export default function OvensPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const reload = () => api<O[]>("/ovens").then(setRows);
  useEffect(() => { reload().catch(() => {}); }, []);

  async function changeType(o: O, oven_type: OvenType) {
    setErr("");
    const prev = rows;
    setRows(rs => rs.map(r => r.id === o.id ? { ...r, oven_type } : r));
    setSavingId(o.id);
    try {
      await api(`/ovens/${o.id}`, { method: "PATCH", body: JSON.stringify({ oven_type }) });
    } catch (e) {
      setRows(prev);
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingId(null);
    }
  }

  return (<>
    <h2>炉位</h2>
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>标签</th><th>备注</th><th>炉型</th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}>
      <td>{o.label}</td>
      <td>{o.capacity_note}</td>
      <td>
        <select
          value={o.oven_type}
          disabled={savingId === o.id}
          onChange={e => changeType(o, e.target.value as OvenType)}
          title="炉位自身的炉型"
        >
          {Object.entries(OVEN_TYPE_LABELS).map(([v, label]) =>
            <option key={v} value={v}>{label}</option>)}
        </select>
        {savingId === o.id && <span className="hint"> 保存中…</span>}
      </td>
    </tr>)}</tbody></table>
  </>);
}
