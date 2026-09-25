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
background → canvas → surface → elevated → floating → inspector
```

Cada nivel necesita una función y debe distinguirse perceptiblemente del anterior mediante luminosidad, borde, sombra y profundidad atmosférica.

**Dark calm ≠ near-black monotony.** Si dos niveles espaciales colapsan visualmente a casi negro, existe drift.

Evitar elevación/glass/floating puramente decorativos.

## Design DNA · V1 Amendment

### Dark calm ≠ near-black monotony

La base oscura Aetheris favorece navy / graphite / blue-gray / storm / slate.

La profundidad debe seguir:

```
background → canvas → surface → elevated → floating → inspector
```

No basta con que dos capas tengan bordes distintos: deben poseer separación perceptible.

### Financial control ≠ HTML form

Un control financiero debe comunicar **SIGNIFICADO + UNIDAD + VALOR**.

Los grids de inputs genéricos sin labels visibles son interacción legacy.

### Financial inputs

Preferir:

- label visible;
- unidad integrada visualmente;
- `tabular-nums`;
- helper contextual solo cuando aporte;
- foco perceptible sin glow.

REGLA CRÍTICA: el formato visual nunca modifica el valor canónico usado por cálculos o payloads.

Ejemplo:

```
valor canónico: 12000000
presentación:   12.000.000
payload:        12000000
```

La unidad puede aparecer como affix visual del control, pero nunca formar parte del valor emitido.

### Selection patterns

- Conjuntos pequeños y estables → `SegmentedControl`.
- Listas mayores → selector apropiado, preferiblemente nativo/adaptado antes de construir un combobox propio.

### Color semantics

- Azul → interacción / navegación / selección.
- Verde → positivo / éxito.
- Rojo → negativo / destructivo.
- Amarillo → warning / atención.

Los colores semánticos no se usan como decoración general.

### Persistent vs contextual UI

El espacio persistente es costoso.

Mantener visible cuando:

- es estado central;
- se consulta frecuentemente;
- requiere atención continua;
- forma parte natural del flujo principal.

Preferir invocación contextual cuando:

- se usa ocasionalmente;
- requiere varios campos;
- es simulación, configuración o mantenimiento;
- ocupa mucho espacio estando inactiva.

El patrón inicial preferido en workspaces compatibles es una **DOCKED CONTEXTUAL TOOL SURFACE**:

- columna contextual del workspace;
- no overlay, no modal, no backdrop, no portal, no focus trap;
- stacked/inline en mobile.

Esto es un patrón preferido, **NO** una obligación universal ni un sistema de ventanas.

### Inspector vs ToolSurface

- **Inspector** → explica, evidencia, fuente, confianza, detalle.
- **ToolSurface** → permite actuar, configurar, simular, calcular o importar.

No mezclar ambos roles.

### Motion

Discreto, corto y funcional. Respetar `prefers-reduced-motion`.

### Prohibiciones

Evitar: cyberpunk; HUD; neon; glow excesivo; glassmorphism dominante; gráficos/gauges inventados; decoración sin evidencia real.

### Abstraction discipline

`USE AS-IS` → `CONFIGURE / COMPOSE` → `ADAPT ONLY IF REQUIRED` → `BUILD ONLY IF NECESSARY`.

No crear un design system grande. Abstraer únicamente patrones realmente consumidos.

NO duplicar metodología detallada de las skills upstream.

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
