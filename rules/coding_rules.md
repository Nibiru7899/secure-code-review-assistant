# Original demo engineering guidance

These rules are approved for the synthetic pilot only. They are not MISRA rules
and do not establish standards compliance or certification.

RULE PTR-001
Title: Validate nullable pointers
Category: null-pointer
Check externally supplied or nullable pointers before dereferencing them.

RULE BND-001
Title: Validate array boundaries
Category: boundary
Read arrays only at nonnegative indices strictly below their element count.
Ensure string copies fit the destination including the terminating byte.

RULE RET-001
Title: Check operation results
Category: unchecked-return
Check file and I/O return values before using data or treating an operation as successful.

RULE INIT-001
Title: Initialize values before use
Category: initialization
Initialize local values on every path before reading or returning them.

RULE RES-001
Title: Release owned resources
Category: resource
Release an acquired file or other resource on every exit path where ownership is held.

RULE STATE-001
Title: Validate state transitions
Category: state
Activate a session only after it has entered the open state.
