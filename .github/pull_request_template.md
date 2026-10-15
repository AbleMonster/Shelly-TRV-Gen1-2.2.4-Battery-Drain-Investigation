# Pull Request

## Summary

Describe what this pull request changes.

## Type of Change

- [ ] Documentation
- [ ] Reverse-engineering research
- [ ] Analysis tooling
- [ ] Battery/test tooling
- [ ] Patch logic
- [ ] Bug fix
- [ ] Test data / test methodology
- [ ] Repository maintenance
- [ ] Other

## Motivation

Why is this change necessary?

Reference relevant issues, research reports, findings, or test results where applicable.

## Technical Details

Describe the implementation or research changes.

For firmware-related changes, include relevant information such as:

- Firmware version/build
- Firmware SHA256
- Function/instruction addresses
- Original behavior
- Modified behavior
- Original/replacement instructions or bytes where appropriate

## Evidence

For research or firmware-behavior claims, classify the evidence where appropriate:

- [ ] PROVEN
- [ ] STRONGLY SUPPORTED
- [ ] INFERENCE
- [ ] UNKNOWN / not applicable

Explain the evidence supporting the change.

## Verification

Describe how the change was verified.

Examples:

- Static binary verification
- Independent disassembly
- Script tests
- Hardware testing
- A/B testing
- Long-term testing
- Documentation review

## Firmware / Copyright Check

I confirm that this pull request does **not** include:

- [ ] Original Shelly firmware binaries
- [ ] Complete patched Shelly firmware binaries
- [ ] Proprietary GBL firmware images
- [ ] Unnecessary large proprietary disassembly dumps
- [ ] Credentials, tokens, keys, or other secrets

If any item above cannot be confirmed, explain why before submitting the pull request.

## Side Effects / Risks

Describe known or possible side effects.

For firmware patches, explicitly state which stock behaviors are intended to remain unchanged.

## Checklist

- [ ] The change is focused and does not contain unrelated modifications.
- [ ] Relevant documentation has been updated.
- [ ] Claims are separated from assumptions or interpretation.
- [ ] Firmware versions/builds are identified where relevant.
- [ ] Sensitive information has been removed.
- [ ] I have reviewed `CONTRIBUTING.md`.
- [ ] I have followed `SECURITY.md` for any security-sensitive findings.

## Additional Notes

Add anything else reviewers should know.