---
name: Research finding
about: Submit a reverse-engineering finding, firmware observation, or alternative technical explanation
title: "[RESEARCH] "
labels: research
assignees: ''
---

# Research Finding

## Summary

Briefly describe the finding or hypothesis.

## Research Target

**Device:** Shelly TRV Gen1  
**Firmware version:**  
**Build:**  
**Firmware SHA256:**  

## Area

Select or describe the relevant area:

- [ ] Beacon handling
- [ ] Wi-Fi power management
- [ ] WF200 communication
- [ ] Battery drain
- [ ] Sleep / wake behavior
- [ ] Firmware scheduler
- [ ] mDNS / networking
- [ ] Recovery behavior
- [ ] Firmware comparison
- [ ] Other

## Evidence Classification

Select the strongest classification currently supported:

- [ ] PROVEN
- [ ] STRONGLY SUPPORTED
- [ ] INFERENCE
- [ ] UNKNOWN / investigation question

### Why this classification?

Explain what evidence supports the selected classification.

## Technical Evidence

Provide the relevant evidence.

Where applicable, include:

- Function addresses
- Instruction addresses
- Native instructions
- Data addresses
- Control-flow paths
- Firmware differences
- Logs
- Measurements
- Mathematical analysis
- Tool/version used

Please distinguish native evidence from decompiler interpretation.

## Observed Behavior

Describe what was directly observed or reconstructed.

## Interpretation

Explain what you believe the evidence means.

Keep interpretation separate from directly demonstrated behavior.

## Alternative Explanations

What other explanations could account for the same evidence?

## Falsification

What observation or experiment would disprove or weaken this finding?

## Reproduction

Describe how another researcher can reproduce the analysis.

## Relationship to Existing Findings

Does this:

- [ ] Confirm an existing finding
- [ ] Extend an existing finding
- [ ] Contradict an existing finding
- [ ] Propose an alternative explanation
- [ ] Describe a new area of investigation

Reference relevant issues, reports, commits, or documentation where applicable.

## Additional Notes

Add any other relevant context.

---

If this finding may represent a security vulnerability rather than an ordinary firmware bug or research result, please follow `SECURITY.md` instead of publishing sensitive exploitation details here.