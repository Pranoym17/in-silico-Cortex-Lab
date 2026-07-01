"use client";

import { useMemo, useState } from "react";
import { PARADIGM_TEMPLATES, ParadigmTemplate } from "@/lib/paradigmTemplates";
import {
  assetBlock,
  searchStimulusAssets,
  STIMULUS_CATEGORIES,
  StimulusAsset
} from "@/lib/stimulusCatalog";

export function ParadigmLibraryPanel({
  isSaving,
  onApplyTemplate
}: {
  isSaving: boolean;
  onApplyTemplate: (template: ParadigmTemplate, mode: "append" | "replace") => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const matchingAssets = useMemo(
    () => searchStimulusAssets(query, category).slice(0, 12),
    [category, query]
  );

  function addAsset(asset: StimulusAsset) {
    return onApplyTemplate(
      {
        slug: `asset-${asset.id}`,
        name: asset.title,
        description: asset.attribution,
        blocks: [assetBlock(asset, 0, asset.tags[0] ?? asset.category)]
      },
      "append"
    );
  }

  return (
    <section className="panel stack">
      <h2>Templates</h2>
      <div className="template-list">
        {PARADIGM_TEMPLATES.map((template) => (
          <article className="template-row" key={template.slug}>
            <div>
              <h3>{template.name}</h3>
              <p>{template.description}</p>
            </div>
            <div className="template-actions">
              <button type="button" onClick={() => onApplyTemplate(template, "append")} disabled={isSaving}>
                Append
              </button>
              <button type="button" onClick={() => onApplyTemplate(template, "replace")} disabled={isSaving}>
                Replace
              </button>
            </div>
          </article>
        ))}
      </div>
      <div className="stimulus-catalog">
        <div className="toolbar">
          <h3>Stimulus catalog</h3>
          <span>{matchingAssets.length} shown</span>
        </div>
        <div className="catalog-filters">
          <input
            aria-label="Search stimulus catalog"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search stimuli"
            type="search"
            value={query}
          />
          <select aria-label="Stimulus category" onChange={(event) => setCategory(event.target.value)} value={category}>
            <option value="all">All categories</option>
            {STIMULUS_CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="stimulus-grid">
          {matchingAssets.map((asset) => (
            <article className="stimulus-item" key={asset.id}>
              {asset.modality === "image" ? (
                <img alt={asset.title} src={asset.public_path} />
              ) : (
                <audio aria-label={`${asset.title} preview`} controls preload="none" src={asset.public_path} />
              )}
              <strong>{asset.title}</strong>
              <span>{asset.category}</span>
              <button disabled={isSaving} onClick={() => addAsset(asset)} type="button">
                Add
              </button>
              <details>
                <summary>Attribution</summary>
                <p>{asset.attribution}</p>
                <a href={asset.license_url} rel="noreferrer" target="_blank">
                  {asset.license}
                </a>
              </details>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
