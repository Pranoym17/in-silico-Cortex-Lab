"use client";

import { FormEvent, useState } from "react";
import { StimulusBlock } from "@/lib/api";
import { getConditionColor, getConditionSummaries } from "@/lib/builderConditions";

export function ConditionsPanel({
  blocks,
  isSaving,
  onRenameCondition
}: {
  blocks: StimulusBlock[];
  isSaving: boolean;
  onRenameCondition: (from: string, to: string) => Promise<void>;
}) {
  const summaries = getConditionSummaries(blocks);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!from.trim() || !to.trim()) {
      return;
    }

    await onRenameCondition(from.trim(), to.trim());
    setFrom("");
    setTo("");
  }

  return (
    <section className="panel stack">
      <h2>Conditions</h2>
      {summaries.length === 0 ? <p>No conditions yet.</p> : null}
      <div className="condition-list">
        {summaries.map((condition) => (
          <div className="condition-row" key={condition.name}>
            <span className="condition-swatch" style={{ background: getConditionColor(condition.name) }} />
            <span>{condition.name}</span>
            <span>{condition.count}</span>
          </div>
        ))}
      </div>
      <form className="condition-form" onSubmit={handleSubmit}>
        <input aria-label="Condition to rename" onChange={(event) => setFrom(event.target.value)} placeholder="from" value={from} />
        <input aria-label="New condition name" onChange={(event) => setTo(event.target.value)} placeholder="to" value={to} />
        <button type="submit" disabled={isSaving || !from.trim() || !to.trim()}>
          Rename
        </button>
      </form>
    </section>
  );
}

