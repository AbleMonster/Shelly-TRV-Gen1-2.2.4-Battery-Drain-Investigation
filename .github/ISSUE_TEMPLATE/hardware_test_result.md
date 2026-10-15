---
name: Hardware test result
about: Submit battery, firmware, A/B, or long-term hardware test results
title: "[TEST] "
labels: testing
assignees: ''
---

# Hardware Test Result

## Test Summary

Briefly describe what was tested and why.

## Device

**Device:** Shelly TRV Gen1  
**Device label:**  
**Firmware version:**  
**Build:**  
**Firmware SHA256:**  
**Patch variant:**  

Use an anonymous device label if preferred.

## Test Period

**Start:**  
**End:**  
**Total duration:**  

## Test Conditions

Describe relevant conditions, including where available:

**Starting battery voltage:**  
**Ending battery voltage:**  
**Starting battery percentage:**  
**Ending battery percentage:**  
**Wi-Fi RSSI:**  
**Network/AP:**  
**Measurement interval:**  

Also mention:

- Charging events
- Reboots
- Configuration changes
- Network changes
- Manual interventions

## Patch / Control Configuration

Describe exactly what firmware or patch configuration was tested.

For A/B testing, identify:

### Control

Firmware / patch:

### Experimental

Firmware / patch:

## Measurements

Provide the relevant measurements, logs, reports, or data.

Battery voltage is preferred over battery percentage when evaluating battery consumption.

## Observed Behavior

Describe what happened during the test.

Examples:

- Battery-voltage trend
- Beacon Recovery events
- Connectivity
- Reconnects
- Device responsiveness
- Unexpected behavior
- Recovery-loop behavior

## Result

What conclusion is directly supported by this test?

## Limitations

Describe factors that may affect interpretation.

Examples:

- Different battery starting conditions
- Different RSSI
- Different TRV usage
- Different network conditions
- Short observation period
- Missing diagnostic statistics

## Raw Data / Attachments

Attach or reference relevant logs, CSV files, reports, or other test data.

Remove credentials, tokens, Wi-Fi credentials, and unnecessary personal information before uploading.

## Additional Notes

Add any other relevant information.