"use client";

import { PARADIGM_TEMPLATES, ParadigmTemplate } from "@/lib/paradigmTemplates";

export function ParadigmLibraryPanel({
  isSaving,
  onApplyTemplate
}: {
  isSaving: boolean;
  onApplyTemplate: (template: ParadigmTemplate) => Promise<void>;
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
            <button type="button" onClick={() => onApplyTemplate(template)} disabled={isSaving}>
              Apply
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

