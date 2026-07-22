// Pure derivation of the alert detail pane's policy line — pulled out so the
// linked/unlinked framing is unit-testable without a DOM/component-testing
// setup, matching this package's existing convention.
export function describePolicy(policyName: string | null | undefined): string {
  return policyName ? `Triggered policy: ${policyName}.` : "Not linked to a specific policy.";
}
