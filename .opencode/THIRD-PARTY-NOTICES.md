# Third-Party Notices — Design QA skills

Los siguientes archivos son copias sin modificar de skills upsteam, utilizadas bajo licencia MIT:

- **Origen:** https://github.com/osmontero/opencode-skills
- **Commit inspeccionado:** `05809ed` (main, 2026-09-14)
- **Licencia:** MIT — Copyright (c) 2026 Osmany Montero (texto completo en `skills/LICENSE-osmontero-opencode-skills.txt`)

## Skills vendorizadas (project-local)

| Archivo | Responsabilidad |
| --- | --- |
| `skills/reviewing-interface-quality/SKILL.md` | Metodología de critique/QA de interfaces y severidad |
| `skills/designing-user-experience/SKILL.md` | UX: flows, estados, forms, feedback |
| `skills/designing-user-experience/references/flow-patterns.md` | Referencia requerida por la skill anterior |
| `skills/building-accessible-interfaces/SKILL.md` | Accesibilidad práctica y WCAG 2.2 AA |

Los contenidos de las tres skills están íntegros y sin mutilar (upstream los declara
originales de dicho repositorio bajo MIT).

## No vendorizado en esta fase

- `agents/interface-reviewer.md` — solo referencia estructural; el reviewer local
  `.opencode/agents/aetheris-design-reviewer.md` mantiene la frontera de seguridad.
- Colección completa de 35 skills, scripts `install.sh`/`install.ps1`, benchmarks,
  datasets y demás agentes: fuera de alcance.

## Skill de referencia externa (no instalada)

- `microsoft/skills` → `.github/skills/frontend-design-review/SKILL.md`
  (referencia metodológica: design-system compliance, insight-to-action,
  action hierarchy, trustworthy errors; sus recomendaciones creativas
  —grid-breaking, texturas, gradientes— NO se heredan: Aetheris define su dirección).
