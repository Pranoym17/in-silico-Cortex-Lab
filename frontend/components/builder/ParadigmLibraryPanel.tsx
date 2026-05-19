"use client";

import { PARADIGM_TEMPLATES, ParadigmTemplate } from "@/lib/paradigmTemplates";

export function ParadigmLibraryPanel({
  isSaving,
  onApplyTemplate
}: {
  isSaving: boolean;
  onApplyTemplate: (template: ParadigmTemplate, mode: "append" | "replace") => Promise<void>;
}) {
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
    </section>
  );
}
