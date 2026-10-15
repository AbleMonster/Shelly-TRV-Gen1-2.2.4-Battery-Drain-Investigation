# Contributing to Shelly TRV Gen1 Battery Drain Research

Thank you for your interest in contributing to this project.

This repository investigates battery-drain behavior in the Shelly TRV Gen1, with a particular focus on firmware behavior, Wi-Fi power management, beacon handling, and related control logic.

Contributions are welcome, including independent analysis, hardware observations, documentation improvements, testing results, and tools that help make the research reproducible.

Because this project involves reverse engineering and experimental firmware modifications, contributions should clearly distinguish verified facts from interpretation.

---

## What You Can Contribute

Useful contributions include:

- Independent reverse-engineering findings
- Firmware behavior analysis
- Battery and power-consumption measurements
- Long-term test results
- Wi-Fi and WF200 behavior observations
- Reproduction of existing findings
- Documentation corrections or improvements
- Analysis scripts and research tools
- Patch review and static verification
- Hardware A/B test results
- Alternative explanations for observed behavior
- Evidence that confirms or disproves an existing hypothesis

Negative results are also useful.

If an experiment does not reproduce an expected result, please report it rather than omitting it.

---

## Research and Evidence Standards

The goal of this project is to understand the actual firmware behavior, not merely to find modifications that appear to reduce battery consumption.

When contributing research, please separate observations from interpretation.

Where appropriate, use the following evidence classifications.

### PROVEN

Directly supported by reproducible evidence such as:

- Native instructions or control flow
- Direct data-flow analysis
- Reproducible firmware behavior
- Hardware measurements
- Deterministic mathematical results
- Verified binary differences

A statement should only be classified as `PROVEN` within the scope actually demonstrated by the evidence.

### STRONGLY SUPPORTED

Multiple pieces of evidence consistently support the conclusion, but one or more links remain indirect or incomplete.

### INFERENCE

A technically plausible interpretation of the available evidence that has not yet been demonstrated directly.

### UNKNOWN

The available evidence is insufficient to determine the answer.

Please do not present an `INFERENCE` as a confirmed firmware bug or developer intention.

---

## Reverse-Engineering Contributions

Reverse-engineering findings should be reproducible wherever practical.

Please include relevant information such as:

- Device model
- Firmware version
- Firmware build identifier
- SHA256 or another appropriate hash when relevant
- Function or virtual addresses
- Instruction addresses
- Original instructions
- Relevant control-flow paths
- Data addresses and field widths
- Tool and version used
- Analysis assumptions
- Relevant logs or measurements

For firmware analysis, native instructions should be preferred over conclusions based solely on decompiler output.

Decompiler output is useful for understanding control flow, but it should not be treated as an exact representation of the original source code.

When possible, important findings should be verified against the underlying machine instructions.

---

## Firmware Identity

Firmware findings should identify the exact firmware being analyzed.

For example:

```text
Device: Shelly TRV Gen1
Firmware: 2.2.4
Build: 20240619-130912/v2.2.4@ee290818
SHA256: <hash>
```

Do not assume that behavior observed in one firmware version also exists in another version.

If comparing firmware versions, clearly identify which findings apply to which version.

---

## Firmware and Copyrighted Material

This repository is intended to contain original research, documentation, tools, and independently created patching methods.

Please do **not** submit:

- Original Shelly firmware binaries
- Complete extracted proprietary firmware images
- Modified or patched complete Shelly firmware binaries
- GBL files containing proprietary Shelly firmware
- Large raw disassembly dumps containing unnecessary proprietary code
- Proprietary SDK material that cannot legally be redistributed
- Files obtained from unauthorized sources

Instead, document the research necessary to reproduce a finding or modification from a firmware image legitimately obtained by the user.

Small instruction sequences, byte sequences, addresses, hashes, and technical excerpts may be included where necessary to document and reproduce the research.

Contributors are responsible for ensuring that material they submit can legally be redistributed.

---

## Patch Contributions

A patch should not be accepted merely because it appears to improve battery life.

Patch proposals should explain:

1. What behavior is being changed
2. What evidence shows that the original behavior is defective or undesirable
3. Why the proposed modification addresses the identified cause
4. Which original behaviors are intentionally preserved
5. Which behaviors may change as a side effect
6. How the modification was statically verified
7. How it was or should be tested on hardware

Whenever possible, prefer minimal changes over broad suppression of existing firmware mechanisms.

For example, disabling an entire recovery mechanism is not equivalent to correcting the condition that causes it to execute incorrectly.

---

## Patch Documentation

Instruction-level patch proposals should include, where applicable:

```text
Virtual address:
Application offset:
Original instruction:
Original bytes:
Replacement instruction:
Replacement bytes:
Instruction size:
Branch target:
```

Also document any assumptions concerning:

- Thumb / Thumb-2 encoding
- Alignment
- Register state
- Condition flags
- Branch range
- Literal pools
- Application-to-container offsets
- Checksums or integrity fields

Any calculated offset that has not been independently verified should be identified as such.

---

## Hardware Test Results

Hardware observations should contain enough information to understand the test conditions.

Useful information includes:

- Device identifier or anonymous test label
- Firmware version/build
- Patch variant
- Test duration
- Battery voltage
- Battery percentage where relevant
- Device uptime
- Wi-Fi signal strength
- Relevant firmware statistics
- Reboots or charging events
- Configuration changes during the test
- Measurement interval
- Test start and end times

Battery percentage alone should not be treated as a precise measurement of energy consumption.

When possible, include battery voltage and sufficiently long observation periods.

---

## A/B Testing

When comparing patched and unpatched firmware, try to keep test conditions as similar as practical.

Clearly identify:

- Control device
- Patched device
- Firmware versions
- Patch differences
- Start conditions
- Observation period
- Relevant environmental differences

Do not discard results simply because they contradict the current hypothesis.

Unexpected results are particularly valuable because they may reveal an incorrect assumption.

---

## Logs and Diagnostic Data

Before submitting logs:

- Remove passwords
- Remove authentication tokens
- Remove private API keys
- Remove Wi-Fi credentials
- Remove unnecessary personal information
- Remove other sensitive data

Local IP addresses and anonymous device labels may be useful for technical analysis, but contributors should decide whether they are necessary before publishing them.

Prefer focused log excerpts over very large unfiltered dumps.

---

## Reproducibility

Where practical, another researcher should be able to reproduce a finding using the information in the repository.

A strong contribution should answer:

- What was tested?
- On which firmware?
- How was it tested?
- What was observed?
- What conclusion follows directly from the observation?
- What remains uncertain?
- What result would falsify the conclusion?

Explicit falsification criteria are encouraged.

---

## Issues

Before opening a new issue:

- Check whether the topic is already documented
- Search existing issues
- Identify the firmware version involved
- Include reproduction steps where possible
- Include relevant logs or measurements
- Clearly distinguish observation from interpretation

Please keep one issue focused on one technical problem whenever practical.

---

## Pull Requests

Pull requests should be focused and reviewable.

A pull request should:

- Explain what is being changed
- Explain why the change is necessary
- Reference relevant research or issues
- Avoid unrelated changes
- Preserve existing documentation where possible
- Include verification or test information where relevant

For reverse-engineering findings, include enough evidence for the result to be independently reviewed.

Do not combine large documentation rewrites, unrelated research findings, and firmware patch changes into a single pull request unless they are directly dependent on each other.

---

## Challenging Existing Findings

Existing conclusions are not considered untouchable.

If you believe a documented finding is incorrect, incomplete, or based on an invalid assumption, please provide the evidence supporting your interpretation.

Good-faith attempts to falsify existing conclusions are encouraged.

The objective is to understand the firmware accurately, not to defend a particular hypothesis.

---

## Responsible Disclosure and Security

If you discover a security issue that could create a meaningful risk to users or devices, avoid publishing sensitive exploitation details immediately.

Please follow the project's security reporting process once `SECURITY.md` is available.

Do not include credentials, private keys, authentication material, or other secrets in public issues or pull requests.

---

## Code of Conduct

Participation in this project is subject to the repository's `CODE_OF_CONDUCT.md`.

Please keep technical discussions constructive, evidence-based, and respectful.

---

## Final Principle

This project distinguishes between:

**what the firmware does, what the evidence suggests it means, and what remains unknown.**

Contributions should preserve that distinction.

The purpose of the project is not simply to produce a patch that appears to work, but to understand the underlying behavior well enough to make technically defensible changes.