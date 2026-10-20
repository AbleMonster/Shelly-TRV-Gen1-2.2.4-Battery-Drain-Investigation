# Security Policy

## Purpose

This repository contains independent research into the Shelly TRV Gen1 firmware, including reverse engineering, Wi-Fi power-management behavior, firmware control flow, experimental patches, and hardware testing.

Most findings in this repository are ordinary firmware-behavior or reliability findings and can be discussed publicly.

However, reverse engineering may also reveal vulnerabilities that could create a meaningful security risk to users or devices.

This policy describes how such findings should be handled.

---

## What Should Be Reported Privately

Please do **not** immediately open a public GitHub issue if a finding could enable or materially contribute to:

- Unauthorized access to a Shelly device
- Authentication or authorization bypass
- Remote code execution
- Arbitrary firmware modification
- Firmware-signature or integrity-check bypass
- Unauthorized extraction of credentials or secrets
- Exposure of Wi-Fi credentials
- Exposure of authentication tokens or cryptographic material
- Unauthorized control of a device
- Network compromise through a Shelly device
- Exploitation of the WF200 communication interface
- Memory corruption with plausible security impact
- A remotely triggerable denial of service with meaningful security consequences
- Circumvention of an established security boundary
- Any other behavior that could reasonably put users, devices, or networks at risk

For such findings, please use GitHub's private security reporting functionality where available.

If private security reporting is not available, contact the repository maintainer privately before publishing technical exploitation details.

---

## What Can Normally Be Reported Publicly

Ordinary firmware bugs, reliability problems, and research findings can generally be reported through normal GitHub issues.

Examples include:

- Battery drain
- Unexpected power-management behavior
- Beacon handling anomalies
- Incorrect recovery behavior
- Firmware state-machine inconsistencies
- Diagnostic-counter behavior
- Reproducible crashes without identified security impact
- Firmware comparison results
- Hardware test results
- Reverse-engineering corrections
- Documentation errors
- Experimental observations

The existence of a firmware bug does not automatically make it a security vulnerability.

If the security impact is uncertain, prefer private disclosure until the impact can be evaluated.

---

## Reporting a Security Issue

A useful private security report should include, where applicable:

- Affected device
- Firmware version
- Firmware build identifier
- Firmware hash
- Affected component
- Relevant function or instruction addresses
- Reproduction conditions
- Reproduction steps
- Expected behavior
- Observed behavior
- Potential security impact
- Whether physical or network access is required
- Whether authentication is required
- Relevant logs or focused technical evidence
- Suggested mitigation, if known

Clearly distinguish between directly demonstrated behavior and suspected security impact.

A possible exploit scenario should not be presented as confirmed unless it has actually been demonstrated.

---

## Evidence and Reproducibility

Security findings should follow the same evidence standards as the rest of the research project.

Where appropriate, distinguish between:

- **PROVEN** — directly demonstrated by reproducible evidence
- **STRONGLY SUPPORTED** — multiple pieces of evidence support the conclusion, but part of the chain remains indirect
- **INFERENCE** — technically plausible but not directly demonstrated
- **UNKNOWN** — available evidence is insufficient

A firmware defect may be proven while its security impact remains an inference.

Please preserve that distinction.

---

## Responsible Disclosure

When a finding affects Shelly firmware, Silicon Labs components, or another third-party component, the appropriate vendor should be given a reasonable opportunity to investigate the issue before exploitation details are published.

Depending on the affected component, coordinated disclosure may involve:

- Shelly
- Silicon Labs
- Another upstream software or component vendor

Public disclosure should balance reproducibility and technical transparency against unnecessary risk to users.

Once an issue has been addressed, or sufficient time for coordinated disclosure has passed, technical documentation may be published where appropriate.

---

## Firmware and Copyrighted Material

Do **not** include proprietary firmware binaries in security reports, issues, or pull requests unless a private and legally appropriate method of sharing them has been explicitly agreed upon.

Do not publicly submit:

- Original Shelly firmware binaries
- Complete extracted proprietary firmware images
- Complete patched Shelly firmware images
- Proprietary GBL firmware images
- Large unnecessary proprietary disassembly dumps
- Proprietary SDK material that cannot legally be redistributed
- Files obtained from unauthorized sources

Where necessary, use focused technical information such as:

- Firmware hashes
- Addresses
- Small byte sequences
- Small instruction sequences
- Control-flow descriptions
- Focused disassembly excerpts
- Reproduction procedures

This should be sufficient to identify and investigate most findings without redistributing complete proprietary firmware.

---

## Sensitive Information

Before publishing logs, captures, screenshots, or diagnostic data, remove information that is not necessary for reproducing the finding.

This includes:

- Passwords
- Authentication tokens
- API keys
- Wi-Fi credentials
- Private keys
- Cloud credentials
- Device identifiers where unnecessary
- MAC addresses where unnecessary
- Local network information where unnecessary
- Personal information
- Other secrets

Do not publish secrets merely because they were discovered during reverse engineering or diagnostic logging.

---

## Experimental Firmware

Firmware modifications documented by this project are experimental unless explicitly stated otherwise.

Experimental patches may alter device behavior and should be tested only on devices where the tester understands and accepts the associated risk.

A patch that appears to improve battery life or reliability should not automatically be considered safe or correct.

Firmware modifications should be supported by technical evidence and appropriate verification.

---

## Scope of This Repository

This repository investigates firmware behavior and documents independently obtained technical findings.

The repository is not the official security contact for:

- Shelly
- Silicon Labs
- WF200
- Third-party libraries
- Cloud infrastructure operated by other organizations

Security vulnerabilities in those products ultimately need to be addressed by the responsible vendor.

This repository may document such findings after appropriate responsible-disclosure considerations have been satisfied.

---

## Research Integrity

Do not exaggerate the security significance of a firmware finding.

A defect affecting power management, reliability, state handling, or battery consumption is not a security vulnerability unless a meaningful security impact can be demonstrated or reasonably supported.

Likewise, the absence of a demonstrated exploit does not prove that a defect has no security implications.

Document what is known, what is supported by evidence, and what remains uncertain.

---

## Final Principle

The purpose of responsible disclosure is to allow technically important findings to be investigated and documented without unnecessarily increasing risk to users.

When uncertain whether a newly discovered behavior has meaningful security implications, disclose it privately first and evaluate the impact before publishing exploitation details.