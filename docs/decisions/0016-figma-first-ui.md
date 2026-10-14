# 0016: UI is designed in Figma first

**Decision:** every screen is designed in Figma (by the owner, or drafted by Claude through the Figma connector), then implemented with shadcn/ui. Colours, type and spacing become Tailwind theme tokens, so screens stay consistent. `apps/web/DESIGN.md` maps frames to routes and components. Figma work runs in local sessions (plugins don't load in cloud sessions) and can proceed alongside backend phases.
