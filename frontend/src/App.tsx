/**
 * Root component. Holds ConstraintForm state, calls the backend via
 * api/client.ts on submit, and renders an ActivityCard per recommendation
 * (or an empty/uncertain state -- per principle #3, expect 1-3 results,
 * not a catalog).
 */

// TODO: wire ConstraintForm -> postRecommendations() -> ActivityCard list.
