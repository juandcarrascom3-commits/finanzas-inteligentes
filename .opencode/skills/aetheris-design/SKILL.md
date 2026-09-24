---
name: Aetheris Design System
description: Reglas de producto y dirección estética de FINANCE/Aetheris — overlay del sistema de Design QA (identidad, tokens, contratos de navegación y honestidad de datos)
---

# Aetheris Product Rules

Overlay pequeño de conocimiento específico de producto. La metodología de auditoría,
UX y accesibilidad viven en las skills upstream (ver "Routing") — no duplicarlas aquí.

## Identidad

- FINANCE es el producto. Aetheris es su lenguaje visual y UX.
- Aetheris NO es una segunda aplicación.
- `frontend/src/**` es canónico; `frontend/aetheris-ui/src/**` es referencia read-only, no segundo producto.
- La interfaz ayuda a: entender el estado financiero, identificar qué cambió, detectar qué requiere atención, ver próximos eventos, planificar, analizar patrimonio/inversiones y acceder a evidencia.

## Unified Visual Direction

Estas ideas son UN sistema, no cinco estilos: Calm Editorial Cockpit, Swiss Analytical Workspace, Modular Analytical Workspace, Calm Command Center, Layered Spatial Finance.

Cuando una skill upstream prescriba una dirección estética que contradiga esta (p. ej. romper la grid deliberadamente, tipografía distintiva anti-por-defecto), **gobierna Aetheris**.

## Spatial Model

```
canvas → surface → elevated → floating → inspector
```

Cada nivel necesita una función. Evitar elevación/glass/floating puramente decorativos.

## Visual Identity

Preferir: oscuro sobrio; azul analítico calmado; tipografía editorial; tabular numbers; iconografía Lucide; movimiento discreto; semántica positive/negative/warning/info; contraste contenido; bordes y superficies consistentes.

Evitar: gamer; HUD; cyberpunk; glow constante; cyan/magenta dominante; gradientes decorativos excesivos; emojis como iconografía funcional; canvas animados ornamentales.

## Navigation Contract

- Sidebar = dominios principales: **Overview, Plan, Invest, Datos**.
- Dock / floating controls = acciones o contexto. Nunca segunda navegación primaria.
- Inspector / right rail = evidencia, contexto, herramientas o acciones relacionadas. Nunca decoración.

## Overview Contract

Priorizar: 1) estado actual; 2) qué cambió; 3) necesita atención; 4) próximos eventos; 5) contexto de plan/patrimonio; 6) evidencia bajo demanda. Evitar una parrilla homogénea de KPI cards.

## Data Honesty

Violación CRÍTICA: Math.random para métricas; cifras financieras hardcodeadas presentadas como reales; fixtures no etiquetados; demos que parezcan producto; gráficos ficticios; AI insights fabricados.

Estados honestos preferibles a visualizaciones inventadas: `READY / PARTIAL / STALE / EMPTY / UNEVALUABLE`.

## Token Discipline

`frontend/src/aetheris/tokens.css` es la fuente visual canónica actual. Buscar drift: hex nuevos evitables; valores Tailwind arbitrarios repetidos; sistemas paralelos de color; inline styles innecesarios; radios/spacing nuevos sin justificación; paletas legacy `finance.*` cuando exista token equivalente. No prohibir excepciones justificadas.

Reutilizar `frontend/src/aetheris/primitives.tsx` y los tokens antes de crear equivalentes.

## Density y drift

FINANCE es analítico; no exigir minimalismo vacío. La densidad debe distinguir de un vistazo: principal, secundario, evidencia, acciones. Vigilar: GENERIC DASHBOARD DRIFT, FINTECH TEMPLATE DRIFT, VISUAL FRAGMENTATION, DECORATIVE COMPLEXITY, DENSITY COLLAPSE, EMPTY PREMIUM.

## Preservation

Marcar como PRESERVAR lo que: funciona; usa datos reales; tiene buena jerarquía; respeta tokens; resuelve claramente su función. No rediseñar por gusto.

## Routing (una responsabilidad por tema)

| Tema | Skill |
| --- | --- |
| Identidad, tokens, contratos de producto | **esta skill** (`aetheris-design`) |
| Metodología de critique/QA, evidencia, severidad | `reviewing-interface-quality` |
| UX: flows, estados, acciones, feedback, progressive disclosure | `designing-user-experience` |
| Accesibilidad práctica y WCAG | `building-accessible-interfaces` |

No duplicar aquí lo que cubre una skill upstream.
