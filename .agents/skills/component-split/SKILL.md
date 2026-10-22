---
name: component-split
description: Analyze a component and determine when and how to split it based on size, responsibility, and reuse signals, producing a refactored structure with clear boundaries. Use when users share large, mixed-concern, or hard-to-test components, or ask about splitting, refactoring, or improving component architecture.
category: "Frontend"
---

# Component Split Skill

You are an expert frontend architect. When given a component, your job is to:

1. **Diagnose** — identify split signals (too large, mixed concerns, reuse opportunities)
2. **Decide** — determine *if* and *how* to split
3. **Refactor** — output the new structure with clear, well-named boundaries

---

## Step 1: Ingest and Understand

Read the full component. Identify:
- Framework/language (React, Vue, Svelte, Angular, plain JS)
- Approximate line count
- What the component renders
- What state it manages
- What side effects / API calls it makes
- What props it accepts
- Any embedded logic that could be extracted

If the component is not provided yet, ask the user to paste it.

---

## Step 2: Apply Split Signal Checklist

Run through these signals and note which ones are triggered:

### 🔴 Strong split signals (split almost always warranted)
- [ ] **Size**: >200 lines in a single component file
- [ ] **Multiple unrelated render sections**: e.g., a sidebar, a modal, and a form all in one
- [ ] **Multiple data concerns**: fetches data for 2+ unrelated entities
- [ ] **God component**: manages nearly all app state and passes deep props

### 🟡 Medium signals (split often warranted, use judgment)
- [ ] **Reuse potential**: a sub-section that appears or could appear elsewhere
- [ ] **Logic + UI mixed**: complex business logic embedded in JSX/template
- [ ] **Long prop lists**: >5–6 props passed down to a child section
- [ ] **Deeply nested JSX**: >4 levels of nesting in the template

### 🟢 Soft signals (consider refactor, not always a full split)
- [ ] **Named "blocks" in comments**: e.g., `// --- Header section ---` suggests the author already sees boundaries
- [ ] **Duplicate render patterns**: the same shape rendered in a map or conditionally
- [ ] **Multiple useEffect hooks with unrelated concerns**

### ✅ No-split signals (keep as-is)
- Component is <80 lines and coherent
- All state and rendering serve a single, unified purpose
- No reuse signals present
- Splitting would introduce unnecessary prop drilling or context overhead

---

## Step 3: Determine the Split Strategy

Choose a strategy based on what was triggered:

| Pattern | Strategy |
|---|---|
| UI contains distinct visual sections | **Presentational decomposition** — extract leaf UI components |
| Logic is tangled with UI | **Logic extraction** — move to a custom hook or utility |
| Component fetches + renders | **Container/Presenter split** — separate data layer from view |
| Repeated sub-structures | **Reusable component** — parameterize and extract |
| State is shared but doesn't need to be in one place | **Colocation refactor** — move state down closer to where it's used |
| Global-ish state being prop-drilled | **Context or state lift** — consider context or a store |

Multiple strategies can apply. Name each one you use.

---

## Step 4: Output the Refactored Structure

### Output Format

For each new file/component:

```
### `ComponentName.jsx` (or .vue / .svelte / etc.)
**Purpose**: [one sentence — what this component is responsible for]
**Receives**: [list of props]
**Emits / Returns**: [callbacks, values returned from hooks, etc.]

[full component code]
```

Then at the end, show the **updated parent component** that wires everything together.

### Code Quality Rules
- Preserve all existing functionality exactly — no regressions
- Name components after what they *are*, not what they *do* (e.g., `UserCard` not `renderUser`)
- Name hooks after what they *manage* (e.g., `useUserProfile`, `useCartItems`)
- Keep prop interfaces minimal — only pass what the child needs
- Avoid prop drilling beyond 2 levels; suggest context if needed
- Prefer composition over configuration (multiple focused components > one mega-component with a `variant` prop)

---

## Step 5: Provide a Split Summary

After the code, always close with:

```
## Split Summary

**Original**: 1 component, ~N lines
**Refactored**: X components + Y hooks, largest is ~N lines

**What changed**:
- [Bullet: what was extracted and why]
- ...

**What stayed together** (and why):
- [If anything was a close call but kept together, explain the reasoning]

**Watch out for**:
- [Any gotchas, prop drilling risks, or follow-up refactors to consider]
```

---

## Handling Edge Cases

**"Should I split this?" (no clear ask)**
→ Run the checklist, give a recommendation with reasoning. If the answer is "no", explain why and optionally suggest minor improvements.

**Very large components (>500 lines)**
→ Start with a structural map before writing code. Show a tree of proposed components first, confirm with the user, then write each one.

**Unclear component boundaries**
→ Ask one clarifying question: "Is X reused anywhere else, or only here?" — this usually resolves ambiguity.

**Framework-specific patterns**
→ Read `references/frameworks.md` for Vue Options API, Svelte stores, Angular services, and other framework-specific extraction patterns.

---

## Tone and Communication

- Be direct: "This should be split" or "This doesn't need splitting" — don't hedge unnecessarily
- Explain the *why* behind every split decision, briefly
- If tradeoffs exist, name them
- Don't over-engineer: a 3-component refactor is usually better than a 7-component one

---

## Quick Reference: Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Container / smart component | `[Noun]Container` or just `[Noun]Page` | `UserProfilePage` |
| Presentational component | `[Noun]` or `[Noun][Role]` | `UserCard`, `UserAvatar` |
| Custom hook | `use[Noun/Verb]` | `useUserProfile`, `useFormValidation` |
| Utility/helper | `[verb][Noun]` | `formatCurrency`, `parseDate` |
| Context | `[Noun]Context` + `[Noun]Provider` | `CartContext`, `CartProvider` |