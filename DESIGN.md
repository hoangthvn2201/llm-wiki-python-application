---
name: Academic Intelligence Interface
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#44e2cd'
  on-secondary: '#003731'
  secondary-container: '#03c6b2'
  on-secondary-container: '#004d44'
  tertiary: '#b9c8de'
  on-tertiary: '#233143'
  tertiary-container: '#8392a6'
  on-tertiary-container: '#1c2b3c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#62fae3'
  secondary-fixed-dim: '#3cddc7'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005047'
  tertiary-fixed: '#d4e4fa'
  tertiary-fixed-dim: '#b9c8de'
  on-tertiary-fixed: '#0d1c2d'
  on-tertiary-fixed-variant: '#39485a'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-sm:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-reading:
    fontFamily: Source Serif 4
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.7'
  body-ui:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  mono-label:
    fontFamily: jetbrainsMono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 280px
  content-max-width: 850px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  stack-gap: 12px
---

## Brand & Style
The design system is rooted in the "Knowledge-First" philosophy, blending the structured rigor of a modern digital encyclopedia with the cutting-edge capabilities of retrieval-augmented generation. The goal is to move away from conversational chat interfaces and toward a sophisticated, research-oriented workspace.

The style is **Modern-Academic Minimalism** with **Glassmorphism** accents. It prioritizes information density and clarity, using a dark, high-contrast palette to reduce eye strain during long-form reading. The aesthetic evokes a sense of "digital archiving" where every piece of data is indexed, accessible, and intelligently connected. The emotional response should be one of deep focus, intellectual authority, and technical precision.

## Colors
The palette is built on a foundation of "Deep Charcoal" and "Slate Blue" to create a sense of depth and stability. The primary interaction color is **Electric Indigo** (#6366F1), symbolizing active intelligence and RAG processing. **Teal** (#2DD4BF) serves as a secondary accent for success states and citation markers.

- **Primary:** Electric Indigo for primary actions, active states, and AI-driven highlights.
- **Secondary:** Teal for knowledge verification, citations, and secondary data visualizations.
- **Surface/Neutral:** Deep Navy and Slate tones for container backgrounds and sidebar navigation.
- **Contrast:** A strict adherence to high-contrast ratios ensures that long-form academic text remains crisp against the dark backgrounds.

## Typography
This design system employs a dual-typeface strategy to distinguish between the interface and the knowledge layer.

1.  **Interface (Geist):** Used for navigation, buttons, metadata, and controls. Its technical, sharp terminals provide a "futuristic" and precise feel.
2.  **Content (Source Serif 4):** Used for the central "Wiki" or document content. This serif provides high legibility for long-form reading, grounding the application in academic tradition.

Line heights are generous (1.7 for reading) to promote focus. Monospaced elements (JetBrains Mono) are used sparingly for citations, IDs, and metadata tags to emphasize the structured nature of the data.

## Layout & Spacing
The layout follows a **Fixed-Fluid hybrid** model. 
- **Sidebar:** A fixed 280px left navigation contains the "Knowledge Tree" and workspace switching. It uses a semi-transparent glass backdrop to maintain a sense of space.
- **Main Content:** The central reading area is capped at 850px to maintain optimal line length for the serif body text, centered within the remaining viewport.
- **Secondary Panel:** An optional right-side "Inspector" panel (320px) appears for citations, AI references, and footnotes.

Spacing follows a strict 4px/8px baseline grid to ensure a tight, organized feel. Large margins (40px) are used at the top of document pages to provide visual "breathability."

## Elevation & Depth
Depth is conveyed through **Glassmorphism and Tonal Layering** rather than traditional drop shadows.

- **Level 0 (Base):** The deepest background layer (#020617).
- **Level 1 (Containers):** The primary UI containers use a slightly lighter slate (#0F172A) with a subtle 1px border (#1E293B).
- **Level 2 (Overlays):** Modals, tooltips, and floating menus utilize a translucent background (`rgba(15, 23, 42, 0.8)`) with a 12px `backdrop-filter: blur()`.
- **Accents:** Highlighted AI-generated content uses a very subtle inner glow or a faint indigo tint to the background to signify its origin.

## Shapes
The design system uses a "Rounded-Academic" approach.
- **Standard Radius:** 0.5rem (8px) for input fields and small components.
- **Container Radius:** 1rem (16px) for cards, document views, and the sidebar, creating a soft but professional frame.
- **Strictness:** Buttons and interactive elements maintain consistent 12px-16px rounding to feel "attractive" and modern, contrasting with the sharp, technical typography.

## Components
- **Buttons:** Primary buttons use a solid Electric Indigo fill with white text. Secondary buttons use a "Ghost" style with a 1px slate border that glows Indigo on hover.
- **Knowledge Cards:** Used for search results and wiki previews. They feature a subtle glass effect, teal citation counts in the corner, and Geist-based metadata labels.
- **Citations:** Inline numeric markers (e.g., [1]) in Teal. Clicking opens a glass-morphic side-peek showing the source snippet.
- **Input Fields:** Search and Query bars are prominent, using a larger 16px radius and a subtle 1px "intelligence" glow when focused.
- **Side Navigation:** Vertical list items with 4px left-accent bars for active states. Icons should be thin-stroke (1.5px) to match the Geist font weight.
- **Progressive Disclosure:** AI-generated summaries use a "typing" reveal animation or a soft fade-in to distinguish them from static wiki content.