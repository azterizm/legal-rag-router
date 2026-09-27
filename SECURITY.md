# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |
| < 0.1 | No |

## Reporting a vulnerability

Please report suspected vulnerabilities privately to **abdullah@memonsystems.com**
with the subject line `legal-rag-router security`. Do not open a public issue.

Include the affected version, a description of the issue, and, where possible, a minimal
reproduction. You will receive an acknowledgement within 3 working days and a status update
within 10 working days.

## Scope notes

- The router makes no network calls and executes no code from the index it loads. The index
  is plain data (a sorted coordinate list plus JSON tables), verified against the SHA-256
  hashes in its manifest before use. Reports of ways to bypass that verification are in scope.
- Identifiers taken from a query reach the partition filter (`filters.py`) only after they
  pass the coordinate grammar and are found in the index. Any way to get query-controlled
  text into a filter expression is in scope.
- Pathological inputs that make routing exceed its latency budget (for example regular
  expression backtracking) are in scope.
